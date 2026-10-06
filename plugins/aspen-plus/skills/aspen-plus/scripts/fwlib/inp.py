"""Read, extract and check Aspen Plus input files (.inp, the Aspen Plus input language).

An input file is a list of paragraphs: a keyword in column 1 (DATABANKS, COMPONENTS, PROPERTIES,
FLOWSHEET, STREAM, BLOCK, CALCULATOR, ...), statements indented under it, '&' at the end of a line
to continue it, ';' for comments, and inline Fortran on lines that start with 'F' in column 1.
Aspen Plus opens one with File > Open (Input Files *.inp) and its engine runs one directly
(`aspen <runid>`). Every .his file starts with the input of its run, so any run can be turned
back into an .inp.

check() lints a file before it is opened in Aspen Plus. It catches what makes a hand-written input
fail or silently mean something else: missing IN-UNITS (values then read in ENG units), blocks
without a BLOCK paragraph, streams with two sources, feeds without specifications, components that
were never declared, chemistry that no property method uses, unbalanced reactions, Fortran
column errors. It does not replace a run: Aspen Plus remains the judge of the input.
"""
from __future__ import annotations

import re
from collections import OrderedDict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from . import his
from .bkp import charge_of
from .common import BLOCK_MODELS, read_text_any

# Paragraph keywords seen in Aspen Plus V15 input files (input echoes of real runs and the
# help's input summaries) plus common ones; anything else is reported as a note, not an error.
KNOWN_PARAGRAPHS = {
    "TITLE", "IN-UNITS", "OUT-UNITS", "DEF-STREAMS", "DEF-STREAM-CLA", "DEF-SUBS-CLA", "DEF-SUBS-ATTR",
    "SIM-OPTIONS", "MODEL-OPTION", "RUN-CONTROL", "SYS-OPTIONS", "ACCOUNT-INFO", "DESCRIPTION", "DATABANKS",
    "PROP-SOURCES", "COMPONENTS", "CISOLID-COMPS", "NC-COMPS", "FORMULA", "HENRY-COMPS", "COMP-LIST",
    "COMP-GROUP", "ATTR-COMPS", "CHEMISTRY", "PROPERTIES", "PROP-REPLACE", "PROP-DATA", "PROP-SET", "ESTIMATE",
    "STRUCTURES", "NC-PROPS", "USER-PROPS", "MOLE-WT", "FLOWSHEET", "STREAM", "BLOCK", "CALCULATOR",
    "DESIGN-SPEC", "SENSITIVITY", "OPTIMIZATION", "CONSTRAINT", "CONVERGENCE", "CONV-OPTIONS", "TEAR",
    "SEQUENCE", "CONV-ORDER", "DISABLE", "STREAM-REPOR", "PROPERTY-REP", "REPORT", "BLOCK-REPORT",
    "REACTIONS", "PROP-TABLE", "SOLVE", "DYNAMICS", "EO-CONV-OPTI", "TRANSFER", "BALANCE", "PRES-RELIEF",
    "REGRESSION", "DATA", "DATA-SET", "STREAM-PRICE", "UTILITY", "POLYMERS", "BLOCK-OPTION", "EO-OPTIONS",
    "CASE-STUDY", "FORTRAN", "DEBUG", "SUMMARY", "STREAM-LIBR", "INIT-VAR-ATT", "MEASUREMENT",
}
ELECTROLYTE_METHODS = {"ELECNRTL", "ENRTL-RK", "ENRTL-SR", "ENRTL-HF", "ENRTL-HG", "PITZER", "PITZ-HG",
                       "B-PITZER", "OLI", "AQUEOUS", "ELEC-PR"}
SUBSTREAM_NAMES = {"MIXED", "CISOLID", "NC", "CIPSD", "NCPSD"}
STATE_KEYS = ("TEMP", "PRES", "VFRAC")
FLOW_SENTENCES = ("MOLE-FLOW", "MASS-FLOW", "STDVOL-FLOW", "VOLUME-FLOW")
FRAC_SENTENCES = ("MOLE-FRAC", "MASS-FRAC", "STDVOL-FRAC")

# Element symbols in upper case (Aspen aliases are upper case). Two-letter symbols are taken first
# only when the pair cannot also be read as two elements (CO is C+O, CS is C+S, HF is H+F ...).
_SINGLE = set("H B C N O F P S K V Y I W U".split())
_TWO = {"NA", "CL", "CA", "MG", "AL", "SI", "FE", "ZN", "CU", "BR", "LI", "MN", "BA", "SR", "NI", "CR", "PB", "TI",
        "AG", "AU", "HG", "ZR", "MO", "AR", "HE", "NE", "KR", "XE", "BE", "SE", "GE", "GA", "CD", "TE", "RB", "LA",
        "CE", "PT", "PD", "RH", "RU", "IR", "TA", "AS", "RA", "RN", "TH", "PA"}


def read(path) -> str:
    return read_text_any(Path(path))


# ---------------------------------------------------------------------------
# .his -> .inp
# ---------------------------------------------------------------------------
def from_his(d: dict, run_index: int = -1, source: str = "") -> str:
    """The input of a run as an .inp text (the echo, without line numbers)."""
    lines = [t for _, t in d["runs"][run_index]["echo"]]
    head = [f"; Input of run {len(d['runs']) if run_index == -1 else run_index + 1} of {d['n_runs']}"
            + (f" in {source}" if source else "") + ", extracted by proc-sim-agent"]
    return "\n".join(head + lines).rstrip() + "\n"


def input_text_of(path: Path) -> str:
    """Input-language text of an .inp, or of the last run in a .his (only the input echo is read)."""
    path = Path(path)
    if path.suffix.lower() == ".his":
        lines = read_text_any(path).split("\n")
        starts = [i for i, l in enumerate(lines) if "*** INPUT SUMMARY ***" in l] or [0]
        _, echo = his._parse_echo(lines, starts[-1], len(lines))
        return "\n".join(t for _, t in echo)
    return read(path)


# ---------------------------------------------------------------------------
# syntax examples from the user's own runs
# ---------------------------------------------------------------------------
def find_examples(paths: List[Path], keyword: str, limit: int = 3) -> List[dict]:
    """Paragraphs of real input files that show how `keyword` is written in this Aspen Plus release.

    keyword: a block model (RADFRAC -> 'BLOCK x RADFRAC' paragraphs), a paragraph keyword
    (DESIGN-SPEC, CHEMISTRY ...) or a statement keyword (COL-SPECS, TABULATE ...). One example per
    file, and examples that differ only in numbers count once."""
    kw = keyword.upper().strip()
    seen, out = set(), []
    for p in paths:
        try:
            text = input_text_of(p)
        except Exception:  # pragma: no cover - unreadable file
            continue
        raw, pars = _paragraphs_with_lines(text)
        for par in pars:
            toks = par["header"].split()
            if kw in BLOCK_MODELS:
                ok = par["key"] == "BLOCK" and len(toks) > 2 and toks[2].upper() == kw
            elif kw in KNOWN_PARAGRAPHS:
                ok = par["key"] == kw
            else:
                ok = any(s.split() and s.split()[0].upper() == kw for s in par["statements"])
            if not ok:
                continue
            body = "\n".join([raw[par["line"] - 1].rstrip()] + [l.rstrip() for l in par["lines"]])
            shape = re.sub(r"\s+", " ", re.sub(r"[-+]?\d+\.?\d*(?:[EeDd][-+]?\d+)?", "#", body))
            if shape in seen:
                continue
            seen.add(shape)
            out.append({"file": str(p), "line": par["line"], "text": body})
            break
        if len(out) >= limit:
            break
    return out


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _strip_units(s: str) -> str:
    return re.sub(r"<[^>]*>", " ", s)


def _entries(s: str) -> List[List[str]]:
    """'H2O -2. / H3O+ 1.' -> [['H2O','-2.'], ['H3O+','1.']]"""
    return [e.split() for e in _strip_units(s).split("/") if e.split()]


def _num(x: str) -> Optional[float]:
    try:
        return float(x.replace("D", "E").replace("d", "e"))
    except (ValueError, AttributeError):
        return None


def formula_elements(alias: str, cid: str = "") -> Optional[Dict[str, float]]:
    """Element counts of an upper-case Aspen alias (H2O, CO3-2, C6H15N-2, NACL, NA2CO3*10W).

    Returns None when the alias cannot be read safely (user components, odd notation)."""
    if not alias:
        return None
    a = alias.upper().strip()
    a = re.sub(r"\((S|L|G|AQ)\)$", "", a)
    if charge_of(cid or a):
        a = re.sub(r"(?:\+{1,3}|-{1,3}|[+-]\d)$", "", a)
    else:
        a = re.sub(r"-(?:\d+|[A-Z]\d*)$", "", a)  # isomer / databank suffix: C6H15N-2, C4H7NO-D2
    water = 0
    m = re.match(r"^(.*)\*(\d*)W$", a)  # hydrates
    if m:
        a, water = m.group(1), int(m.group(2) or 1)
    out: Dict[str, float] = {}
    i = 0
    while i < len(a):
        if a[i:i + 2] in _TWO:
            el, i = a[i:i + 2], i + 2
        elif a[i] in _SINGLE:
            el, i = a[i], i + 1
        else:
            return None
        j = i
        while j < len(a) and a[j].isdigit():
            j += 1
        out[el] = out.get(el, 0) + (int(a[i:j]) if j > i else 1)
        i = j
    if water:
        out["H"] = out.get("H", 0) + 2 * water
        out["O"] = out.get("O", 0) + water
    if any(v > 120 for v in out.values()):  # 'CNO999' is a name, not C N O999
        return None
    return out or None


class Finding:
    __slots__ = ("level", "line", "where", "msg")

    def __init__(self, level: str, line: int, where: str, msg: str):
        self.level, self.line, self.where, self.msg = level, line, where, msg

    def as_dict(self):
        return {"level": self.level, "line": self.line, "where": self.where, "message": self.msg}


# ---------------------------------------------------------------------------
# check
# ---------------------------------------------------------------------------
def _paragraphs_with_lines(text: str):
    """Paragraphs with the line number of their header (1-based)."""
    raw = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    pars, cur = [], None
    for n, t in enumerate(raw, 1):
        if not t.strip() or t.lstrip().startswith(";"):
            continue
        is_fortran = bool(his.FORTRAN_LINE.match(t))
        if not t[0].isspace() and not is_fortran:
            cur = {"key": t.split()[0].upper(), "header": t.strip(), "line": n, "lines": [], "line_nos": []}
            pars.append(cur)
        elif cur is not None:
            cur["lines"].append(t)
            cur["line_nos"].append(n)
    for p in pars:
        p["statements"] = his._statements(p["lines"])
        hdr = p["header"]
        if hdr.endswith("&") and p["statements"]:
            p["header"] = hdr[:-1].strip() + " " + p["statements"][0]
            p["statements"] = p["statements"][1:]
    return raw, pars


def check(text: str) -> dict:
    F: List[Finding] = []

    def add(level, line, where, msg):
        F.append(Finding(level, line, where, msg))

    raw, pars = _paragraphs_with_lines(text)

    # --- lexical ------------------------------------------------------------------------
    open_dq = 0  # line where a double-quoted text (e.g. a multi-line DESCRIPTION) was opened
    for n, t in enumerate(raw, 1):
        if t.lstrip().startswith(";") or his.FORTRAN_LINE.match(t):
            continue
        if len(t.rstrip()) > 80:
            add("warning", n, "", f"line is {len(t.rstrip())} characters long; keep input lines within 80 "
                                  "characters and continue with ' &'")
        if t.count('"') % 2:
            open_dq = 0 if open_dq else n
        elif not open_dq and '"' not in t and t.count("'") % 2:
            add("error", n, "", "unbalanced single quote")
    if open_dq:
        add("error", open_dq, "", "a double quote opened here is never closed")
    for p in pars:
        if p["lines"] and p["lines"][-1].rstrip().endswith("&"):
            add("error", p["line_nos"][-1], p["header"], "the paragraph ends with '&' (continuation of nothing)")
        for s in [p["header"]] + p["statements"]:
            if his.FORTRAN_LINE.match(s):
                continue
            body = re.sub(r"'[^']*'|\"[^\"]*\"", "", s)
            if body.count("(") != body.count(")"):
                add("warning", p["line"], p["header"], f"unbalanced parentheses in: {s[:60]}")

    keys = [p["key"] for p in pars]
    for p in pars:
        if p["key"] not in KNOWN_PARAGRAPHS:
            add("note", p["line"], p["header"], f"'{p['key']}' is not a paragraph keyword this checker knows - "
                                                "check the spelling (a statement may need indenting)")

    # --- model ----------------------------------------------------------------------------
    model = his.parse_input_language([l for l in text.replace("\r\n", "\n").split("\n")])
    line_of = {}
    for p in pars:
        line_of.setdefault((p["key"], (p["header"].split() + ["", ""])[1]), p["line"])

    def L(key, name=""):
        return line_of.get((key, name), line_of.get((key, ""), 0))

    if "IN-UNITS" not in keys:
        add("warning", 0, "IN-UNITS", "no IN-UNITS paragraph: Aspen Plus then reads every number in ENG units "
                                      "(F, psia, lb/hr). Add e.g. 'IN-UNITS MET PRESSURE=bar TEMPERATURE=C'")
    if "COMPONENTS" not in keys:
        add("error", 0, "COMPONENTS", "no COMPONENTS paragraph")
    if "PROPERTIES" not in keys:
        add("error", 0, "PROPERTIES", "no PROPERTIES paragraph (global property method)")
    if "DATABANKS" not in keys and "COMPONENTS" in keys:
        add("note", 0, "DATABANKS", "no DATABANKS paragraph: the default databanks of this Aspen Plus version are "
                                    "used")
    # Databank names carry the release ('APV150 PURE41' is V15): another release does not know them.
    for p in pars:
        if p["key"] in ("DATABANKS", "PROP-SOURCES"):
            tags = sorted(set(re.findall(r"'[A-Z]*V(\d{3})\s", " ".join([p["header"]] + p["statements"]))))
            if len(tags) > 1:
                add("warning", p["line"], p["key"], "databanks of different releases: "
                    + ", ".join(_release(t) for t in tags))
            elif tags and p["key"] == "DATABANKS":
                add("note", p["line"], p["key"], f"databank names are those of Aspen Plus {_release(tags[0])}; for "
                    "another release copy DATABANKS and PROP-SOURCES from a run of that release "
                    "(fw.py his <file> --echo)")

    comps = OrderedDict((c["id"].upper(), dict(c)) for c in model["components"])
    for extra in model.get("solids", []) + model.get("nc_components", []):
        comps.setdefault(extra.upper(), {"id": extra, "databank_name": ""})
    for p in pars:  # user-defined components (FORMULA paragraph): their 'formula' is only a name
        if p["key"] == "FORMULA":
            for e in _entries(" ".join([p["header"][len("FORMULA"):]] + p["statements"])):
                if e and e[0].upper() in comps:
                    comps[e[0].upper()]["databank_name"] = ""

    def need_comp(cid, line, where):
        if cid.upper() not in comps and cid.upper() not in SUBSTREAM_NAMES:
            add("error", line, where, f"component {cid} is not declared in COMPONENTS")

    # HENRY-COMPS and DEF-STREAMS
    henry_sets: Dict[str, List[str]] = {}
    heat_work = set()
    for p in pars:
        toks = p["header"].split()
        if p["key"] == "HENRY-COMPS" and len(toks) > 1:
            ids = toks[2:] + " ".join(p["statements"]).split()
            henry_sets[toks[1].upper()] = ids
            for c in ids:
                need_comp(c, p["line"], p["header"])
        if p["key"] == "DEF-STREAMS" and len(toks) > 2 and toks[1].upper() in ("HEAT", "WORK", "LOAD"):
            heat_work.update(t.upper() for t in toks[2:] + " ".join(p["statements"]).split())

    # PROPERTIES statements
    prop_stmts = []
    for p in pars:
        if p["key"] == "PROPERTIES":
            prop_stmts.append((p["line"], p["header"][len("PROPERTIES"):].strip()))
            for s in p["statements"]:
                if s.upper().startswith("PROPERTIES"):
                    prop_stmts.append((p["line"], s[len("PROPERTIES"):].strip()))
        if p["key"] == "BLOCK":
            for s in p["statements"]:
                if s.upper().startswith("PROPERTIES"):
                    prop_stmts.append((p["line"], s[len("PROPERTIES"):].strip()))
    used_chem, methods_used, true_comps = set(), set(), []
    for line, s in prop_stmts:
        kv = his._kv(s)
        for part in s.split("/"):
            w = part.split()
            if w and "=" not in w[0]:
                methods_used.add(w[0].upper())
        if "CHEMISTRY" in kv:
            used_chem.add(kv["CHEMISTRY"].upper())
        if "HENRY-COMPS" in kv and kv["HENRY-COMPS"].upper() not in henry_sets:
            add("error", line, "PROPERTIES", f"HENRY-COMPS={kv['HENRY-COMPS']} but there is no "
                                             f"'HENRY-COMPS {kv['HENRY-COMPS']}' paragraph")
        if "TRUE-COMPS" in kv:
            true_comps.append((line, kv["TRUE-COMPS"].upper(), kv.get("CHEMISTRY", "").upper()))

    # CHEMISTRY and reaction balances
    chem_ids = []
    for p in pars:
        toks = p["header"].split()
        if p["key"] == "CHEMISTRY":
            cid = toks[1].upper() if len(toks) > 1 else "GLOBAL"
            chem_ids.append(cid)
            participants = set()
            for s in p["statements"]:
                w = s.split()
                if not w:
                    continue
                kw = w[0].upper()
                if kw == "STOIC" and len(w) > 2:
                    ent = _entries(s[len(w[0]):].split(None, 1)[1] if len(s.split(None, 2)) > 2 else "")
                    _balance(ent, comps, add, p["line"], f"CHEMISTRY {cid} STOIC {w[1]}", need_comp)
                    participants.update(e[0].upper() for e in ent)
                elif kw in ("DISS", "SALT") and len(w) > 2:
                    elec = w[1]
                    ent = _entries(s.split(None, 2)[2])
                    _balance([[elec, "-1"]] + ent, comps, add, p["line"], f"CHEMISTRY {cid} {kw} {elec}", need_comp)
                    participants.update(e[0].upper() for e in ent)
                    participants.add(elec.upper())
            if cid not in used_chem:
                add("warning", p["line"], p["header"],
                    f"chemistry {cid} is defined but no PROPERTIES statement uses it (add CHEMISTRY={cid}); "
                    "without it the electrolyte reactions are ignored")
            hen = set(c.upper() for ids in henry_sets.values() for c in ids)
            volatile = sorted(participants & hen)
            for line, tc, ch in true_comps:
                if tc == "NO" and (ch == cid or not ch) and volatile:
                    add("warning", line, "PROPERTIES",
                        f"apparent-component approach (TRUE-COMPS=NO) while chemistry {cid} produces volatile "
                        f"species ({', '.join(volatile)}). Aspen Plus help: when apparent components yield volatile "
                        "reaction products, always use the true component approach (TRUE-COMPS=YES)")
        if p["key"] == "REACTIONS" and len(toks) > 1:
            for s in p["statements"]:
                w = s.split()
                if w and w[0].upper() == "STOIC" and len(w) > 2:
                    rest = s.split(None, 2)[2]
                    rw = rest.split()
                    if rw and rw[0].upper() in SUBSTREAM_NAMES:
                        rest = rest.split(None, 1)[1] if len(rw) > 1 else ""
                    _balance(_entries(rest), comps, add, p["line"], f"REACTIONS {toks[1]} STOIC {w[1]}", need_comp)
    ions = [c for c in comps if charge_of(c)]
    if ions and not chem_ids:
        add("warning", L("COMPONENTS"), "COMPONENTS", f"ionic components ({', '.join(ions[:6])}) but no CHEMISTRY "
                                                      "paragraph: ions then never form")
    if chem_ids and not (methods_used & ELECTROLYTE_METHODS):
        add("note", L("PROPERTIES"), "PROPERTIES", "CHEMISTRY is defined but no electrolyte property method "
                                                   "(ELECNRTL, ENRTL-RK, PITZER ...) is used")

    # FLOWSHEET connectivity
    conns = model["connections"]
    src: Dict[str, List[str]] = {}
    dst: Dict[str, List[str]] = {}
    for b, c in conns.items():
        for s in c["out"]:
            src.setdefault(s.upper(), []).append(b)
        for s in c["in"]:
            dst.setdefault(s.upper(), []).append(b)
    for s, bs in src.items():
        if len(bs) > 1:
            add("error", L("FLOWSHEET"), "FLOWSHEET", f"stream {s} leaves more than one block ({', '.join(bs)})")
    for s, bs in dst.items():
        if len(bs) > 1:
            add("error", L("FLOWSHEET"), "FLOWSHEET", f"stream {s} enters more than one block ({', '.join(bs)})")
    blocks = model["blocks"]
    for b in conns:
        if b not in blocks:
            add("error", L("FLOWSHEET"), "FLOWSHEET", f"block {b} is in FLOWSHEET but has no 'BLOCK {b} <model>' "
                                                      "paragraph")
    for b, info in blocks.items():
        line = L("BLOCK", b)
        if b not in conns:
            add("error", line, f"BLOCK {b}", f"block {b} is not connected in the FLOWSHEET paragraph")
        mdl = (info.get("model") or "").upper()
        if not mdl:
            add("error", line, f"BLOCK {b}", "the BLOCK line needs the model after the block ID (e.g. BLOCK B1 FLASH2)")
        elif mdl not in BLOCK_MODELS:
            add("warning", line, f"BLOCK {b}", f"unknown unit-operation model '{info['model']}'")
        _check_block(b, mdl, info.get("statements", []), conns.get(b), comps, add, line, need_comp, heat_work)
    streams = model["streams"]
    for s in sorted(set(dst) - set(src)):
        if s in heat_work:
            continue
        if s not in {k.upper() for k in streams}:
            add("error", L("FLOWSHEET"), "FLOWSHEET", f"feed stream {s} has no STREAM paragraph (conditions and flow)")
    for sname, sd in streams.items():
        line = L("STREAM", sname)
        u = sname.upper()
        if u not in src and u not in dst:
            add("warning", line, f"STREAM {sname}", f"stream {sname} is specified but not connected to any block")
        _check_stream(sname, sd, comps, add, line, need_comp, is_feed=(u in dst and u not in src))

    # Fortran objects
    for kind, objs in (("CALCULATOR", model["calculators"]), ("DESIGN-SPEC", model["design_specs"]),
                       ("SENSITIVITY", model["sensitivities"])):
        for name, obj in objs.items():
            line = L(kind, name)
            for issue in his.fortran_lint(obj):
                add("warning", line, f"{kind} {name}", issue)
            if kind == "DESIGN-SPEC":
                for part, label in ((obj["spec"], "SPEC"), (obj["tol"], "TOL-SPEC"), (obj["vary"], "VARY"),
                                    (obj["limits"], "LIMITS")):
                    if not part:
                        add("error", line, f"{kind} {name}", f"missing {label} statement")
            if kind == "SENSITIVITY":
                if not obj["vary"]:
                    add("error", line, f"{kind} {name}", "missing VARY statement")
                if not obj["range"]:
                    add("error", line, f"{kind} {name}", "missing RANGE statement")
                if not obj["tabulate"]:
                    add("warning", line, f"{kind} {name}", "nothing is tabulated (TABULATE)")
            for dfn in obj["defines"]:
                for cm in re.findall(r"COMPONENT=(\S+)", dfn["detail"]):
                    need_comp(cm, line, f"{kind} {name}")
            if kind == "CALCULATOR":
                defined = {dfn["name"].upper() for dfn in obj["defines"]}
                for v in obj["write_vars"] + obj["read_vars"]:
                    if v.upper() not in defined:
                        add("error", line, f"{kind} {name}", f"{v} is listed in READ-VARS/WRITE-VARS but not "
                                                             "DEFINEd")
    # DISABLE references
    names_by_kind = {"BLOCK": set(blocks), "CALCULATOR": set(model["calculators"]),
                     "DESIGN-SPEC": set(model["design_specs"]), "SENSITIVITY": set(model["sensitivities"]),
                     "CONVERGENCE": set(model["convergence"])}
    for d in model["disabled"]:
        w = d.split()
        if len(w) == 2 and w[0] in names_by_kind and w[1] not in names_by_kind[w[0]]:
            add("error", L("DISABLE"), "DISABLE", f"DISABLE names {d}, which does not exist")

    order = {"error": 0, "warning": 1, "note": 2}
    seen = set()
    F = [f for f in F if not ((f.level, f.line, f.msg) in seen or seen.add((f.level, f.line, f.msg)))]
    F.sort(key=lambda f: (order[f.level], f.line))
    summary = {
        "components": len(comps), "ions": ions, "property_methods": model["property_methods"],
        "chemistry": chem_ids, "henry_sets": henry_sets,
        "blocks": {b: (blocks.get(b, {}).get("model") or "?") for b in list(conns) + [x for x in blocks if x not in conns]},
        "feeds": sorted(set(dst) - set(src) - heat_work), "products": sorted(set(src) - set(dst)),
        "calculators": list(model["calculators"]), "design_specs": list(model["design_specs"]),
        "sensitivities": list(model["sensitivities"]), "in_units": model.get("in_units", ""),
    }
    return {"findings": [f.as_dict() for f in F], "summary": summary,
            "counts": {k: sum(1 for f in F if f.level == k) for k in ("error", "warning", "note")}}


def _release(code: str) -> str:
    """'150' -> 'V15', '121' -> 'V12.1' (databank name tags, e.g. 'APV150 PURE41')."""
    return f"V{int(code[:2])}" + (f".{code[2]}" if code[2] != "0" else "")


def _balance(entries, comps, add, line, where, need_comp):
    coefs: List[Tuple[str, float]] = []
    for e in entries:
        if len(e) < 2:
            add("error", line, where, f"entry '{' '.join(e)}' needs a component and a coefficient")
            continue
        need_comp(e[0], line, where)
        v = _num(e[1])
        if v is None:
            add("error", line, where, f"coefficient '{e[1]}' of {e[0]} is not a number")
            continue
        coefs.append((e[0], v))
    if not coefs:
        return
    q = sum(v * charge_of(c) for c, v in coefs)
    if abs(q) > 1e-9:
        add("error", line, where, f"not charge-balanced (net charge {q:+g})")
    elems: Dict[str, float] = {}
    for c, v in coefs:
        info = comps.get(c.upper())
        alias = (info or {}).get("databank_name", "") if info else ""
        fe = formula_elements(alias, c) if alias else None
        if fe is None:
            return  # a component without a readable formula: no element check
        for el, n in fe.items():
            elems[el] = elems.get(el, 0) + v * n
    off = {el: round(n, 6) for el, n in elems.items() if abs(n) > 1e-6}
    if off:
        add("warning", line, where, "elements do not balance (formulas read from the component aliases): "
            + ", ".join(f"{el} {n:+g}" for el, n in off.items()))


def _check_stream(name, sd, comps, add, line, need_comp, is_feed):
    subs = sd.get("substreams") or []
    if not subs:
        if is_feed:
            add("error", line, f"STREAM {name}", "no SUBSTREAM statement (e.g. SUBSTREAM MIXED TEMP=25 PRES=1)")
        return
    for sub in subs:
        if sub.get("name", "").upper() != "MIXED":
            continue
        state = [k for k in STATE_KEYS if k in sub]
        if is_feed and len(state) != 2:
            add("error", line, f"STREAM {name}", f"give exactly two of TEMP, PRES, VFRAC (found: "
                                                 f"{', '.join(state) or 'none'})")
    flows = [c for c in sd.get("composition", []) if c["basis"] in FLOW_SENTENCES]
    fracs = [c for c in sd.get("composition", []) if c["basis"] in FRAC_SENTENCES]
    total = any(k in sub for sub in subs for k in FLOW_SENTENCES)
    if is_feed and not flows and not (fracs and total):
        add("error", line, f"STREAM {name}", "no flow: give component flows (MOLE-FLOW H2O 10 / ...) or a total "
                                             "flow on SUBSTREAM plus fractions (MOLE-FRAC ...)")
    if fracs and not total and is_feed:
        add("error", line, f"STREAM {name}", "fractions given without a total flow on the SUBSTREAM statement")
    for c in sd.get("composition", []):
        tot = 0.0
        for cid, val in c["values"]:
            need_comp(cid, line, f"STREAM {name}")
            v = _num(val)
            if v is None:
                add("error", line, f"STREAM {name}", f"value '{val}' for {cid} is not a number")
            else:
                tot += v
                if v < 0:
                    add("error", line, f"STREAM {name}", f"negative {c['basis']} for {cid}")
        if c["basis"] in FRAC_SENTENCES and c["values"] and abs(tot - 1.0) > 0.01:
            add("note", line, f"STREAM {name}", f"{c['basis']} values add up to {tot:g} (Aspen Plus normalises them)")


def _check_block(b, mdl, statements, conn, comps, add, line, need_comp, heat_work=()):
    where = f"BLOCK {b}"
    param = {}
    for s in statements:
        if s.upper().startswith("PARAM"):
            param.update(his._kv(s))
    if mdl in ("FLASH2", "FLASH3"):
        specs = [k for k in ("TEMP", "PRES", "VFRAC", "DUTY") if k in param]
        if len(specs) != 2:
            add("error", line, where, f"{BLOCK_MODELS[mdl]} needs exactly two of TEMP, PRES, VFRAC, DUTY "
                                      f"(found: {', '.join(specs) or 'none'})")
    elif mdl == "HEATER":
        specs = [k for k in ("TEMP", "PRES", "VFRAC", "DUTY", "DELT", "DEGSUB", "DEGSUP") if k in param]
        if len(specs) < 2:
            add("error", line, where, f"Heater needs two specifications among TEMP/DELT/DEGSUB/DEGSUP, PRES, VFRAC, "
                                      f"DUTY (found: {', '.join(specs) or 'none'}; PRES=0 means no pressure drop)")
    elif mdl in ("PUMP", "COMPR", "MCOMPR"):
        if not any(k in param for k in ("PRES", "DELP", "PRATIO", "POWER", "NSTAGE")):
            add("error", line, where, f"{BLOCK_MODELS[mdl]} needs an outlet specification (PRES, DELP, PRATIO or POWER)")
        if mdl == "COMPR" and "TYPE" not in param:
            add("error", line, where, "Compr needs TYPE (e.g. TYPE=ISENTROPIC)")
    elif mdl == "VALVE":
        if not any(k in param for k in ("P-OUT", "P-DROP", "FLO-COEF", "VAL-POSN")):
            add("error", line, where, "Valve needs P-OUT or P-DROP (or a valve-sizing specification)")
    elif mdl == "RSTOIC":
        if not any(s.upper().startswith("STOIC") for s in statements):
            add("error", line, where, "RStoic needs at least one STOIC statement")
        nst = {s.split()[1] for s in statements if s.upper().startswith("STOIC") and len(s.split()) > 1}
        nconv = {s.split()[1] for s in statements if s.upper().startswith(("CONV", "EXTENT")) and len(s.split()) > 1}
        for r in sorted(nst - nconv):
            add("error", line, where, f"reaction {r} has no CONV or EXTENT statement")
        for s in statements:
            if s.upper().startswith("STOIC"):
                w = s.split(None, 3)
                if len(w) >= 4:
                    _balance(_entries(w[3]), comps, add, line, f"{where} STOIC {w[1]}", need_comp)
    elif mdl == "RADFRAC":
        if "NSTAGE" not in param:
            add("error", line, where, "RadFrac needs NSTAGE on the PARAM statement")
        listed = set()
        for s in statements:
            w = s.split()
            if w and w[0].upper() in ("FEEDS", "PRODUCTS"):
                for e in _entries(s[len(w[0]):]):
                    listed.add(e[0].upper())
        if conn:
            for st in conn["in"] + conn["out"]:
                if st.upper() not in listed and st.upper() not in heat_work:
                    add("error", line, where, f"stream {st} is connected but missing from FEEDS/PRODUCTS")
        config = {}
        for s in statements:
            if s.upper().startswith("COL-CONFIG"):
                config.update(re.findall(r"([A-Z-]+)=([A-Z0-9-]+)", s.upper()))
        # one operating specification per condenser and per reboiler (an absorber has neither)
        needed = (config.get("CONDENSER", "TOTAL") != "NONE") + (config.get("REBOILER", "KETTLE") != "NONE")
        if needed and not any(s.upper().startswith("COL-SPECS") for s in statements):
            add("warning", line, where, f"no COL-SPECS statement (this configuration needs {needed} operating "
                                        "specification" + ("s)" if needed > 1 else ")"))
    elif mdl == "FSPLIT" and conn:
        nspec = sum(1 for s in statements if s.split() and s.split()[0].upper() in
                    ("FRAC", "MOLE-FLOW", "MASS-FLOW", "STDVOL-FLOW", "VOLUME-FLOW", "LIMIT-FLOW", "ACT-VOL-FLOW"))
        if nspec < len(conn["out"]) - 1:
            add("error", line, where, f"FSplit with {len(conn['out'])} outlets needs {len(conn['out']) - 1} "
                                      f"split specifications (found {nspec})")


def render(res: dict, path: str = "") -> str:
    s = res["summary"]
    c = res["counts"]
    L = [f"# Input check{': ' + Path(path).name if path else ''}",
         f"{c['error']} errors, {c['warning']} warnings, {c['note']} notes"]
    L.append(f"- Units: IN-UNITS {s['in_units'] or '(none: ENG)'}")
    L.append(f"- {s['components']} components" + (f", ions: {' '.join(s['ions'])}" if s["ions"] else ""))
    L.append(f"- Property method: {' | '.join(s['property_methods']) or '-'}"
             + (f"; chemistry: {', '.join(s['chemistry'])}" if s["chemistry"] else ""))
    if s["henry_sets"]:
        L.append("- Henry components: " + "; ".join(f"{k}: {' '.join(v)}" for k, v in s["henry_sets"].items()))
    L.append("- Blocks: " + (", ".join(f"{b} ({m})" for b, m in s["blocks"].items()) or "-"))
    L.append(f"- Feeds: {' '.join(s['feeds']) or '-'} | products: {' '.join(s['products']) or '-'}")
    for label, key in (("Calculators", "calculators"), ("Design specs", "design_specs"),
                       ("Sensitivity", "sensitivities")):
        if s[key]:
            L.append(f"- {label}: {', '.join(s[key])}")
    if res["findings"]:
        L.append("")
        for f in res["findings"]:
            loc = f"line {f['line']}" if f["line"] else ""
            where = f" [{f['where']}]" if f["where"] else ""
            L.append(f"- {f['level'].upper()}{(' ' + loc) if loc else ''}{where}: {f['message']}")
    else:
        L.append("\nNo problems found. Open it in Aspen Plus (File > Open > Input Files *.inp) and run it; the run "
                 "decides the rest.")
    return "\n".join(L)
