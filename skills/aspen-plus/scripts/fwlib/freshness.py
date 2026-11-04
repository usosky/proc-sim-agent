"""Which run does each file of a case describe?

Aspen Plus writes the date and time of a run into the files of that run. This module reads those
stamps and compares them within one case (the files with the same name in one folder). File
modification times are never used: sync clients and copies rewrite them.

  .his  the header of the last run in the file (ORIGINAL, EDIT or RESTART RUN, date, time, RUN ID)
  .bkp  the results section ($_SUMMARY_FILE): RUN-STATUS date, time and run ID; line 1: when saved
  .sum  the same RUN-STATUS records as the results section of a .bkp
  .rep  the first-page header (date, time; or the page-header date) and INPUT FILE NAME (run ID)
  .cpm  the last control-panel event (<< ... hh:mm:ss Day Mon d, yyyy>>)

The .his stamp is the start of a run. The .rep stamp is written when the report is generated, at
the end of the run, so a long run puts it later than the .his; the RUN-STATUS stamp of a .bkp is
treated the same way. A file is stale when it describes an earlier run than another file of the
case:
  - run IDs differ (another engine session): older by more than a minute;
  - a .rep, .bkp, .sum or .cpm stamped before the start of the last run in the .his;
  - otherwise only when more than 12 hours older than the newest stamp (one run can take hours).
A .cpm stamp is compared with the others but never makes them stale: its last event can be an
export made long after the run.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from .common import natural_key, open_shared, side_file

RUN_EXTS = (".bkp", ".his", ".rep", ".cpm", ".sum")
FIX = "run, save, then File > Export > Report"
SESSION_SLACK = 60            # s: different run IDs
START_SLACK = 120             # s: a report or results stamped before the last run started
EVENT_SLACK = 600             # s: control-panel events before the last run started
SAME_SESSION_SLACK = 12 * 3600

_MON = {m: i for i, m in enumerate(("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT",
                                    "NOV", "DEC"), 1)}
LONG_DATE = re.compile(r"\b([A-Za-z]{3,9})\.?\s+(\d{1,2}),\s*(\d{4})\b")             # OCTOBER 2, 2026
TIME_12 = re.compile(r"\b(\d{1,2}):(\d{2}):(\d{2})\s*([AaPp])\.?\s*[Mm]\.?")         # 11:02:41 P.M.
EVENT_TIME = re.compile(r"\b(\d{1,2}):(\d{2}):(\d{2})\s+[A-Za-z]{3}\s+([A-Za-z]{3})\s+(\d{1,2}),\s*(\d{4})")
ASCTIME = re.compile(r"\b[A-Za-z]{3}\s+([A-Za-z]{3})\s+(\d{1,2})\s+(\d{1,2}):(\d{2}):(\d{2})\s+(\d{4})\b")
PAGE_DATE = re.compile(r"\bVER:\s*[\d.]+\s+(\d{2})/(\d{2})/(\d{4})\s+PAGE")         # 10/02/2026 (month first)

RUN_MARK = b"*** INPUT SUMMARY ***"        # his.parse splits runs at the same line
SUMMARY_MARK = b"$_SUMMARY_FILE"            # results section of a .bkp
CPM_EVENT = re.compile(rb"<<[ \t]*([^<>\r\n]*?)[ \t]+(\d{1,2}:\d{2}:\d{2}[ \t]+[A-Za-z]{3}[ \t]+[A-Za-z]{3}[ \t]+"
                       rb"\d{1,2},[ \t]*\d{4})[ \t]*>>")
STATUS_IT = re.compile(rb'DSET RUN-STATUS IT @IT \([ \t]*"([^"\r\n]*)"[ \t]+"([^"\r\n]*)"')
STATUS_RUNID = re.compile(rb'DSET RUN-STATUS RUNID @RUNID \([ \t]*"([^"\r\n]*)"')


# ---------------------------------------------------------------------------
# dates as Aspen Plus writes them (English month names whatever the Windows language)
# ---------------------------------------------------------------------------
def _month(name: str) -> Optional[int]:
    return _MON.get(name[:3].upper())


def _hour(h: str, ampm: str) -> int:
    return int(h) % 12 + (12 if ampm.upper() == "P" else 0)


def parse_datetime(text: str) -> Optional[datetime]:
    """'OCTOBER 2, 2026 11:02:41 P.M.', '23:02:40 Fri Oct 2, 2026' or 'Thu Sep 28 12:45:40 2023'."""
    try:
        m = EVENT_TIME.search(text)
        if m:
            h, mi, s, mon, d, y = m.groups()
            return datetime(int(y), _month(mon), int(d), int(h), int(mi), int(s))
        m = ASCTIME.search(text)
        if m:
            mon, d, h, mi, s, y = m.groups()
            return datetime(int(y), _month(mon), int(d), int(h), int(mi), int(s))
        d, t = LONG_DATE.search(text), TIME_12.search(text)
        if d and t and _month(d.group(1)):
            return datetime(int(d.group(3)), _month(d.group(1)), int(d.group(2)), _hour(t.group(1), t.group(4)),
                            int(t.group(2)), int(t.group(3)))
    except (TypeError, ValueError):     # unknown month name, impossible date
        return None
    return None


def _date_and_time(date_text: str, time_text: str) -> Optional[datetime]:
    return parse_datetime(f"{date_text} {time_text}")


def human(seconds: float) -> str:
    s = int(abs(seconds))
    if s < 120:
        return f"{s} s"
    if s < 7200:
        return f"{s // 60} min"
    if s < 2 * 86400:
        return f"{s // 3600} h {s % 3600 // 60} min"
    if s < 30 * 86400:
        return f"{s // 86400} days {s % 86400 // 3600} h"
    return f"{s // 86400} days"


def _iso(t: Optional[datetime], precision: str = "s") -> str:
    if not t:
        return ""
    return t.strftime("%Y-%m-%d") + " (date only)" if precision == "day" else t.strftime("%Y-%m-%d %H:%M:%S")


def _lo(s: dict) -> datetime:
    return s["time"]


def _hi(s: dict) -> datetime:
    """A stamp with the date only stands for the whole day."""
    return s["time"] + timedelta(seconds=86399) if s.get("precision") == "day" else s["time"]


# ---------------------------------------------------------------------------
# reading the stamps
# ---------------------------------------------------------------------------
def _head(path, n: int = 64 << 10) -> bytes:
    with open_shared(path) as fh:
        return fh.read(n)


def _find_all(path, needle: bytes, chunk: int = 8 << 20) -> List[int]:
    """Offsets of every occurrence of `needle`, read in chunks: files of hundreds of MB do not need to
    fit in memory."""
    out = []
    with open_shared(path) as fh:
        base, tail = 0, b""
        while True:
            block = fh.read(chunk)
            if not block:
                break
            buf = tail + block
            start = base - len(tail)
            i = buf.find(needle)
            while i >= 0:
                if not out or start + i > out[-1]:
                    out.append(start + i)
                i = buf.find(needle, i + 1)
            tail = buf[-(len(needle) - 1):] if len(needle) > 1 else b""
            base += len(block)
    return out


def _window(path, offset: int, n: int = 1500) -> bytes:
    with open_shared(path) as fh:
        fh.seek(offset)
        return fh.read(n)


def _text(b: bytes) -> str:
    return b.decode("cp1252", errors="replace")


def _run_id(name: str) -> str:
    return re.sub(r"\.inm$", "", (name or "").strip(), flags=re.I).lower()


def _his_stamp(path, st: dict) -> None:
    st["role"] = "start"
    marks = _find_all(path, RUN_MARK)
    st["runs"] = max(1, len(marks))
    if marks:
        lines = [l for l in _text(_window(path, marks[-1])).splitlines() if l.strip()][:12]
        for i, l in enumerate(lines):
            m = re.match(r"^\s*(ORIGINAL RUN|EDIT RUN|RESTART RUN)\s+(.*)$", l)
            if not m:
                continue
            st["run_type"] = m.group(1)
            d = LONG_DATE.search(m.group(2))
            t = next((TIME_12.search(x) for x in lines[i + 1:i + 3] if TIME_12.search(x)), None)
            if d and t:
                st["time"] = _date_and_time(d.group(0), t.group(0))
            for x in lines[i + 1:i + 6]:
                mm = re.match(r"^\s*RUN ID\s*:\s*(\S+)", x) or re.match(r"^\s*INPUT FILE:\s*(\S+)", x)
                if mm and not st.get("run_id"):
                    st["run_id"] = _run_id(mm.group(1))
            break
    if not st.get("time"):                  # no run header: the file header (date, then the time)
        _report_header(_text(_head(path, 8 << 10)), st)


def _report_header(text: str, st: dict) -> None:
    lines = text.splitlines()[:60]
    date = next((LONG_DATE.search(l.split("PLATFORM:", 1)[1]) for l in lines
                 if "PLATFORM:" in l and LONG_DATE.search(l.split("PLATFORM:", 1)[1])), None)
    tm = next((TIME_12.search(l) for l in lines if "INSTALLATION:" in l and TIME_12.search(l)), None)
    if date and tm:
        st["time"] = _date_and_time(date.group(0), tm.group(0))
        return
    m = PAGE_DATE.search(text)              # page header only: the date, no time
    if m:
        try:
            st["time"] = datetime(int(m.group(3)), int(m.group(1)), int(m.group(2)))
            st["precision"] = "day"
        except ValueError:
            pass


def _rep_stamp(path, st: dict) -> None:
    st["role"] = "end"
    text = _text(_head(path))
    _report_header(text, st)
    m = re.search(r"INPUT FILE NAME:\s*(\S+)", text)
    if m:
        st["run_id"] = _run_id(m.group(1))


def _status_records(data: bytes, st: dict) -> None:
    it, rid = STATUS_IT.search(data), STATUS_RUNID.search(data)
    st["has_results"] = bool(it or rid)
    if it:
        st["time"] = parse_datetime(_text(it.group(1)))
        st["run_id"] = _run_id(_text(it.group(2)))
    if rid and not st.get("run_id"):
        st["run_id"] = _run_id(_text(rid.group(1)))


def _bkp_stamp(path, st: dict) -> None:
    st["role"] = "end"
    first = _text(_head(path, 400)).splitlines()[:1]
    m = re.search(r'DATETIME\s+"([^"]*)"', first[0]) if first else None
    st["saved"] = parse_datetime(m.group(1)) if m else None
    marks = _find_all(path, SUMMARY_MARK)
    if not marks:
        st["has_results"] = False
        return
    _status_records(_window(path, marks[-1], 64 << 10), st)


def _sum_stamp(path, st: dict) -> None:
    st["role"] = "end"
    _status_records(_head(path), st)


def _cpm_stamp(path, st: dict) -> None:
    st["role"] = "event"
    last = None
    with open_shared(path) as fh:
        for line in fh:
            if b"<<" in line:
                m = CPM_EVENT.search(line)
                if m:
                    last = m
    if last:
        st["event"] = _text(last.group(1)).strip()
        st["time"] = parse_datetime(_text(last.group(2)))


def stamp(path) -> dict:
    """The run stamp of one file: {file, ext, role, time, run_id, ...}; time is None when not found."""
    p = Path(path)
    ext = p.suffix.lower()
    st = {"file": p.name, "ext": ext, "role": "", "time": None, "run_id": "", "precision": "s"}
    try:
        if ext == ".his":
            _his_stamp(p, st)
        elif ext == ".rep":
            _rep_stamp(p, st)
        elif ext == ".bkp":
            _bkp_stamp(p, st)
        elif ext == ".sum":
            _sum_stamp(p, st)
        elif ext == ".cpm":
            _cpm_stamp(p, st)
    except OSError as e:
        st["error"] = str(e)
    return st


# ---------------------------------------------------------------------------
# comparing the files of a case
# ---------------------------------------------------------------------------
def siblings(path) -> List[Path]:
    """The files of the same case: same folder, same name (any case), run-file extensions, no
    working, recovery or sync-conflict copies."""
    p = Path(path)
    folder, stem = p.parent, p.stem.lower()
    try:
        names = sorted(f for f in folder.iterdir() if f.is_file())
    except OSError:
        return [p]
    out = [f for f in names if f.stem.lower() == stem and f.suffix.lower() in RUN_EXTS and not side_file(f.name)]
    return out or [p]


def _slack(older: dict, newer: dict) -> float:
    if older["run_id"] and newer["run_id"] and older["run_id"] != newer["run_id"]:
        return SESSION_SLACK
    if newer["role"] == "start" and older["role"] == "end":
        return START_SLACK
    if newer["role"] == "start" and older["role"] == "event":
        return EVENT_SLACK
    return SAME_SESSION_SLACK


def compare(stamps: List[dict]) -> dict:
    """Verdict per file and for the case: fresh, stale (which file, older by how much) or unknown."""
    known = [s for s in stamps if s.get("time")]
    refs = [s for s in known if s["role"] != "event"]
    files: Dict[str, dict] = {}
    for s in stamps:
        r = {"ext": s["ext"], "time": _iso(s.get("time"), s.get("precision", "s")), "run_id": s.get("run_id", ""),
             "verdict": "unknown"}
        for k in ("run_type", "runs", "event", "has_results", "precision"):
            if k in s:
                r[k] = s[k]
        if s.get("saved"):
            r["saved"] = _iso(s["saved"])
        if s.get("time") and len(known) > 1:
            worst = None
            for ref in refs:
                if ref is s:
                    continue
                gap = (_lo(ref) - _hi(s)).total_seconds()
                if gap > _slack(s, ref) and (worst is None or gap > worst[0]):
                    worst = (gap, ref)
            if worst:
                r.update(verdict="stale", older_by=human(worst[0]), older_by_s=int(worst[0]),
                         than=worst[1]["file"], than_time=_iso(worst[1]["time"], worst[1].get("precision", "s")))
            else:
                r["verdict"] = "fresh"
        files[s["file"]] = r
    stale = [n for n, r in files.items() if r["verdict"] == "stale"]
    newest = max(refs or known, key=_hi) if known else None
    res = {"verdict": "stale" if stale else ("fresh" if len(known) > 1 else "unknown"),
           "files": files, "stale": stale, "notes": [],
           "last_run": {"file": newest["file"], "time": _iso(newest["time"], newest.get("precision", "s"))}
           if newest else {}}
    for s in stamps:                        # a .bkp saved without results after the run files were written
        if s["ext"] == ".bkp" and s.get("has_results") is False and s.get("saved"):
            older = [k for k in known if k is not s and (s["saved"] - _hi(k)).total_seconds() > START_SLACK]
            if older:
                res["notes"].append(
                    f"{s['file']} holds no results and was saved on {_iso(s['saved'])}, after the run in "
                    f"{', '.join(k['file'] for k in older)}: if the input changed, those files describe the "
                    f"old input ({FIX})")
    return res


def check_case(path) -> dict:
    """Compare a file with the other files of its case."""
    return compare([stamp(f) for f in siblings(path)])


def warning_lines(path, res: Optional[dict] = None) -> List[str]:
    """The lines his, rep, check and cpm print at the top: the file read is older than the last run."""
    res = res if res is not None else check_case(path)
    name = Path(path).name
    r = res["files"].get(name)
    out = []
    if r and r["verdict"] == "stale":
        out.append(f"WARNING: {name} describes an older run than {r['than']} ({r['time']} vs {r['than_time']}, "
                   f"{r['older_by']} older). The numbers below are from that older run. Fix: {FIX}.")
    out += [f"Note: {n}" for n in res["notes"] if name in n]
    return out


def sort_key(path):
    """For picking a file of a folder: newest run stamp first known, then the name (never file times)."""
    t = stamp(path).get("time")
    return (t is not None, t or datetime.min, natural_key(Path(path).name))


def describe(res: dict) -> str:
    """One line for sim-scan: which files are stale and why."""
    parts = []
    for n, r in res["files"].items():
        if r["verdict"] == "stale":
            parts.append(f"{n} is {r['older_by']} older than the run in {r['than']}")
    return "; ".join(parts)

