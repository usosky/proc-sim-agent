"""Read an Aspen Plus report file (.rep): run information, convergence status, overall balance,
block results, stream tables and problem status.

Reports are paged text; every page starts with
  ' ASPEN PLUS   PLAT: WIN-X64   VER: 41.0      10/02/2026  PAGE 26'
followed by the section title. Numbers use Fortran styles such as '1.2104-06' (= 1.2104E-06),
'-0.163319+08' and '9,237,420.'.

Privacy: the 'LICENSED TO' line and 'LOCATED IN:' paths are never reported.
"""
from __future__ import annotations

import csv
import re
from collections import OrderedDict
from pathlib import Path
from typing import Dict, List, Optional

from .common import ENGINE_TO_RELEASE, fmt_num, read_text_any

PAGE_RX = re.compile(r"^\f?\s*ASPEN PLUS\s+PLAT:\s*(\S+)\s+VER:\s*([\d.]+)\s+(\S+)\s+PAGE\s+(\S+)\s*$")
BLOCK_RX = re.compile(r"^ BLOCK:\s+(\S+)\s+MODEL:\s+(\S+)(\s+\(CONTINUED\))?")
FORT_NUM = re.compile(r"^([-+]?\d*\.?\d+)([-+]\d{1,3})$")
PRIVATE = re.compile(r"LICENSED TO|LOCATED IN:", re.I)


def to_float(tok: str) -> Optional[float]:
    """Parse report numbers: '1.2104-06', '-0.163319+08', '9,237,420.', '0.23401E-13', '.12866E-11'."""
    if tok is None:
        return None
    t = tok.strip().replace(",", "")
    if not t or t.upper() in ("MISSING", "----"):
        return None
    m = FORT_NUM.match(t)
    if m:
        try:
            return float(m.group(1) + "e" + m.group(2))
        except ValueError:
            return None
    try:
        return float(t.replace("D", "E").replace("d", "e"))
    except ValueError:
        return None


def _is_val(tok: str) -> bool:
    return to_float(tok) is not None or tok.upper() == "MISSING"


# ---------------------------------------------------------------------------
# paging
# ---------------------------------------------------------------------------
_SECTION_RX = re.compile(r"^([A-Z][A-Z0-9 ./&-]*SECTION)(\s+\(CONTINUED\))?$")


def _pages(lines: List[str]):
    """Yield dicts {section, page, lines} with page headers and section titles removed.

    The section title is the first line after the page header that ends in 'SECTION'; a run
    title (TITLE paragraph) printed under the page header is skipped. A page without a section
    title continues the previous page's section.
    """
    pages = []
    cur = None
    pre: List[str] = []
    prev_section = None
    pending: List[str] = []
    for l in lines:
        m = PAGE_RX.match(l)
        if m:
            if cur is not None and cur["section"] is None:  # page ended before a title was found
                cur["section"] = prev_section or "?"
                cur["lines"].extend(pending)
            pending = []
            cur = {"platform": m.group(1), "engine": m.group(2), "date": m.group(3), "page": m.group(4),
                   "section": None, "lines": []}
            pages.append(cur)
            continue
        if cur is None:
            pre.append(l)
            continue
        if cur["section"] is None:
            st = l.strip()
            if not st:
                continue
            sm = _SECTION_RX.match(st)
            if sm:
                cur["section"] = sm.group(1)
                prev_section = sm.group(1)
                pending = []  # a run title above the section name is dropped
                continue
            pending.append(l)
            if len(pending) >= 3:  # no section title on this page
                cur["section"] = prev_section or pending[0].strip()
                cur["lines"].extend(pending if prev_section else pending[1:])
                pending = []
            continue
        cur["lines"].append(l)
    if cur is not None and cur["section"] is None:
        cur["section"] = prev_section or "?"
        cur["lines"].extend(pending)
    return pre, pages


def parse(path) -> dict:
    text = read_text_any(Path(path))
    lines = text.split("\n")
    pre, pages = _pages(lines)
    sections: "OrderedDict[str, List[str]]" = OrderedDict()
    for p in pages:
        sections.setdefault(p["section"], []).extend(p["lines"])
    first = pages[0] if pages else {}
    out = OrderedDict(file=str(path))
    out["engine"] = first.get("engine", "")
    out["release"] = ENGINE_TO_RELEASE.get(out["engine"], "")
    out["platform"] = first.get("platform", "")
    out["date"] = first.get("date", "")
    out["n_pages"] = len(pages)
    out["sections"] = [s for s in sections if s.endswith("SECTION")]
    out["run_control"] = _run_control(sections.get("RUN CONTROL SECTION", []))
    fs = sections.get("FLOWSHEET SECTION", [])
    out["convergence"] = _convergence(fs)
    out["overall_balance"] = _balance(fs)
    out["blocks"] = _blocks(sections.get("U-O-S BLOCK SECTION", []))
    out["streams"] = _streams(sections.get("STREAM SECTION", []))
    out["problem_status"] = _problem_status(sections.get("PROBLEM STATUS SECTION", []))
    out["_sections"] = sections
    return out


def _clean(lines: List[str]) -> List[str]:
    return [l.rstrip() for l in lines if not PRIVATE.search(l)]


def _run_control(lines):
    info = OrderedDict()
    for l in lines:
        if PRIVATE.search(l):
            continue
        m = re.match(r"^\s*(TYPE OF RUN|INPUT FILE NAME|OUTPUT PROBLEM DATA FILE NAME|CALLING PROGRAM NAME):\s*(.*)$", l)
        if m:
            info[m.group(1).lower()] = m.group(2).strip()
        if "SIMULATION REQUESTED" in l:
            info["scope"] = l.strip()
    return info


def _convergence(lines):
    rows = []
    in_tear = False
    for l in lines:
        if "TEAR STREAM SUMMARY" in l or "DESIGN-SPEC SUMMARY" in l or "SPEC SUMMARY" in l:
            in_tear = True
            continue
        if in_tear:
            m = re.match(r"^\s+(\S+)\s+(.+?)\s+([-+]?[\d.]+(?:[EeDd]?[-+]\d+)?)\s+([-+]?[\d.]+(?:[EeDd]?[-+]\d+)?)\s+"
                         r"([-+]?[\d.]+(?:[EeDd]?[-+]\d+)?)\s+([#*])\s+(\S+)", l)
            if m:
                rows.append({"stream_or_spec": m.group(1), "variable": m.group(2).strip(), "max_err_tol": m.group(3),
                             "status": "converged" if m.group(6) == "#" else "NOT CONVERGED", "block": m.group(7)})
            if l.strip().startswith(("#  =", "*  =")):
                in_tear = False
    return rows


def _balance(lines):
    out = OrderedDict()
    start = None
    for i, l in enumerate(lines):
        if "OVERALL FLOWSHEET BALANCE" in l:
            start = i
            break
    if start is None:
        return out
    for l in lines[start:start + 120]:
        m = re.match(r"^\s+(MOLE|MASS|ENTHALPY)\(([^)]*)\)\s+(.*)$", l)
        if m:
            nums = [to_float(t) for t in m.group(3).split()]
            out[f"{m.group(1)} ({m.group(2).strip()})"] = nums
    return out


_UNIT_WORDS = {"C", "K", "F", "R", "BAR", "MBAR", "ATM", "PSIA", "PSIG", "KPA", "MPA", "PA", "KW", "MW", "W", "HP",
               "SQM", "SQFT", "M", "MM", "CM", "METER", "SEC", "HR", "MIN", "%"}


def _is_unit(tok: str) -> bool:
    tok = tok.rstrip(",")
    return tok in _UNIT_WORDS or (("/" in tok or tok.startswith("M-")) and len(tok) <= 14
                                  and re.match(r"^[A-Z%][A-Z0-9%*.\-/]*$", tok) is not None)


def _kv_line(l: str):
    """'    REBOILER DUTY    CAL/SEC   9,237,420.' -> ('REBOILER DUTY', 'CAL/SEC', 9237420.0); table rows -> None."""
    m = re.match(r"^(.*?)\s+(\S+)\s*$", l.rstrip())
    if not m:
        return None
    head, last = m.group(1), m.group(2)
    val = to_float(last)
    if val is None or not head.strip():
        return None
    toks = head.split()
    # a second number in the label means this is a table row (component split fractions, profiles, ...)
    if any(re.search(r"[.Ee]", t) and to_float(t) is not None for t in toks):
        return None
    unit = ""
    if len(toks) > 1 and _is_unit(toks[-1]):
        unit = toks[-1].rstrip(",")
        toks = toks[:-1]
    label = " ".join(toks).rstrip(",:")
    if not re.search(r"[A-Z]{2}", label):
        return None
    return label, unit, val


_KEY_ORDER = ("DUTY", "NET WORK", "ELECTRICITY", "BRAKE", "OUTLET TEMP", "OUTLET PRES", "TOP STAGE TEMP",
              "BOTTOM STAGE TEMP", "REFLUX RATIO", "BOILUP RATIO", "VAPOR FRACTION", "PRESSURE CHANGE",
              "CALCULATED OUTLET TEMP", "HEAT TRANSFER AREA", "AREA", "LMTD", "UA ")


def key_results(b: dict, n: int = 6):
    """Most informative results first (duties, power, outlet T/P, reflux...)."""
    scored = []
    for idx, (lab, unit, val) in enumerate(b["results"]):
        rank = next((k for k, word in enumerate(_KEY_ORDER) if word in lab), len(_KEY_ORDER))
        scored.append((rank, idx, lab, unit, val))
    scored.sort()
    seen, out = set(), []
    for rank, idx, lab, unit, val in scored:
        if lab in seen:
            continue
        seen.add(lab)
        out.append((lab, unit, val))
        if len(out) >= n:
            break
    return out


def _blocks(lines):
    blocks: "OrderedDict[str, dict]" = OrderedDict()
    cur = None
    for l in lines:
        m = BLOCK_RX.match(l)
        if m:
            name, model = m.group(1), m.group(2)
            cur = blocks.setdefault(name, {"model": model, "lines": [], "results": [], "balance": OrderedDict()})
            continue
        if cur is not None:
            cur["lines"].append(l)
    for name, b in blocks.items():
        in_results = False
        for l in b["lines"]:
            if "****  RESULTS  ****" in l or "***  RESULTS  ***" in l:
                in_results = True
                continue
            mb = re.match(r"^\s+(MOLE|MASS|ENTHALPY)\(([^)]*)\)\s+(.*)$", l)
            if mb and not in_results:
                b["balance"][mb.group(1)] = [to_float(t) for t in mb.group(3).split()]
                continue
            if in_results and len(b["results"]) < 60:
                kv = _kv_line(l)
                if kv:
                    b["results"].append(kv)
        b["lines"] = _clean(b["lines"])
    return blocks


def _streams(lines):
    streams: "OrderedDict[str, OrderedDict]" = OrderedDict()
    ids: List[str] = []
    cols: List[int] = []
    group = ""
    substream = "MIXED"
    for l in lines:
        if not l.strip() or set(l.strip()) <= set("-"):
            continue
        if l.startswith(" STREAM ID"):
            ids = l.split()[2:]
            cols, pos = [], 10
            for x in ids:  # right edge of each column header, searched left to right
                k = l.index(x, pos)
                pos = k + len(x)
                cols.append(pos)
            for s in ids:
                streams.setdefault(s, OrderedDict())
            continue
        if not ids:
            continue
        st = l.strip()
        if re.match(r"^[A-Z0-9+\- ]+\(CONTINUED\)\s*$", st) or (st.split() == ids):
            continue
        if st.startswith("FROM :") or st.startswith("TO   :") or st.startswith("TO :"):
            key = "FROM" if st.startswith("FROM") else "TO"
            vals = st.split(":", 1)[1].split()
            for s, v in zip(ids, vals):
                streams[s][key] = v
            continue
        if st.startswith("SUBSTREAM:"):
            substream = st.split(":", 1)[1].strip()
            group = ""
            continue
        if st.startswith("PHASE:"):
            for s, v in zip(ids, st.split(":", 1)[1].split()):
                streams[s][f"{substream}|PHASE"] = v
            continue
        toks = st.split()
        nval = 0
        for t in reversed(toks):
            if _is_val(t) and nval < len(ids):
                nval += 1
            else:
                break
        label_toks = toks[:len(toks) - nval]
        if nval == 0:
            group = st.rstrip(":").strip()
            continue
        label = " ".join(label_toks)
        indented = l.startswith("   ")
        key = f"{substream}|{group}|{label}" if (indented and group) else f"{substream}|{label}"
        vals = toks[len(toks) - nval:]
        if nval == len(ids):
            pairs = zip(ids, vals)
        else:  # some cells blank: place values by their right edge
            pairs = []
            pos = 0
            for v in vals:
                k = l.index(v, pos)
                pos = k + len(v)
                j = min(range(len(cols)), key=lambda c: abs(cols[c] - pos))
                pairs.append((ids[j], v))
        for s, v in pairs:
            streams[s][key] = v
    return streams


def _problem_status(lines):
    out = []
    for l in lines:
        s = l.strip().strip("*").strip()
        if s and not set(s) <= set("-") and s != "BLOCK STATUS":
            out.append(s)
    return out


# ---------------------------------------------------------------------------
# convenience views
# ---------------------------------------------------------------------------
def stream_value(st: Dict[str, str], *candidates: str) -> Optional[str]:
    for c in candidates:
        for k, v in st.items():
            if k.endswith("|" + c) or k == c:
                return v
    return None


MAIN_PROPS = [("From", ("FROM",)), ("To", ("TO",)), ("Phase", ("PHASE",)),
              ("T", ("TEMP C", "TEMP K", "TEMP F")), ("P", ("PRES BAR", "PRES ATM", "PRES N/SQM", "PRES KPA", "PRES PSIA",
                                                         "PRES MBAR")),
              ("Vapor frac", ("VFRAC",)), ("Mole flow", ("TOTAL FLOW|KMOL/HR", "TOTAL FLOW|KMOL/SEC", "TOTAL FLOW|LBMOL/HR")),
              ("Mass flow", ("TOTAL FLOW|KG/HR", "TOTAL FLOW|KG/SEC", "TOTAL FLOW|LB/HR"))]


def stream_table(d: dict, names: List[str], components: bool = True, min_value: float = 1e-6) -> str:
    st = d["streams"]
    lut = {k.upper(): k for k in st}
    if not names or [n.lower() for n in names] == ["all"]:
        names = list(st.keys())
    names = [lut[n.upper()] for n in names if n.upper() in lut]  # stream names are upper case in reports
    if not names:
        return "No such streams in the report. Available: " + ", ".join(st.keys())
    rows = []
    for label, keys in MAIN_PROPS:
        row = []
        unit = ""
        for n in names:
            v = None
            for k in keys:
                v = stream_value(st[n], k)
                if v is not None:
                    unit = k.split("|")[-1].split(" ", 1)[1] if " " in k.split("|")[-1] else (
                        k.split("|")[-1] if "|" in k else "")
                    break
            row.append(v or "")
        if any(row):
            rows.append((f"{label} ({unit})" if unit and label not in ("From", "To", "Phase", "Vapor frac") else label, row))
    if components:
        basis = None
        for cand in ("COMPONENTS: KG/HR", "COMPONENTS: KMOL/HR", "COMPONENTS: MASS FRAC", "COMPONENTS: MOLE FRAC"):
            if any(cand in k for n in names for k in st[n]):
                basis = cand
                break
        if basis:
            comps = []
            for n in names:
                for k in st[n]:
                    if f"|{basis}|" in k:
                        c = k.split("|")[-1]
                        if c not in comps:
                            comps.append(c)
            for c in comps:
                vals = [stream_value(st[n], f"{basis}|{c}") or "" for n in names]
                if any((to_float(v) or 0) > min_value for v in vals):
                    rows.append((f"{c} [{basis.split(': ')[1].lower()}]", vals))
    def nice(v):
        f = to_float(v)
        return v if f is None or v in ("----",) else fmt_num(f, 5)
    out = ["| | " + " | ".join(names) + " |", "|---|" + "---|" * len(names)]
    for label, vals in rows:
        shown = vals if label in ("From", "To", "Phase") else [nice(v) for v in vals]
        out.append(f"| {label} | " + " | ".join(shown) + " |")
    return "\n".join(out)


def write_csv(d: dict, path: str):
    st = d["streams"]
    keys: List[str] = []
    for s in st.values():
        for k in s:
            if k not in keys:
                keys.append(k)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["property"] + list(st.keys()))
        for k in keys:
            w.writerow([k] + [st[s].get(k, "") for s in st])


def render_markdown(d: dict, max_results: int = 6) -> str:
    L = [f"# Report: {Path(d['file']).name}"]
    L.append(f"- Aspen Plus {d['release'] or ''} (engine {d['engine']}), {d['date']}, {d['n_pages']} pages")
    rc = d["run_control"]
    if rc:
        L.append(f"- Run: {rc.get('type of run', '?')}; input {rc.get('input file name', '?')}"
                 + (f"; {rc['scope'].lower()}" if rc.get("scope") else ""))
    if d["problem_status"]:
        L.append("")
        L.append("## Problem status")
        L.extend("- " + s for s in d["problem_status"][:30])
    if d["convergence"]:
        L.append("")
        L.append("## Convergence status")
        L.append("| Tear/spec | Variable | Max err/tol | Status | Block |")
        L.append("|---|---|---|---|---|")
        for r in d["convergence"]:
            L.append(f"| {r['stream_or_spec']} | {r['variable']} | {r['max_err_tol']} | {r['status']} | {r['block']} |")
    if d["overall_balance"]:
        L.append("")
        L.append("## Overall flowsheet balance")
        for k, v in d["overall_balance"].items():
            # four columns when there is a generation term (moles with reactions), else three
            names = ("in", "out", "generation", "rel. diff") if len(v) >= 4 else ("in", "out", "rel. diff")
            L.append(f"- {k}: " + ", ".join(f"{n} {'' if x is None else f'{x:.6g}'}" for n, x in zip(names, v)))
    if d["blocks"]:
        L.append("")
        L.append(f"## Blocks ({len(d['blocks'])})")
        L.append("| Block | Model | Key results (report units) |")
        L.append("|---|---|---|")
        for name, b in d["blocks"].items():
            res = "; ".join(f"{lab} = {val:.6g} {unit}".strip() for lab, unit, val in key_results(b, max_results))
            L.append(f"| {name} | {b['model']} | {res} |")
    if d["streams"]:
        L.append("")
        L.append(f"## Streams ({len(d['streams'])}): " + ", ".join(d["streams"].keys()))
        L.append("Show a table: `fw.py rep <file> --streams NAME1,NAME2` (or `--csv out.csv` for all properties).")
    L.append("")
    L.append("Sections: " + ", ".join(d["sections"]))
    return "\n".join(L)


def block_text(d: dict, name: str) -> str:
    for n, b in d["blocks"].items():
        if n.upper() == name.upper():
            return f"BLOCK {n} ({b['model']})\n" + "\n".join(l for l in b["lines"] if l.strip())
    return f"No block {name!r}. Blocks: " + ", ".join(d["blocks"].keys())


def section_text(d: dict, name: str) -> str:
    for s, lines in d["_sections"].items():
        if name.upper() in s.upper():
            return f"== {s} ==\n" + "\n".join(_clean([l for l in lines if l.strip()]))
    return f"No section {name!r}. Sections: " + ", ".join(d["sections"])


def find(d: dict, text: str, context: int = 1) -> str:
    out = []
    rx = re.compile(re.escape(text), re.I)
    for s, lines in d["_sections"].items():
        for i, l in enumerate(lines):
            if rx.search(l) and not PRIVATE.search(l):
                lo, hi = max(0, i - context), min(len(lines), i + context + 1)
                out.append(f"[{s}]")
                out.extend(x.rstrip() for x in lines[lo:hi] if x.strip() and not PRIVATE.search(x))
                out.append("")
    return "\n".join(out) if out else f"'{text}' not found."
