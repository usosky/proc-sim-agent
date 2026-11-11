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

from .common import BLOCK_MODELS, ENGINE_TO_RELEASE, read_text_any

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


# Objects hidden with Hide/Reveal (a calculation sequence, design specs, convergence blocks ...)
# are stored in front of the input tree as buffers:
#   '? HIDE_BUFFER "DESIGN-SPEC" ? PASTE_ITEMS ? 2 ... \@? "DESIGN-SPEC" X ? ... \@END_HIDEBUF'
#   '? HIDE_BUFFER CONVERGENCE ? PASTE_ITEMS ? 1 ... \ END_HIDEBUF'   (no '@' before the end)
# Their unpaired '?' marks would shift every later section header, so they are cut out first.
_HIDE_RX = re.compile(r"\?\s*HIDE_BUFFER\b.*?END_HIDEBUF", re.S)
_HIDDEN_KIND_RX = re.compile(r'\?\s*HIDE_BUFFER\s+("[^"]*"|[^\s?]+)')
# Ionic component IDs end in a charge: NA+, CL-, CO3-2, CO3--, H3O+, DGAH+ (not N-MET-02).
ION_RX = re.compile(r"(?:\+{1,3}|-{1,3}|[+-][1-9])$")


def charge_of(cid: str) -> int:
    """Charge encoded at the end of a component ID (0 when it does not look like an ion)."""
    m = ION_RX.search(cid or "")
    if not m:
        return 0
    s = m.group(0)
    if s[-1].isdigit():
        return int(s[-1]) * (1 if s[0] == "+" else -1)
    return len(s) * (1 if s[0] == "+" else -1)


def decode(raw: bytes) -> str:
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return raw.decode(enc).replace("\r\n", "\n").replace("\r", "\n")
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1", errors="replace")


def parse(path) -> dict:
    return parse_text(read_text_any(Path(path)), str(path))


def parse_text(text: str, name: str = "") -> dict:
    out = OrderedDict(file=name)
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
    # kinds of objects hidden with Hide/Reveal: kept in the file, but not part of the problem
    out["hidden"] = list(OrderedDict.fromkeys(_unq(m.group(1)) for m in _HIDDEN_KIND_RX.finditer(serial)))
    serial = _HIDE_RX.sub(" ", serial)
    secs = parse_sections(serial)
    out["sections"] = list(secs.keys())
    out["user_sequence"] = any(s == "SEQUENCE" or s.startswith("SEQUENCE ") for s in secs)
    run_class = ""
    for rec in secs.get("SETUP MAIN", []):
        if rec.get("RUN-CLASS"):
            run_class = rec["RUN-CLASS"]
    out["run_class"] = run_class
    desc = []
    for rec in secs.get("SETUP DESCRIPTION", []):
        v = rec.get("DESCRIP")
        desc += v if isinstance(v, list) else ([v] if v else [])
    out["description"] = re.sub(r"\s+", " ", " ".join(desc)).strip()
    # components
    comps = []
    for rec in secs.get("COMPONENTS MAIN", []):
        if rec["_kw"] == "COMPONENTS" and rec.get("CID"):
            comps.append({"id": rec["CID"], "alias": rec.get("ANAME", ""),
                          "databank_name": rec.get("DBNAME1", ""), "type": rec.get("TYPE", "")})
    out["components"] = comps
    out["ions"] = [c["id"] for c in comps if charge_of(c["id"])]
    henry = OrderedDict()
    for sname, recs in secs.items():
        if sname.startswith("COMPONENTS HENRY-COMPS"):
            hid = sname[len("COMPONENTS HENRY-COMPS"):].strip() or "GLOBAL"
            for rec in recs:
                v = rec.get("CID")
                henry.setdefault(hid, []).extend(v if isinstance(v, list) else ([v] if v else []))
    out["henry"] = henry
    # property method and electrolyte options
    meths, popts = [], OrderedDict()
    # global method first, then those of hierarchy blocks ('PROPERTIES C2HIER.MAIN')
    prop_secs = ["PROPERTIES MAIN"] + [k for k in secs if k.startswith("PROPERTIES ") and k.endswith(".MAIN")]
    for sname in prop_secs:
        for rec in secs.get(sname, []):
            for key in ("GOPSETNAME", "GBASEOPSET"):
                if rec.get(key) and rec[key] not in meths:
                    meths.append(rec[key])
            if sname != "PROPERTIES MAIN":
                continue
            for key, label in (("GCHEMISTRY", "chemistry"), ("GHEN", "henry"), ("GTRUE-COMPS", "true_comps"),
                               ("GFREE-WATER", "free_water")):
                if rec.get(key):
                    popts[label] = rec[key]
    out["property_methods"] = meths
    out["property_options"] = popts
    chem = OrderedDict()
    for sname, recs in secs.items():
        if sname.startswith("CHEMISTRY "):
            cid = sname[len("CHEMISTRY "):].strip()
            reac = {r.get("REACNO") for r in recs if r["_kw"] == "STOIC" and r.get("REACNO")}
            chem[cid] = {"equilibria": len(reac),
                         "dissociations": len({r.get("ELECID") for r in recs if r["_kw"] == "DISS"}),
                         "salts": len({r.get("SALTID") for r in recs if r["_kw"] == "SALT"})}
    out["chemistry"] = chem
    out["reactions"] = [s[len("REACTIONS "):] for s in secs if s.startswith("REACTIONS ")]
    # blocks and connectivity (main flowsheet, flowsheet sections and hierarchy blocks)
    blocks = OrderedDict()
    for sname, recs in secs.items():
        if not sname.startswith("FLOWSHEET "):
            continue
        fs = sname[len("FLOWSHEET "):].strip()
        hier = fs[: -len(".GLOBAL")] if fs.upper().endswith(".GLOBAL") else ""
        section = "" if (fs.upper() == "GLOBAL" or hier) else fs
        for rec in recs:
            if rec["_kw"] == "BLOCK" and rec.get("BLKID"):
                ins = rec.get("IN", []) if isinstance(rec.get("IN"), list) else []
                outs = rec.get("OUT", []) if isinstance(rec.get("OUT"), list) else []
                bid = (hier + "." if hier else "") + rec["BLKID"]
                btype = (rec.get("BLKTYPE") or rec.get("MDLTYPE") or "").upper()
                blocks[bid] = {"model": rec.get("MDLTYPE") or BLOCK_MODELS.get(btype, rec.get("BLKTYPE", "")),
                               "type": btype,
                               "in": _streams(ins), "out": _streams(outs), "section": section,
                               "hierarchy": hier}
    for sname in secs:
        mm = re.match(r"^BLOCK (\S+) (\S+)$", sname)
        if mm and mm.group(2) not in blocks:
            bid = mm.group(2)
            btype = mm.group(1).upper()
            blocks[bid] = {"model": BLOCK_MODELS.get(btype, mm.group(1)), "type": btype, "in": [], "out": [],
                           "section": "", "hierarchy": bid.rsplit(".", 1)[0] if "." in bid else ""}
    out["blocks"] = blocks
    subs = set()
    for sname, recs in secs.items():
        if sname.startswith("STREAM MATERIAL "):
            subs.update(r.get("SSID", "") for r in recs if r["_kw"] == "SUBSTREAM")
    out["substreams"] = sorted(s for s in subs if s)
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
    if d.get("run_class") and d["run_class"].upper() != "FLOWSHEET":
        L.append(f"- Run type: {d['run_class']} (no flowsheet calculation)")
    if d.get("description"):
        L.append(f"- Description: {d['description'][:400]}")
    po = d.get("property_options") or {}
    extra = []
    if po.get("chemistry"):
        extra.append(f"chemistry {po['chemistry']}")
    if po.get("henry"):
        extra.append(f"Henry components {po['henry']}")
    if po.get("true_comps"):
        extra.append("true-component approach" if po["true_comps"].upper() == "YES" else "apparent-component approach")
    L.append(f"- Property method(s): {', '.join(d['property_methods']) or '-'}"
             + (f" ({', '.join(extra)})" if extra else ""))
    comps = ", ".join(c["id"] + (f" ({c['databank_name']})" if c["databank_name"] else "") for c in d["components"])
    L.append(f"- Components ({len(d['components'])}): {comps}")
    for cid, c in (d.get("chemistry") or {}).items():
        L.append(f"- Chemistry {cid}: {c['equilibria']} equilibria, {c['dissociations']} complete dissociations, "
                 f"{c['salts']} salts")
    for hid, comps_ in (d.get("henry") or {}).items():
        L.append(f"- Henry components {hid}: {' '.join(comps_)}")
    if d.get("reactions"):
        L.append(f"- Reaction sets: {', '.join(d['reactions'])}")
    if d.get("substreams") and set(d["substreams"]) - {"MIXED"}:
        L.append(f"- Substreams: {', '.join(d['substreams'])}")
    if d.get("user_sequence"):
        L.append("- A user-defined calculation sequence is specified")
    if d.get("hidden"):
        L.append(f"- Hidden objects (Hide/Reveal; not part of the calculation): {', '.join(d['hidden'])}")
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
