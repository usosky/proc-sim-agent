"""Summarise an Aspen Plus backup file (.bkp).

A .bkp is ASCII: a header (engine version, date), a block list, the input as a
serialised tree of sections (`? SECTION NAME ? \\ RECORD KEY = VALUE ... \\`),
GRAPHICS_BACKUP (flowsheet drawing), and a $_SUMMARY_FILE with run status and
results. This module reads the input tree and the run-status messages.

Privacy: the RUN-STATUS VERS record holds the Windows user and computer name;
it is never reported.
"""
from __future__ import annotations

import re
from collections import OrderedDict
from pathlib import Path
from typing import List

from .common import ENGINE_TO_RELEASE, read_text_any

_TOKEN = re.compile(r'"(?:[^"\\]|\\.)*"|<[^<>\s]*>|[()\\/;=?]|[^\s()\\/;=?"]+')


def _tokens(text: str):
    for m in _TOKEN.finditer(text):
        t = m.group(0)
        if t.startswith("<") and t.endswith(">"):
            continue  # unit / status annotations like <0> <20>
        yield t


def _unq(t: str) -> str:
    return t[1:-1] if len(t) >= 2 and t[0] == '"' and t[-1] == '"' else t


def parse_sections(text: str) -> "OrderedDict[str, List[dict]]":
    """{'FLOWSHEET GLOBAL': [ {'_kw': 'BLOCK', 'BLKID': 'ADS', 'IN': [...], ...}, ...], ...}"""
    toks = list(_tokens(text))
    sections: "OrderedDict[str, List[dict]]" = OrderedDict()
    i, n = 0, len(toks)
    cur = None
    rec = None
    while i < n:
        t = toks[i]
        if t == "?":
            j = i + 1
            head = []
            while j < n and toks[j] != "?":
                head.append(_unq(toks[j]))
                j += 1
            name = " ".join(head)
            k = 2
            while name in sections:
                name = f"{' '.join(head)} #{k}"
                k += 1
            cur = sections.setdefault(name, [])
            rec = None
            i = j + 1
            continue
        if t == ";":  # '; "UNITSET" ;'
            j = i + 1
            while j < n and toks[j] != ";":
                j += 1
            i = j + 1
            continue
        if t == "\\":
            rec = None
            i += 1
            continue
        if t == "/":  # entry separator inside a record (e.g. COMPONENTS CID=A ... / CID=B ...)
            if rec is not None and cur is not None:
                rec = OrderedDict(_kw=rec["_kw"])
                cur.append(rec)
            i += 1
            continue
        if cur is None:
            i += 1
            continue
        if rec is None:
            rec = OrderedDict(_kw=_unq(t))
            cur.append(rec)
            i += 1
            continue
        # KEY = VALUE  |  KEY = ( list )  |  bare word
        if i + 1 < n and toks[i + 1] == "=":
            key = _unq(t)
            j = i + 2
            if j < n and toks[j] == "(":
                vals, depth, j = [], 1, j + 1
                while j < n and depth:
                    if toks[j] == "(":
                        depth += 1
                    elif toks[j] == ")":
                        depth -= 1
                        if depth == 0:
                            break
                    if depth >= 1:
                        vals.append(_unq(toks[j]))
                    j += 1
                val = vals
                i = j + 1
            else:
                val = _unq(toks[j]) if j < n else ""
                i = j + 1
            if key in rec:  # repeated key inside one record: KEY#2, KEY#3, ...
                k2 = 2
                while f"{key}#{k2}" in rec:
                    k2 += 1
                key = f"{key}#{k2}"
            rec[key] = val
            continue
        rec.setdefault("_words", []).append(_unq(t))
        i += 1
    return sections


def parse(path) -> dict:
    text = read_text_any(Path(path))
    out = OrderedDict(file=str(path))
    m = re.match(r'\s*MM\s+"([\d.]+)".*?VERSION\s+"([\d.]+)"\s+DATETIME\s+"([^"]*)"', text)
    if m:
        out["engine"] = m.group(2)
        out["release"] = ENGINE_TO_RELEASE.get(m.group(2), "")
        out["saved"] = m.group(3)
    input_part = text.split(" GRAPHICS_BACKUP", 1)[0]
    k = input_part.find("\n? ")
    if k < 0:
        k = input_part.find("? SETUP")
    serial = input_part[k:].replace("\n", "") if k >= 0 else ""
    secs = parse_sections(serial)
    out["sections"] = list(secs.keys())
    # components
    comps = []
    for rec in secs.get("COMPONENTS MAIN", []):
        if rec["_kw"] == "COMPONENTS" and rec.get("CID"):
            comps.append({"id": rec["CID"], "alias": rec.get("ANAME", ""),
                          "databank_name": rec.get("DBNAME1", "")})
    out["components"] = comps
    # property method
    meths = []
    for rec in secs.get("PROPERTIES MAIN", []):
        for key in ("GOPSETNAME", "GBASEOPSET"):
            if rec.get(key) and rec[key] not in meths:
                meths.append(rec[key])
    out["property_methods"] = meths
    # blocks and connectivity
    blocks = OrderedDict()
    for rec in secs.get("FLOWSHEET GLOBAL", []):
        if rec["_kw"] == "BLOCK" and rec.get("BLKID"):
            ins = rec.get("IN", []) if isinstance(rec.get("IN"), list) else []
            outs = rec.get("OUT", []) if isinstance(rec.get("OUT"), list) else []
            blocks[rec["BLKID"]] = {"model": rec.get("MDLTYPE") or rec.get("BLKTYPE", ""),
                                    "in": _streams(ins), "out": _streams(outs)}
    for name in secs:
        mm = re.match(r"^BLOCK (\S+) (\S+)$", name)
        if mm and mm.group(2) not in blocks:
            blocks[mm.group(2)] = {"model": mm.group(1), "in": [], "out": []}
    out["blocks"] = blocks
    # flowsheet objects
    def names(prefix):
        return [s[len(prefix) + 1:] for s in secs if s.startswith(prefix + " ")]
    out["calculators"] = names("CALCULATOR")
    out["design_specs"] = names("DESIGN-SPEC")
    out["sensitivities"] = names("SENSITIVITY")
    out["optimizations"] = names("OPTIMIZATION")
    out["convergence_blocks"] = names("CONVERGENCE")
    out["streams_with_input"] = [s.split(" ", 2)[2] for s in secs if s.startswith("STREAM MATERIAL ")]
    out["fortran"] = OrderedDict()
    for kind in ("CALCULATOR", "DESIGN-SPEC", "SENSITIVITY"):
        for sname, recs in secs.items():
            if not sname.startswith(kind + " "):
                continue
            lines = []
            defines = []
            for rec in recs:
                if rec["_kw"] == "FORTRAN":
                    v = rec.get("FORTRAN-EXEC")
                    if isinstance(v, list):
                        lines += v
                if rec["_kw"] == "DEFINE" and rec.get("FVN"):
                    defines.append({"name": rec["FVN"], "type": rec.get("FVN-VARTYPE", "")})
            out["fortran"][f"{kind} {sname[len(kind) + 1:]}"] = {"defines": defines, "lines": lines}
    dis = []
    for rec in secs.get("DISABLE", []):
        lst = rec.get("LIST")
        if isinstance(lst, list):
            dis += [f"{rec['_kw']} {x}" for x in lst]
    out["disabled"] = dis
    tears = []
    for rec in secs.get("TEAR", []):
        if rec.get("SID"):
            tears += rec["SID"] if isinstance(rec["SID"], list) else [rec["SID"]]
    out["tears"] = tears
    out["conv_options"] = [" ".join(f"{k}={v}" for k, v in r.items() if not k.startswith("_"))
                           for r in secs.get("CONV-OPTIONS", [])]
    # run status (summary part)
    out["run"] = _run_status(text)
    return out


def _streams(lst: List[str]) -> List[str]:
    """IN = ( "FEED-MIX" M0-1 S2 M0-1 ) -> ['FEED-MIX', 'S2'] (drop port labels)."""
    return [x for x in lst if not re.match(r"^[A-Z]\d+-\d+$", x)]


def _run_status(text: str) -> dict:
    out = {}
    s = text.find("$_SUMMARY_FILE")
    if s < 0:
        return {"has_results": False}
    summ = text[s:]
    out["has_results"] = True
    m = re.search(r'DSET RUN-STATUS IT @IT \(\s*"([^"]*)"\s+"([^"]*)"', summ)
    if m:
        out["last_run"] = re.sub(r"\s+", " ", m.group(1)).strip()
        out["input_file"] = m.group(2)
    m = re.search(r'DSET RUN-STATUS VERS @VERS \(\s*"([^"]*)"\s+"([^"]*)"', summ)
    if m:  # only engine + platform; user and computer name are deliberately skipped
        out["run_engine"] = m.group(1)
        out["platform"] = m.group(2)
    msgs = []
    for mm in re.finditer(r"DSET RUN-STATUS ERRTXT @\S+ \((.*?)\n\s*\)\s*\n", summ, re.S):
        block = mm.group(1)
        lines = [re.sub(r"\\'", "'", x) for x in re.findall(r'"((?:[^"\\]|\\.)*)"', block)]
        msgs.append("\n".join(lines).strip())
    out["messages"] = msgs
    return out


def render_markdown(d: dict) -> str:
    L = [f"# Model summary: {Path(d['file']).name}"]
    L.append(f"- Saved by Aspen Plus {d.get('release') or '?'} (engine {d.get('engine', '?')}) on {d.get('saved', '?')}")
    run = d.get("run", {})
    if run.get("has_results"):
        L.append(f"- Contains results of a run on {run.get('last_run', '?')}")
    else:
        L.append("- No results stored (saved before running, or results removed)")
    L.append(f"- Property method(s): {', '.join(d['property_methods']) or '-'}")
    comps = ", ".join(c["id"] + (f" ({c['databank_name']})" if c["databank_name"] else "") for c in d["components"])
    L.append(f"- Components ({len(d['components'])}): {comps}")
    L.append("")
    L.append(f"## Blocks ({len(d['blocks'])})")
    L.append("| Block | Model | In -> Out |")
    L.append("|---|---|---|")
    for name, b in d["blocks"].items():
        L.append(f"| {name} | {b['model']} | {' '.join(b['in'])} -> {' '.join(b['out'])} |")
    L.append("")
    for label, key in (("Calculators", "calculators"), ("Design specs", "design_specs"),
                       ("Sensitivity", "sensitivities"), ("Optimization", "optimizations"),
                       ("User convergence blocks", "convergence_blocks"), ("Tears", "tears"),
                       ("Disabled", "disabled")):
        # streams_with_input is kept in the JSON only: the .bkp also stores result records for
        # product and intermediate streams, so the list is not reliable enough to print
        if d.get(key):
            L.append(f"- {label}: {', '.join(d[key])}")
    if d.get("conv_options"):
        L.append(f"- Convergence options: {' | '.join(d['conv_options'])}")
    for obj, f in d.get("fortran", {}).items():
        if f["lines"]:
            L.append(f"- {obj}: {len(f['defines'])} defined variables, {len(f['lines'])} Fortran lines")
    msgs = run.get("messages") or []
    if msgs:
        L.append("")
        L.append("## Stored run-status messages")
        for mtxt in msgs:
            L.append("```")
            L.append(mtxt[:3000])
            L.append("```")
    L.append("")
    L.append("Results tables are not decoded from .bkp; export a report (File > Export > Report Files *.rep) "
             "or read the .his for the run trace.")
    return "\n".join(L)
