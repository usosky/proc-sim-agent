"""Scan simulation folders (one folder per model version) and summarise what each holds.

Recommended layout (any depth works):
  <project>/<model>/<version folder>/  model.bkp  model.apw(z)  model.his  model.rep  model.cpm  notes.md ...

For every folder that contains Aspen files the scan reports: the files by type,
engine version, last run status (from the .his summary of errors), whether the
.his is older than the model file (results may be stale), missing exports, and
temporary run files (_xxxxxxx.*) mapped to their model through the Runid line.
The .def file (engine settings) holds the Windows user name and install path; it
is listed but never read.
"""
from __future__ import annotations

import re
from collections import OrderedDict
from pathlib import Path
from typing import List

from .common import (ENGINE_FILE_RX, ENGINE_TO_RELEASE, RECOVERY_RX, human_size, mtime_str, natural_key,
                     open_shared, side_file)

FILE_TYPES = OrderedDict([
    (".apw", "document (binary quick-restart file, version-specific)"),
    (".apwz", "compound file (model + all files it uses)"),
    (".bkp", "backup (ASCII, portable between versions)"),
    (".apmbd", "embedded objects (binary; keep with the .bkp)"),
    (".appdf", "problem definition (binary arrays, convergence data)"),
    (".apt", "template"),
    (".his", "history: input echo, messages, trace"),
    (".rep", "report (export)"),
    (".cpm", "control-panel messages (export)"),
    (".inp", "input-language file (export)"),
    (".sum", "summary file (results, DSET records)"),
    (".apsst", "stream-summary template (XML)"),
    (".slb", "stream library (binary)"),
    (".dfm", "property parameters (DFMS text)"),
    (".apprj", "project data (Prop-Data input language)"),
    (".hch", "Energy Analyzer case (binary)"),
    (".xml", "XML (e.g. results export or energy-analysis setup)"),
    (".def", "engine settings (contains user name - not read)"),
    (".xlsx", "spreadsheet"), (".xls", "spreadsheet"), (".csv", "table"),
    (".md", "notes"), (".txt", "notes"), (".docx", "document"), (".pdf", "document"),
    # engine working files of an open/crashed session (_xxxxxxx.*)
    (".inm", "engine input file (run copy)"), (".in0", "engine working file"), (".inx", "engine working file"),
    (".nin", "engine working file"), (".sin", "engine working file"), (".sor", "engine working file"),
    (".rp1", "report part (run copy)"), (".rp2", "report part (run copy)"), (".jnl", "engine command journal"),
    (".scr", "engine scratch (binary; contains user name - not read)"), (".ads", "engine working file"),
    (".prd", "engine working file"), (".dyl", "engine working file"), (".plf", "engine working file"),
    (".for", "user Fortran (usually empty)"),
    (".bk$", "recovery copy of the .bkp written while the case is open"),
    (".hc$", "recovery copy of the .hch"), (".xm$", "recovery copy of the .xml"),
])
NEVER_READ = {".def", ".scr"}  # may hold the Windows user name / install paths
MODEL_EXT = {".apw", ".apwz", ".bkp"}
RUN_EXT = {".his", ".rep", ".cpm", ".inp", ".sum"}
TEMP_RX = ENGINE_FILE_RX  # engine working files _xxxxxxx.* (name kept for callers)


def _his_quick(path: Path) -> dict:
    """Read only what sim-scan needs from a .his: engine, Runid, error summary."""
    info = {}
    try:
        size = path.stat().st_size
        with open_shared(path) as fh:
            if size <= (8 << 20):
                raw = fh.read()
            else:  # long histories (up to the 500 MB limit): header and the end are enough here
                raw = fh.read(2 << 20)
                fh.seek(size - (4 << 20))
                raw += b"\n" + fh.read()
        text = raw.decode("cp1252", errors="replace")
    except OSError:
        return info
    m = re.search(r"VERSION:\s*([\d.]+)\s+Build", text)
    if m:
        info["engine"] = m.group(1)
    m = re.search(r";Directory\s*.*?Runid\s+(.+)", text)
    if m:
        info["runid"] = m.group(1).strip()
    tabs = list(re.finditer(r"\*\*\* SUMMARY OF ERRORS \*\*\*", text))
    none = list(re.finditer(r"NO ERRORS OR WARNINGS GENERATED", text))
    if tabs and (not none or tabs[-1].start() > none[-1].start()):
        seg = text[tabs[-1].start(): tabs[-1].start() + 900]
        for key in ("TERMINAL ERRORS", "SEVERE ERRORS", "ERRORS", "WARNINGS"):
            mm = re.search(r"^\s*" + key + r"\s+(\d+)\s+(\d+)\s+(\d+)", seg, re.M)
            if mm:
                info[key.lower().replace(" ", "_")] = sum(int(x) for x in mm.groups())
    elif none:
        info["errors"] = info["warnings"] = 0
    elif "SIMULATION CALCULATIONS BEGIN" in text:
        if "Results generated" in text or "Report file generated" in text:
            info["finished_unsaved"] = True
        else:
            info["incomplete"] = True
    last = {}
    for name, state in re.findall(r"LOOP\s+(\S+)\s+ITER\s+\d+:\s*(.*?)\s*,?\s*MAX ERR/TOL", text):
        last[name] = state
    info["not_converged"] = [n for n, st in last.items() if "NOT CONVERGED" in st.upper()]
    return info


def _bkp_engine(path: Path) -> str:
    try:
        with open_shared(path) as fh:
            head = fh.read(200).decode("cp1252", errors="replace")
    except OSError:
        return ""
    m = re.search(r'VERSION\s+"([\d.]+)"', head)
    return m.group(1) if m else ""


def scan(roots: List[str], max_depth: int = 5) -> List[dict]:
    folders = OrderedDict()
    for r in roots:
        root = Path(r).expanduser()
        if not root.exists():
            continue
        for p in [root] + [d for d in root.rglob("*") if d.is_dir()]:
            try:
                depth = len(p.relative_to(root).parts)
            except ValueError:
                depth = 0
            if depth > max_depth:
                continue
            files = [f for f in p.iterdir() if f.is_file()]
            if not any(f.suffix.lower() in MODEL_EXT | RUN_EXT for f in files):
                continue
            folders[str(p)] = _summarise_folder(p, files, root)
    out = list(folders.values())
    out.sort(key=lambda d: natural_key(d["rel"]))
    return out


def _summarise_folder(p: Path, files: List[Path], root: Path) -> dict:
    d = {"path": str(p), "rel": p.relative_to(root).as_posix() if p != root else ".", "files": [],
         "models": OrderedDict(), "temp_runs": [], "notes": [], "version_note": ""}
    for cand in ("notes.md", "NOTES.md", "notes.txt", "README.md", "CHANGES.md", "changes.txt"):
        nf = p / cand
        if nf.is_file():
            try:
                for line in nf.read_text(encoding="utf-8", errors="replace").splitlines():
                    line = line.strip().lstrip("#").strip()
                    if line:
                        d["version_note"] = line[:90]
                        break
            except OSError:
                pass
            break
    for f in sorted(files, key=lambda x: natural_key(x.name)):
        ext = f.suffix.lower()
        try:
            size = f.stat().st_size
        except OSError:
            size = 0
        entry = {"name": f.name, "type": FILE_TYPES.get(ext, ext or "file"), "size": human_size(size),
                 "modified": mtime_str(f)}
        d["files"].append(entry)
        kind = side_file(f.name)
        if kind == "recovery":
            d.setdefault("recovery", []).append(f.name)
            continue
        if kind == "conflict":                 # a sync client's copy: never read as the model
            d.setdefault("conflicts", []).append(f.name)
            continue
        if kind == "engine":
            d.setdefault("temp_files", 0)
            d["temp_files"] += 1
            if ext == ".his":
                info = _his_quick(f)
                d["temp_runs"].append({"file": f.name, "runid": info.get("runid", "?"), "modified": entry["modified"]})
            continue
        if ext in MODEL_EXT | RUN_EXT:
            key = f.stem.lower()  # Aspen writes exports in lower case ('model.rep' next to 'Model.bkp')
            m = d["models"].setdefault(key, {"name": f.stem, "files": {}, "engine": "", "run_engine": "",
                                             "status": ""})
            if ext in MODEL_EXT:
                m["name"] = f.stem
            m["files"][ext] = {"modified": entry["modified"], "mtime": f.stat().st_mtime if f.exists() else 0}
            if ext == ".bkp" and not m["engine"]:
                m["engine"] = _bkp_engine(f)
            if ext == ".his":
                info = _his_quick(f)
                m["his"] = info
                m["run_engine"] = info.get("engine", "")
    for key, m in d["models"].items():
        stem = m["name"]
        exts = m["files"]
        file_rel = ENGINE_TO_RELEASE.get(m["engine"], m["engine"])
        run_rel = ENGINE_TO_RELEASE.get(m["run_engine"], m["run_engine"])
        m["release"] = file_rel or run_rel
        if file_rel and run_rel and file_rel != run_rel:
            m["release"] = f"{file_rel} file, run in {run_rel}"
        h = m.get("his", {})
        if h:
            if h.get("incomplete"):
                m["status"] = "run started, no error summary (interrupted or session still open)"
            elif h.get("finished_unsaved"):
                m["status"] = "run finished, results generated (error summary is written on save - see .cpm)"
            elif "errors" in h or "warnings" in h:
                parts = []
                for k in ("terminal_errors", "severe_errors", "errors", "warnings"):
                    if h.get(k):
                        parts.append(f"{h[k]} {k.replace('_', ' ')}")
                m["status"] = "completed" + (": " + ", ".join(parts) if parts else ", no errors or warnings")
            if h.get("not_converged"):
                m["status"] += "; NOT CONVERGED: " + ", ".join(h["not_converged"])
            norm = lambda x: re.sub(r"[^A-Z0-9]", "", x.upper())
            if h.get("runid") and norm(h["runid"]) != norm(stem):
                m["runid_note"] = f"his Runid is {h['runid']} (file was renamed or saved under another name)"
        else:
            m["status"] = "no .his in this folder (never run here, or history not kept)"
        model_times = [v["mtime"] for e, v in exts.items() if e in MODEL_EXT]
        if ".his" in exts and model_times and max(model_times) > exts[".his"]["mtime"] + 60:
            d["notes"].append(f"{stem}: model saved after the last .his - results in .his may be stale")
        if exts.keys() & MODEL_EXT and ".rep" not in exts:
            d["notes"].append(f"{stem}: no .rep export (File > Export > Report Files) - stream results unavailable")
    return d


def render_markdown(folders: List[dict]) -> str:
    if not folders:
        return "No folders with Aspen files found."
    L = ["# Simulation folders", ""]
    L.append("| Folder | Model | Release | Files | Last run status | Version note |")
    L.append("|---|---|---|---|---|---|")
    for d in folders:
        if not d["models"]:
            L.append(f"| {d['rel']} | (temporary files only) |  | {len(d['files'])} |  | {d['version_note']} |")
        for key, m in d["models"].items():
            exts = " ".join(sorted(m["files"].keys()))
            L.append(f"| {d['rel']} | {m['name']} | {m['release'] or '?'} | {exts} | {m['status']} | "
                     f"{d['version_note']} |")
    notes = [(d["rel"], n) for d in folders for n in d["notes"]]
    runid = [(d["rel"], m["name"], m["runid_note"]) for d in folders for m in d["models"].values() if m.get("runid_note")]
    temps = [(d["rel"], t) for d in folders for t in d["temp_runs"]]
    rec = [(d["rel"], d["recovery"]) for d in folders if d.get("recovery")]
    tmpc = [(d["rel"], d["temp_files"]) for d in folders if d.get("temp_files")]
    conf = [(d["rel"], d["conflicts"]) for d in folders if d.get("conflicts")]
    if notes or runid or temps or rec or tmpc or conf:
        L.append("")
        L.append("## Notes")
        for rel, n in notes:
            L.append(f"- {rel}: {n}")
        for rel, s, n in runid:
            L.append(f"- {rel}/{s}: {n}")
        for rel, t in temps:
            L.append(f"- {rel}: temporary run file {t['file']} belongs to Runid {t['runid']} ({t['modified']})")
        for rel, n in tmpc:
            L.append(f"- {rel}: {n} engine working files (_xxxxxxx.*) - the case is open in Aspen, or Aspen closed "
                     "abnormally; normally they disappear when the case is closed")
        for rel, names in conf:
            L.append(f"- {rel}: sync-conflict copies, not read: {', '.join(names)}. A sync client kept two "
                     "versions of the same file; open both in Aspen, keep the right one and delete the other")
        for rel, names in rec:
            L.append(f"- {rel}: backup copies {', '.join(names)} (appear while a case is open; keep them until the "
                     "main file opens and runs)")
    return "\n".join(L)
