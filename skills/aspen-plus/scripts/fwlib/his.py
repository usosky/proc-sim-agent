"""Digest an Aspen Plus history file (.his).

A .his file holds, per run: the input echo (the full input-language file, numbered),
input-translator messages, flowsheet analysis (tears, computation order), the
calculation trace (block by block, convergence loops, simulation messages) and a
summary of errors. This module turns that into a compact model + run summary.

Privacy: the "THIS COPY ... LICENSED TO" line and the installation path are never
reported, and a directory on the ';Directory' line of the echo is redacted.
"""
from __future__ import annotations

import difflib
import re
from collections import OrderedDict
from pathlib import Path
from typing import Dict, List, Optional

from .common import ENGINE_TO_RELEASE, fmt_num, read_text_any

ID_RX = re.compile(r"\(([A-Z][A-Z0-9$]*\.[0-9]+[A-Z]?)\)")
HEAD_RX = re.compile(r"^\s{1,10}(\*{1,4}\s+)?(TERMINAL ERROR|SEVERE ERROR|ERROR|WARNING|INFORMATION)\b(.*)$")
ECHO_RX = re.compile(r"^\s*(\d+)(?: {4}(.*))?$")
TRACE_RX = re.compile(
    r"^\s+(KODE|KPHASE|UOS BLOCK|CONVERGENCE BLOCK|CALCULATOR BLOCK|ENTHALPY CALCULATION|GENERATING RESULTS|"
    r"--FLASH|OUTLET TEMP|ISENTR TEMP|SPECIFICATION:|FLOW TYPE:|HOT:|COLD:|AREA=|DUTY=|BEGIN |END |ITER |"
    r"LOOP |STREAM \S+ WILL BE FLASHED|SENSITIVITY BLOCK|DESIGN-SPEC|TIME =|NO\. TEMP ITER)")
KV_RX = re.compile(r"([A-Z](?:[A-Z .]*?[A-Z])?)\s*=\s*([-+]?(?:\d+\.?\d*|\.\d+)(?:[EeDd][-+]?\d+)?)")
LOOP_RX = re.compile(r"^\s*LOOP\s+(\S+)\s+ITER\s+(\d+):\s*(.*?)\s*,?\s*MAX ERR/TOL\s+([-+0-9.E]+)")
FORTRAN_LINE = re.compile(r"^[FC](\s|$)")  # 'F' statement / 'C' comment lines of inline Fortran
SEV_ORDER = {"TERMINAL ERROR": 4, "SEVERE ERROR": 3, "ERROR": 2, "WARNING": 1, "INFORMATION": 0}


# ---------------------------------------------------------------------------
# top level
# ---------------------------------------------------------------------------
def parse(path) -> dict:
    text = read_text_any(Path(path))
    lines = text.split("\n")
    header = _parse_header(lines)
    starts = [i for i, l in enumerate(lines) if "*** INPUT SUMMARY ***" in l]
    if not starts:
        starts = [0]
    runs = []
    for k, s in enumerate(starts):
        e = starts[k + 1] if k + 1 < len(starts) else len(lines)
        runs.append(_parse_run(lines, s, e))
    last = runs[-1]
    return {
        "file": str(path),
        "header": header,
        "n_runs": len(runs),
        "runs": runs,
        "model": last["model"],
        "error_summary": last["error_summary"],      # of the last run only: an older run's table misleads
        "status": _overall_status(runs),
    }


def _parse_header(lines: List[str]) -> dict:
    h = {}
    for l in lines[:40]:
        if "*** INPUT SUMMARY ***" in l:
            break
        if "LICENSED TO" in l.upper():
            continue  # never report the licensee
        m = re.search(r"VERSION:\s*([\d.]+)\s+Build\s+(\d+)", l)
        if m:
            h["engine"] = m.group(1)
            h["build"] = m.group(2)
            h["release"] = ENGINE_TO_RELEASE.get(m.group(1), "")
        m = re.search(r"PLATFORM:\s*(\S+)\s+(.*\d{4})", l)
        if m:
            h["platform"] = m.group(1)
            h["date"] = re.sub(r"\s+", " ", m.group(2)).strip()
        m = re.search(r"(\d{1,2}:\d{2}:\d{2}\s+[AP]\.M\.)", l)
        if m and "time" not in h:
            h["time"] = m.group(1)
    return h


def _section_bounds(lines, s, e):
    marks = {}
    for i in range(s, e):
        l = lines[i]
        if "*** INPUT TRANSLATOR MESSAGES ***" in l and "translator" not in marks:
            marks["translator"] = i
        elif "*** FLOWSHEET ANALYSIS MESSAGES ***" in l and "analysis" not in marks:
            marks["analysis"] = i
        elif "*** CALCULATION TRACE ***" in l and "trace" not in marks:
            marks["trace"] = i
        elif ("SIMULATION CALCULATIONS BEGIN" in l or l.startswith("Calculations begin")) and "sim" not in marks:
            marks["sim"] = i
    return marks


def _parse_run(lines, s, e) -> dict:
    m = _section_bounds(lines, s, e)
    t_start = m.get("translator", e)
    echo_meta, echo = _parse_echo(lines, s, t_start)
    model = parse_input_language([t for _, t in echo])
    model["runid"] = echo_meta.get("runid", "")
    tr_end = min([x for x in (m.get("trace"), m.get("analysis"), m.get("sim")) if x is not None] or [e])
    translator_msgs = parse_messages(lines, t_start, tr_end, "input translation") if "translator" in m else []
    a_start = m.get("analysis", tr_end)
    a_end = m.get("sim", e)
    analysis = _parse_analysis(lines, a_start, a_end) if "analysis" in m else {}
    analysis_msgs = parse_messages(lines, a_start, a_end, "flowsheet analysis") if "analysis" in m else []
    trace = _parse_trace(lines, m.get("sim", e), e)
    return {
        "echo_meta": echo_meta,
        "echo": echo,
        "model": model,
        "messages": _group(translator_msgs + analysis_msgs + trace.pop("messages")),
        "analysis": analysis,
        "trace": trace,
        "error_summary": _parse_error_summary(lines, s, e),
        "run_saved": sum(1 for i in range(s, e) if lines[i].strip() == "RUN SAVED"),
        "results_generated": any(("Results generated" in lines[i] or "Report file generated" in lines[i]
                                  or "Report Writer entered" in lines[i]) for i in range(s, e)),
        "reset_scope": sum(1 for i in range(s, e) if lines[i].strip() == "<reset scope>"),
    }


# ---------------------------------------------------------------------------
# input echo
# ---------------------------------------------------------------------------
def _parse_echo(lines, s, e):
    meta = {}
    echo = []
    started = False
    for i in range(s, e):
        l = lines[i]
        if not started:
            st = l.strip()
            if st.startswith(">>"):
                meta["kind"] = st[2:].strip()
            mm = re.match(r"^\s*(ORIGINAL RUN|EDIT RUN|RESTART RUN)\s+(.*)$", l)
            if mm:
                meta["run_type"] = mm.group(1)
                meta["date"] = re.sub(r"\s+", " ", mm.group(2)).strip()
            mm = re.match(r"^\s*(\d{1,2}:\d{2}:\d{2}\s*[AP]\.M\.)", l)
            if mm and "run_type" in meta and "time" not in meta:
                meta["time"] = mm.group(1)
            mm = re.match(r"^\s*INPUT FILE:\s*(\S+)", l)
            if mm:
                meta["input_file"] = mm.group(1)
            mm = re.match(r"^\s*RUN ID\s*:\s*(\S+)", l)
            if mm:
                meta["run_id"] = mm.group(1)
        mm = ECHO_RX.match(l)
        if mm and (started or mm.group(1) == "1"):
            started = True
            txt = mm.group(2) or ""
            dm = re.match(r"^;Directory\s*(.*?)\s*Runid\s+(.*)$", txt)
            if dm:
                meta["runid"] = dm.group(2).strip()
                if dm.group(1).strip():
                    txt = ";Directory <redacted>   Runid " + dm.group(2).strip()
            cm = re.match(r"^;Input file created by Aspen Plus Rel\. ([\d.]+) at (.*)$", txt)
            if cm:
                meta["created_by"] = cm.group(1)
                meta["created_at"] = cm.group(2).strip()
            echo.append((int(mm.group(1)), txt))
        elif started and l.strip() and not mm:
            break
    return meta, echo


def _statements(par_lines: List[str]) -> List[str]:
    """Join '&' continuations; keep Fortran lines verbatim (prefixed by 'F')."""
    out: List[str] = []
    cont = False
    for raw in par_lines:
        if FORTRAN_LINE.match(raw):
            out.append(raw.rstrip())
            cont = False
            continue
        s = raw.strip()
        if not s:
            continue
        if cont and out:
            out[-1] = out[-1] + " " + s
        else:
            out.append(s)
        cont = out[-1].endswith("&")
        if cont:
            out[-1] = out[-1][:-1].rstrip()
    return out


def paragraphs(texts: List[str]):
    """Split echo text into (keyword, header, [statements], [raw lines]) paragraphs."""
    pars = []
    cur = None
    for t in texts:
        if not t.strip():
            continue
        if t.startswith(";"):
            continue
        is_fortran = bool(FORTRAN_LINE.match(t))
        if not t[0].isspace() and not is_fortran:
            cur = {"key": t.split()[0].upper(), "header": t.strip(), "lines": []}
            pars.append(cur)
        elif cur is not None:
            cur["lines"].append(t)
    for p in pars:
        p["statements"] = _statements(p["lines"])
    return pars


def _kv(s: str) -> Dict[str, str]:
    """KEY=VALUE pairs; a value may be followed by a <unit> tag."""
    out = OrderedDict()
    for m in re.finditer(r"([A-Z0-9][A-Z0-9_-]*)=(\"[^\"]*\"|'[^']*'|\S+)(\s+<[^>]+>)?", s):
        v = m.group(2).strip("\"'")
        if m.group(3):
            v += " " + m.group(3).strip()
        out[m.group(1)] = v
    return out


def parse_input_language(texts: List[str]) -> dict:
    """Interpret the input-language echo into a structured model summary."""
    pars = paragraphs(texts)
    model = OrderedDict(
        title="", in_units="", databanks=[], components=[], solids=[], nc_components=[], property_methods=[],
        blocks=OrderedDict(), connections=OrderedDict(), streams=OrderedDict(), calculators=OrderedDict(),
        design_specs=OrderedDict(), sensitivities=OrderedDict(), convergence=OrderedDict(), tears=[],
        conv_options=[], sequences=OrderedDict(), disabled=[], prop_data=OrderedDict(), reactions=OrderedDict(),
        other=OrderedDict())
    for p in pars:
        key, hdr = p["key"], p["header"]
        toks = hdr.split()
        st = p["statements"]
        # header lines may continue with '&' into indented lines
        if hdr.endswith("&") and st:
            hdr = hdr[:-1].strip() + " " + st[0]
            st = st[1:]
            toks = hdr.split()
        if key == "TITLE":
            model["title"] = hdr[5:].strip().strip("'\"")
        elif key == "IN-UNITS":
            model["in_units"] = hdr[8:].strip()
        elif key == "DATABANKS":
            joined = " ".join([hdr] + st)
            model["databanks"] = re.findall(r"'([^']+)'", joined) + [w for w in re.findall(r"\b(NOASPENPCD)\b", joined)]
        elif key == "COMPONENTS":
            joined = " ".join(st)
            for entry in joined.split("/"):
                e = entry.split()
                if e:
                    model["components"].append({"id": e[0], "databank_name": e[1] if len(e) > 1 else "",
                                                "outname": e[2] if len(e) > 2 else ""})
        elif key in ("CISOLID-COMPS", "NC-COMPS"):
            names = toks[1:] + " ".join(st).split()
            (model["solids"] if key == "CISOLID-COMPS" else model["nc_components"]).extend(names)
        elif key == "FLOWSHEET":
            section = toks[1] if len(toks) > 1 else ""
            for s in st:
                w = s.split()
                if w and w[0].upper() == "BLOCK" and len(w) > 1:
                    ins, outs, mode = [], [], None
                    for tok in w[2:]:
                        if tok.upper().startswith("IN="):
                            mode, tok = "in", tok[3:]
                        elif tok.upper().startswith("OUT="):
                            mode, tok = "out", tok[4:]
                        if tok and mode:
                            (ins if mode == "in" else outs).append(tok)
                    model["connections"][w[1]] = {"in": ins, "out": outs, "section": section}
        elif key == "PROPERTIES":
            model["property_methods"].append(" ".join(toks[1:]))
        elif key == "PROP-DATA":
            params, comps = [], []
            for s in st:
                w = s.split()
                if not w:
                    continue
                if w[0] == "PROP-LIST":
                    params += [x for x in re.split(r"[\s/]+", s[len("PROP-LIST"):]) if x]
                elif w[0] in ("PVAL", "BPVAL") and len(w) > 1:
                    comps += w[1:3] if w[0] == "BPVAL" else w[1:2]
            name = toks[1] if len(toks) > 1 else f"#{len(model['prop_data']) + 1}"
            model["prop_data"][name] = {"params": list(dict.fromkeys(params)), "components": list(dict.fromkeys(comps))}
        elif key == "STREAM" and len(toks) > 1:
            model["streams"][toks[1]] = _parse_stream(st)
        elif key == "BLOCK" and len(toks) > 1:
            model["blocks"][toks[1]] = {"model": toks[2] if len(toks) > 2 else "", "statements": st}
        elif key == "CALCULATOR" and len(toks) > 1:
            model["calculators"][toks[1]] = _parse_fortran_object(st, p["lines"])
        elif key == "DESIGN-SPEC" and len(toks) > 1:
            model["design_specs"][toks[1]] = _parse_fortran_object(st, p["lines"])
        elif key == "SENSITIVITY" and len(toks) > 1:
            model["sensitivities"][toks[1]] = _parse_fortran_object(st, p["lines"])
        elif key == "CONVERGENCE" and len(toks) > 1:
            model["convergence"][toks[1]] = {"method": toks[2] if len(toks) > 2 else "", "statements": st}
        elif key == "TEAR":
            for s in st:
                model["tears"] += [x for x in re.split(r"[\s/]+", s) if x and "=" not in x]
        elif key == "CONV-OPTIONS":
            model["conv_options"] += st
        elif key == "SEQUENCE" and len(toks) > 1:
            model["sequences"][toks[1]] = st
        elif key == "DISABLE":
            for s in st:  # 'DESIGN-SPEC CO2 DS-1 DS-2' disables several objects of one type
                w = s.split()
                if len(w) >= 2:
                    model["disabled"] += [f"{w[0].upper()} {name}" for name in w[1:]]
                elif w:
                    model["disabled"].append(w[0])
        elif key == "REACTIONS" and len(toks) > 1:
            model["reactions"][toks[1]] = {"type": toks[2] if len(toks) > 2 else "", "statements": st}
        else:
            name = toks[1] if len(toks) > 1 else ""
            model["other"].setdefault(key, []).append(name)
    _classify_streams(model)
    return model


def _parse_stream(st: List[str]) -> dict:
    d = {"substreams": [], "composition": []}
    for s in st:
        w = s.split()
        if not w:
            continue
        if w[0] == "SUBSTREAM" and len(w) > 1:
            d["substreams"].append({"name": w[1], **_kv(s)})
        elif w[0] in ("MOLE-FRAC", "MASS-FRAC", "MOLE-FLOW", "MASS-FLOW", "STDVOL-FRAC", "STDVOL-FLOW", "VOLUME-FLOW"):
            pairs = []
            for entry in s[len(w[0]):].split("/"):
                e = entry.split()
                if len(e) >= 2:
                    pairs.append((e[0], e[1]))
            d["composition"].append({"basis": w[0], "values": pairs})
    return d


def _parse_fortran_object(st: List[str], raw_lines: List[str]) -> dict:
    d = OrderedDict(defines=[], read_vars=[], write_vars=[], execute=[], spec=None, tol=None, vary=[],
                    limits=None, tabulate=[], range=[], params=[], fortran=[], other=[])
    for s in st:
        if FORTRAN_LINE.match(s):
            d["fortran"].append(s)
            continue
        w = s.split()
        if not w:
            continue
        k = w[0].upper()
        if k == "DEFINE" and len(w) >= 3:
            d["defines"].append({"name": w[1], "type": w[2], "detail": " ".join(w[3:])})
        elif k == "VECTOR-DEF" and len(w) >= 3:
            d["defines"].append({"name": w[1], "type": "VECTOR-DEF " + w[2], "detail": " ".join(w[3:])})
        elif k == "READ-VARS":
            d["read_vars"] += w[1:]
        elif k == "WRITE-VARS":
            d["write_vars"] += w[1:]
        elif k == "EXECUTE":
            d["execute"].append(" ".join(w[1:]))
        elif k == "SPEC":
            d["spec"] = " ".join(w[1:])
        elif k == "TOL-SPEC":
            d["tol"] = " ".join(w[1:])
        elif k == "VARY":
            d["vary"].append(" ".join(w[1:]))
        elif k == "LIMITS":
            d["limits"] = " ".join(w[1:])
        elif k == "TABULATE":
            d["tabulate"].append(" ".join(w[1:]))
        elif k == "RANGE":
            d["range"].append(" ".join(w[1:]))
        elif k == "PARAM":
            d["params"].append(" ".join(w[1:]))
        else:
            d["other"].append(s)
    return d


def _classify_streams(model):
    produced = set()
    consumed = set()
    for c in model["connections"].values():
        produced.update(c["out"])
        consumed.update(c["in"])
    for name, s in model["streams"].items():
        s["role"] = "tear/initial estimate" if name in produced else ("feed" if name in consumed else "unconnected")
    model["products"] = sorted(produced - consumed)
    model["feeds_connected"] = sorted(consumed - produced)


# ---------------------------------------------------------------------------
# messages
# ---------------------------------------------------------------------------
def parse_messages(lines, s, e, phase) -> List[dict]:
    out = []
    i = s
    ctx = {"iter": None, "loop": None, "block": None}
    while i < e:
        l = lines[i]
        lm = re.match(r"^\s*CONVERGENCE BLOCK\s+(\S+)", l)
        if lm:
            ctx["loop"] = lm.group(1)
        im = re.match(r"^\s*ITER\s+(\d+)\s+For Tear", l)
        if im:
            ctx["iter"] = int(im.group(1))
        bm = re.match(r"^\s*(?:UOS BLOCK|GENERATING RESULTS FOR UOS BLOCK)\s+(\S+)", l)
        if bm:
            ctx["block"] = bm.group(1)
        hm = HEAD_RX.match(l)
        rest3 = (hm.group(3) or "").strip() if hm else ""
        is_header = hm and (hm.group(1) or re.match(r"\s*(IN|WHILE|DURING|FROM|ON)\b", hm.group(3) or "")
                            or not rest3 or ID_RX.fullmatch(rest3))  # 'INFORMATION   (PSTOP1AP.1)'
        if not is_header:
            i += 1
            continue
        sev = hm.group(2)
        context = hm.group(3) or ""
        mid = ID_RX.search(context)
        body: List[str] = []
        j = i + 1
        if mid:
            context = ID_RX.sub("", context)
        elif j < e:
            nxt = lines[j]
            m2 = ID_RX.search(nxt)
            if m2:
                mid = m2
                rest = ID_RX.sub("", nxt).strip()
                if rest.startswith('"') or rest.startswith("(MODEL") or rest.startswith("(WHILE"):
                    context += " " + rest
                elif rest:
                    body.append(rest)
                j += 1
        while j < e and len(body) < 25:
            b = lines[j]
            if not b.strip() or HEAD_RX.match(b) or TRACE_RX.match(b) or b.startswith(" ***") or not b.startswith("   "):
                break
            body.append(b.strip())
            j += 1
        context = re.sub(r"\s+", " ", context).strip()
        out.append({
            "phase": phase, "severity": sev, "id": mid.group(1) if mid else "", "context": context,
            "where": _where(context, body), "body": body, "line": i + 1,
            "loop": ctx["loop"], "iter": ctx["iter"],
        })
        i = j
    return out


def _where(context: str, body: List[str]) -> str:
    m = re.search(r'BLOCK:\s*"([^"]+)"', context)
    if m:
        mm = re.search(r'MODEL:\s*"([^"]+)"', context)
        kind = "convergence block" if "CONVERGENCE BLOCK" in context else "block"
        return f"{kind} {m.group(1)}" + (f" ({mm.group(1)})" if mm else "")
    m = re.search(r'"([A-Z-]+)" PARAGRAPH', context)
    if m:
        for b in body[:2]:
            mm = re.search(r"\b([A-Z-]+) NAME:\s*(\S+)", b)
            if mm:
                return f"{m.group(1)} {mm.group(2)}"
        return f"{m.group(1)} paragraph"
    for b in body[:3]:
        mm = re.search(r"(?:FORTRAN|CALCULATOR) BLOCK (\S+)", b, re.I)
        if mm:
            return f"calculator {mm.group(1)}"
    c = re.sub(r"^(IN|WHILE|DURING|FROM|ON)\s+(THE\s+)?", "", context).strip()
    return c.lower() or "-"


def _group(msgs: List[dict]) -> List[dict]:
    groups: "OrderedDict[tuple, dict]" = OrderedDict()
    for m in msgs:
        key = (m["phase"], m["severity"], m["id"] or m["context"][:40])
        g = groups.get(key)
        if not g:
            g = groups[key] = {"phase": m["phase"], "severity": m["severity"], "id": m["id"],
                               "context": m["context"], "count": 0, "where": [], "first_lines": [],
                               "body": m["body"], "first_line_no": m["line"], "iters": []}
        g["count"] += 1
        if m["where"] not in g["where"]:
            g["where"].append(m["where"])
        fl = next((b for b in m["body"] if not re.match(r"^[A-Z -]+ NAME:\s*\S+$", b)), "")
        if fl and fl not in g["first_lines"]:
            g["first_lines"].append(fl)
        if m.get("iter") is not None:
            g["iters"].append((m.get("loop"), m.get("iter")))
    out = list(groups.values())
    out.sort(key=lambda g: (-SEV_ORDER.get(g["severity"], 0), g["first_line_no"]))
    return out


# ---------------------------------------------------------------------------
# flowsheet analysis + trace
# ---------------------------------------------------------------------------
def _parse_analysis(lines, s, e) -> dict:
    conv = OrderedDict()
    order: List[str] = []
    i = s
    while i < e:
        l = lines[i]
        m = re.search(r"BLOCK\s+(\S+)\s+\(METHOD:\s*([^)]+)\)\s+HAS BEEN DEFINED TO CONVERGE", l)
        if m:
            items = {}
            j = i + 1
            while j < e and lines[j].strip():
                mm = re.match(r"^\s*([A-Z -]+):\s*(.*)$", lines[j])
                if mm:
                    items.setdefault(mm.group(1).strip().lower(), []).extend(mm.group(2).split())
                j += 1
            conv[m.group(1)] = {"method": m.group(2).strip(), **items}
            i = j
            continue
        if "COMPUTATION ORDER FOR THE FLOWSHEET IS" in l:
            j = i + 1
            while j < e and lines[j].strip():
                order.extend(lines[j].split())
                j += 1
            i = j
            continue
        i += 1
    return {"convergence_blocks": conv, "computation_order": " ".join(order)}


def _parse_trace(lines, s, e) -> dict:
    passes = 0
    loops: "OrderedDict[str, list]" = OrderedDict()
    blocks: "OrderedDict[str, dict]" = OrderedDict()
    executions: "OrderedDict[str, int]" = OrderedDict()
    calc_exec: "OrderedDict[str, int]" = OrderedDict()
    cur = None
    generating = False  # results-generation flashes (NPSH, TQ curves...) are not the block's outlet state
    for i in range(s, e):
        l = lines[i]
        if "SIMULATION CALCULATIONS BEGIN" in l:
            passes += 1
            blocks = OrderedDict()  # keep values of the last pass only
            continue
        m = re.match(r"^\s*(GENERATING RESULTS FOR )?UOS BLOCK\s+(\S+)\s+MODEL:\s*(\S+)", l)
        if m:
            cur = m.group(2)
            generating = bool(m.group(1))
            blocks.setdefault(cur, {"model": m.group(3), "values": OrderedDict()})
            if not generating:
                executions[cur] = executions.get(cur, 0) + 1
            continue
        m = re.match(r"^\s*CALCULATOR BLOCK\s+(\S+)\s*(TIME|$)", l)
        if m:
            calc_exec[m.group(1)] = calc_exec.get(m.group(1), 0) + 1
            cur = None
            continue
        m = LOOP_RX.match(l)
        if m:
            loops.setdefault(m.group(1), []).append(
                {"iter": int(m.group(2)), "status": m.group(3).strip(), "max_err_tol": m.group(4)})
            cur = None
            continue
        if re.match(r"^\s*(CONVERGENCE BLOCK|ENTHALPY CALCULATION|BEGIN HEATX TQ|END HEATX|Report Writer|"
                    r"Results generated|--FLASH|STREAM \S+ WILL BE FLASHED|SENSITIVITY BLOCK|DESIGN-SPEC)", l):
            cur = None  # values after these lines belong to stream flashes / TQ curves, not to the block
            continue
        if cur and l.strip() and not HEAD_RX.match(l):
            prefix = ""
            st = l.strip()
            if st.startswith("HOT:"):
                prefix, st = "HOT ", st[4:]
            elif st.startswith("COLD:"):
                prefix, st = "COLD ", st[5:]
            vals = blocks[cur]["values"]
            for k, v in KV_RX.findall(st):
                k = prefix + re.sub(r"\s+", " ", k.strip())
                if generating and (k in ("T", "P", "V", "Q", "KODE", "NTRIAL") or k in vals):
                    continue
                try:
                    vals[k] = float(v.replace("D", "E").replace("d", "e"))
                except ValueError:
                    pass
    loop_summary = OrderedDict()
    for name, its in loops.items():
        last = its[-1]
        loop_summary[name] = {"iterations": last["iter"], "converged": "CONVERGED" in last["status"].upper()
                              and "NOT" not in last["status"].upper(), "last_status": last["status"],
                              "max_err_tol": last["max_err_tol"], "history": its[-6:]}
    return {"passes": passes, "loops": loop_summary, "blocks": blocks, "executions": executions,
            "calculator_executions": calc_exec, "messages": parse_messages(lines, s, e, "simulation")}


def _parse_error_summary(lines, s, e) -> Optional[dict]:
    found = None
    for i in range(s, e):
        if "NO ERRORS OR WARNINGS GENERATED" in lines[i]:
            found = {"none": True}
        if "*** SUMMARY OF ERRORS ***" in lines[i]:
            tab = {}
            for j in range(i + 1, min(i + 10, e)):
                m = re.match(r"^\s*(TERMINAL ERRORS|SEVERE ERRORS|ERRORS|WARNINGS)\s+(\d+)\s+(\d+)\s+(\d+)", lines[j])
                if m:
                    tab[m.group(1).lower()] = {"physical_property": int(m.group(2)), "system": int(m.group(3)),
                                               "simulation": int(m.group(4))}
            found = {"none": False, "table": tab}
    return found


def _overall_status(runs) -> str:
    last = runs[-1]
    es = last["error_summary"]
    loops = last["trace"]["loops"]
    bad_loops = [n for n, l in loops.items() if not l["converged"]]
    if es is None:
        if last["trace"]["passes"] == 0:
            return "not run (input translation only)"
        if last.get("results_generated"):
            txt = ("calculations finished and results were generated; no summary-of-errors table yet "
                   "(Aspen appends it when the run is saved - check the .cpm or the Control Panel)")
        else:
            txt = "no error summary in file (run interrupted, or temporary file of an open session)"
    elif es.get("none"):
        txt = "completed: no errors or warnings"
    else:
        t = es["table"]
        tot = lambda k: sum(t.get(k, {}).values())
        parts = []
        for k, label in (("terminal errors", "terminal"), ("severe errors", "severe"), ("errors", "errors"),
                         ("warnings", "warnings")):
            if tot(k):
                parts.append(f"{tot(k)} {label}")
        txt = "completed" + (": " + ", ".join(parts) if parts else ": no errors or warnings")
    if bad_loops:
        txt += f"; NOT CONVERGED: {', '.join(bad_loops)}"
    return txt


# ---------------------------------------------------------------------------
# rendering
# ---------------------------------------------------------------------------
def _c(K):
    return K - 273.15


def block_rows(blocks: dict) -> List[dict]:
    rows = []
    for name, b in blocks.items():
        v = b["values"]
        model = b["model"]
        T = v.get("OUTLET TEMP", v.get("T", v.get("TEMP")))
        P = v.get("OUTLET PRES", v.get("P"))
        duty = None
        other = []
        if model == "COMPR" or "BRAKE HP" in v:
            duty = v.get("BRAKE HP")
            if "CALC ISENTR EFF" in v:
                other.append(f"eff {v['CALC ISENTR EFF']:.2f}")
        elif model == "PUMP" or "BRAKE PWR" in v:
            duty = v.get("ELEC PWR", v.get("BRAKE PWR"))
            if "DELTA P" in v:
                other.append(f"dP {v['DELTA P'] / 1e5:.4g} bar")
            if "PUMP EFF" in v:
                other.append(f"eff {v['PUMP EFF']:.2f}")
        elif "DUTY" in v:
            duty = v.get("DUTY")
        else:
            duty = v.get("Q")
        if "HOT TIN" in v and "HOT TOUT" in v:
            T = None
            other.append(f"hot {_c(v['HOT TIN']):.1f}->{_c(v['HOT TOUT']):.1f} C")
        if "COLD TIN" in v and "COLD TOUT" in v:
            other.append(f"cold {_c(v['COLD TIN']):.1f}->{_c(v['COLD TOUT']):.1f} C")
        if "AREA" in v:
            other.append(f"area {fmt_num(v['AREA'])} m2")
        if "V" in v and model not in ("COMPR",):
            other.append(f"vap.frac {v['V']:.3g}")
        rows.append({"block": name, "model": model, "T_C": None if T is None else _c(T),
                     "P_bar": None if P is None else P / 1e5, "duty_kW": None if duty is None else duty / 1e3,
                     "other": "; ".join(other)})
    return rows


def checks(d: dict) -> List[str]:
    """Heuristic engineering flags (clearly labelled as such in the output)."""
    out = []
    run = d["runs"][-1]
    for name, l in run["trace"]["loops"].items():
        if not l["converged"]:
            out.append(f"Loop {name} did not converge (last: {l['last_status']}, max err/tol {l['max_err_tol']}).")
    for r in block_rows(run["trace"]["blocks"]):
        if r["model"] == "COMPR" and r["T_C"] is not None and r["T_C"] > 200:
            out.append(f"{r['block']}: discharge temperature {r['T_C']:.0f} C (> 200 C) - check against machine/seal "
                       f"limits; more stages, intercooling or a lower pressure ratio per stage bring it down.")
        if r["P_bar"] is not None and r["P_bar"] <= 0:
            out.append(f"{r['block']}: non-positive pressure in trace ({r['P_bar']:.3g} bar).")
    m = run["model"]
    for kind, objs in (("calculator", m["calculators"]), ("design spec", m["design_specs"]),
                       ("sensitivity", m["sensitivities"])):
        for name, obj in objs.items():
            for issue in fortran_lint(obj):
                if issue.startswith("uses names") or "column 72" in issue or "tab character" in issue:
                    out.append(f"{kind} {name}: {issue}")
    for g in run["messages"]:
        if g["severity"] in ("ERROR", "SEVERE ERROR", "TERMINAL ERROR"):
            out.append(f"{g['severity']} {g['id']} at {', '.join(g['where'])} (x{g['count']}).")
    for g in run["messages"]:
        if g["phase"] == "simulation" and g["iters"] and all(it is not None and it == 0 for _, it in g["iters"]):
            out.append(f"{g['id']} at {', '.join(g['where'])} only in iteration 0 of {g['iters'][0][0]} "
                       "(initial estimates) - usually harmless if the loop converged.")
    return out


def render_markdown(d: dict, fortran: bool = False, max_blocks: int = 60) -> str:
    h = d["header"]
    run = d["runs"][-1]
    m = run["model"]
    meta = run["echo_meta"]
    L = []
    rel = f"Aspen Plus {h.get('release') or ''} (engine {h.get('engine', '?')}, build {h.get('build', '?')})".replace("  ", " ")
    L.append(f"# Run digest: {Path(d['file']).name}")
    when = (f"{meta['date']} {meta.get('time', '')}".strip() if meta.get("date")
            else f"{h.get('date', '?')} {h.get('time', '')}".strip())
    L.append(f"- {rel}; run {when}".rstrip())
    if d["n_runs"] > 1:
        L.append(f"- This file holds {d['n_runs']} runs; the digest describes the last one "
                 f"({meta.get('run_type', 'run').lower()} {d['n_runs']} of {d['n_runs']}, {when})")
    L.append(f"- Runid: {m.get('runid') or '?'}; input file: {meta.get('input_file', '?')}")
    L.append(f"- Status: {d['status']}")
    es = d["error_summary"]
    if es and not es.get("none"):
        t = es["table"]
        L.append("- Summary of errors (phys.prop/system/simulation): " + "; ".join(
            f"{k} {v['physical_property']}/{v['system']}/{v['simulation']}" for k, v in t.items()))
    L.append("")
    L.append("## Model (from the input echo)")
    if m["title"]:
        L.append(f"- Title: {m['title']}")
    L.append(f"- Units: {m['in_units'] or '-'}; property method(s): {', '.join(m['property_methods']) or '-'}")
    if m["databanks"]:
        L.append(f"- Databanks: {', '.join(m['databanks'])}")
    user_db = [c["id"] for c in m["components"] if c["databank_name"] and c["databank_name"] == c["id"]]
    comps = ", ".join(c["id"] for c in m["components"])
    L.append(f"- Components ({len(m['components'])}): {comps}")
    if m["solids"]:
        L.append(f"- Conventional solids (CISOLID): {', '.join(m['solids'])}")
    if m["prop_data"]:
        pd = "; ".join(f"{k}: {', '.join(v['params'])}" + (f" for {', '.join(v['components'][:6])}" if v["components"] else "")
                       for k, v in m["prop_data"].items())
        L.append(f"- User property data: {pd}")
    # blocks
    L.append("")
    L.append(f"### Blocks ({len(m['blocks'])})")
    L.append("| Block | Model | In -> Out | Key input |")
    L.append("|---|---|---|---|")
    for name, b in list(m["blocks"].items())[:max_blocks]:
        c = m["connections"].get(name, {"in": [], "out": []})
        key_inp = "; ".join(_short_spec(b["statements"]))
        L.append(f"| {name} | {b['model']} | {' '.join(c['in'])} -> {' '.join(c['out'])} | {key_inp} |")
    feeds = [n for n, s in m["streams"].items() if s["role"] == "feed"]
    est = [n for n, s in m["streams"].items() if s["role"] != "feed"]
    L.append("")
    if feeds:
        L.append("- Feeds: " + "; ".join(f"{n} ({_stream_short(m['streams'][n])})" for n in feeds))
    if est:
        L.append("- Streams with entered values that are block outlets (tear/initial estimates): " + ", ".join(est))
    if m["products"]:
        L.append("- Product streams: " + ", ".join(m["products"]))
    # flowsheet objects
    dis = set(x.split(" ", 1)[1] if " " in x else x for x in m["disabled"])
    if m["calculators"]:
        L.append("")
        L.append(f"### Calculators ({len(m['calculators'])})")
        for name, c in m["calculators"].items():
            L.extend(_render_fortran_object(name, c, name in dis, fortran))
    if m["design_specs"]:
        L.append("")
        L.append(f"### Design specs ({len(m['design_specs'])})")
        for name, c in m["design_specs"].items():
            L.extend(_render_fortran_object(name, c, name in dis, fortran))
    if m["sensitivities"]:
        L.append("")
        L.append(f"### Sensitivity analyses ({len(m['sensitivities'])})")
        for name, c in m["sensitivities"].items():
            L.extend(_render_fortran_object(name, c, name in dis, fortran))
    conv_lines = []
    if m["convergence"]:
        conv_lines.append("user convergence blocks: " + ", ".join(f"{k} ({v['method']})" for k, v in m["convergence"].items()))
    if m["tears"]:
        conv_lines.append("user tears: " + " ".join(m["tears"]))
    if m["conv_options"]:
        conv_lines.append("CONV-OPTIONS: " + " | ".join(m["conv_options"]))
    if m["sequences"]:
        conv_lines.append("user sequence(s): " + ", ".join(m["sequences"]))
    if m["disabled"]:
        conv_lines.append("disabled: " + ", ".join(m["disabled"]))
    if m["reactions"]:
        conv_lines.append("reaction sets: " + ", ".join(f"{k} ({v['type']})" for k, v in m["reactions"].items()))
    if m["other"]:
        conv_lines.append("other paragraphs: " + ", ".join(f"{k}" + (f" x{len(v)}" if len(v) > 1 else "")
                                                           for k, v in m["other"].items()))
    if conv_lines:
        L.append("")
        L.append("### Convergence and other settings")
        L.extend("- " + x for x in conv_lines)
    # analysis + trace
    an = run["analysis"]
    tr = run["trace"]
    L.append("")
    L.append("## Flowsheet analysis and calculation")
    for name, cb in an.get("convergence_blocks", {}).items():
        extra = "; ".join(f"{k}: {' '.join(v)}" for k, v in cb.items() if k != "method")
        L.append(f"- {name} ({cb['method']}) converges {extra}")
    if an.get("computation_order"):
        L.append(f"- Computation order: {an['computation_order']}")
    if tr["loops"]:
        for name, l in tr["loops"].items():
            state = "converged" if l["converged"] else "NOT converged"
            L.append(f"- Loop {name}: {state} after {l['iterations']} iterations (max err/tol {l['max_err_tol']})")
    elif tr["passes"]:
        L.append("- No convergence loops in the trace (sequential, no recycle iterations).")
    if tr["calculator_executions"]:
        L.append("- Calculator executions: " + ", ".join(f"{k} x{v}" for k, v in tr["calculator_executions"].items()))
    rows = block_rows(tr["blocks"])
    if rows:
        L.append("")
        L.append("### Block results from the trace (last pass; trace values are SI, converted)")
        L.append("| Block | Model | T out (C) | P out (bar) | Duty/power (kW) | Other |")
        L.append("|---|---|---|---|---|---|")
        for r in rows[:max_blocks]:
            t = "" if r["T_C"] is None else f"{r['T_C']:.1f}"
            p = "" if r["P_bar"] is None else fmt_num(r["P_bar"])
            q = "" if r["duty_kW"] is None else fmt_num(r["duty_kW"])
            L.append(f"| {r['block']} | {r['model']} | {t} | {p} | {q} | {r['other']} |")
    # messages
    L.append("")
    L.append("## Messages")
    if not run["messages"]:
        L.append("- none")
    else:
        L.append("| Severity | ID | Phase | Where | Count | First line |")
        L.append("|---|---|---|---|---|---|")
        for g in run["messages"]:
            first = g["first_lines"][0] if g["first_lines"] else ""
            more = f" (+{len(g['first_lines']) - 1} variants)" if len(g["first_lines"]) > 1 else ""
            where = ", ".join(g["where"][:4]) + (" ..." if len(g["where"]) > 4 else "")
            L.append(f"| {g['severity']} | {g['id'] or '-'} | {g['phase']} | {where} | {g['count']} | "
                     f"{first[:110]}{more} |")
    flags = checks(d)
    if flags:
        L.append("")
        L.append("## Auto-checks (heuristic, verify before acting)")
        L.extend("- " + f for f in flags)
    ids = sorted({g["id"] for g in run["messages"] if g["id"]})
    if ids:
        L.append("")
        L.append("Message IDs to look up (references/messages.md, then the help index): " + ", ".join(ids))
    return "\n".join(L)


def _short_spec(statements: List[str], n: int = 2) -> List[str]:
    out = []
    for s in statements:
        w = s.split()
        if not w:
            continue
        if w[0] in ("PARAM", "STOIC", "CONV", "FEEDS", "COL-CONFIG", "RATEFRAC", "RXN-IDS", "EXTENT", "FRAC",
                    "SPECS", "MOLE-FLOW", "MASS-FLOW", "TYPE", "MOLE-YIELD", "MASS-YIELD", "P-SPEC"):
            s = re.sub(r"\s+(SB-MAXIT|SB-TOL|MAXIT|DPPARMOPT)=\S+", "", s)
            out.append(s[:90])
        if len(out) >= n:
            break
    return out


def _stream_short(s: dict) -> str:
    parts = []
    for ss in s["substreams"]:
        kv = {k: v for k, v in ss.items() if k in ("TEMP", "PRES", "VFRAC", "MOLE-FLOW", "MASS-FLOW", "PHASE")}
        parts.append(" ".join(f"{k}={v}" for k, v in kv.items()))
    for c in s["composition"][:1]:
        vals = ", ".join(f"{a} {b}" for a, b in c["values"][:6])
        parts.append(f"{c['basis']}: {vals}")
    return "; ".join(p for p in parts if p)


def _render_fortran_object(name: str, c: dict, disabled: bool, fortran: bool) -> List[str]:
    L = [f"- **{name}**" + (" (disabled)" if disabled else "")]
    if c["defines"]:
        L.append("  - defines: " + "; ".join(f"{d['name']} = {d['type']} {d['detail']}".strip() for d in c["defines"]))
    if c["read_vars"] or c["write_vars"]:
        L.append(f"  - import (READ-VARS): {' '.join(c['read_vars']) or '-'}; export (WRITE-VARS): {' '.join(c['write_vars']) or '-'}")
    if c["execute"]:
        L.append(f"  - execute: {'; '.join(c['execute'])}")
    if c["spec"]:
        L.append(f"  - spec: {c['spec']}" + (f" (tol {c['tol']})" if c["tol"] else ""))
    if c["vary"]:
        L.append(f"  - vary: {'; '.join(c['vary'])}" + (f"; limits {c['limits']}" if c["limits"] else ""))
    if c["range"]:
        L.append(f"  - range: {'; '.join(c['range'])}")
    if c["tabulate"]:
        L.append(f"  - tabulate: {len(c['tabulate'])} variables")
    if c["params"]:
        L.append(f"  - params: {'; '.join(c['params'])}")
    if c["fortran"]:
        L.append(f"  - Fortran: {len(c['fortran'])} lines")
        for issue in fortran_lint(c):
            L.append(f"  - lint: {issue}")
        if fortran:
            L.append("```fortran")
            # 'F' in column 1 marks a Fortran statement in the input language; replacing it by a blank
            # restores the text as typed on the Calculate sheet (statements start in column 7).
            L.extend((" " + f[1:]) if f.startswith("F") else f for f in c["fortran"])
            L.append("```")
    return L


# ---------------------------------------------------------------------------
# inline Fortran lint (calculators, design specs, sensitivity blocks)
# ---------------------------------------------------------------------------
_F_KEYWORDS = set("""IF THEN ELSE ELSEIF ENDIF END DO ENDDO CONTINUE GOTO GO TO RETURN CALL WRITE READ FORMAT
REAL INTEGER DOUBLE PRECISION LOGICAL CHARACTER PARAMETER DIMENSION DATA COMMON INCLUDE IMPLICIT NONE STOP
EXTERNAL INTRINSIC SAVE""".split())
_F_INTRINSICS = set("""ABS DABS IABS SQRT DSQRT EXP DEXP LOG DLOG LOG10 DLOG10 ALOG ALOG10 SIN COS TAN DSIN DCOS DTAN
ASIN ACOS ATAN ATAN2 DASIN DACOS DATAN DATAN2 SINH COSH TANH DSINH DCOSH DTANH MAX MIN MAX0 MIN0 MAX1 MIN1
AMAX0 AMAX1 AMIN0 AMIN1 DMAX1 DMIN1 MOD AMOD DMOD SIGN DSIGN ISIGN INT IFIX IDINT NINT IDNINT REAL FLOAT SNGL
DBLE DFLOAT AINT DINT ANINT DNINT DIM DDIM IDIM""".split())
# unit numbers Aspen provides to inline Fortran: WRITE(NTERM,*) control panel, NHSTRY history, NRPT report
_F_ASPEN_UNITS = {"NTERM", "NHSTRY", "NRPT"}
_F_OPS = re.compile(r"\.(LT|LE|GT|GE|EQ|NE|AND|OR|NOT|EQV|NEQV|TRUE|FALSE)\.", re.I)
_F_IDENT = re.compile(r"(?<![\w.])([A-Z][A-Z0-9_]*)")


def _idents(expr: str) -> List[str]:
    expr = _F_OPS.sub(" ", expr)
    out = []
    for m in _F_IDENT.finditer(expr):
        name = m.group(1)
        if name in _F_KEYWORDS or name in _F_INTRINSICS or name in _F_ASPEN_UNITS:
            continue
        out.append(name)
    return out


def _split_if(stmt: str):
    """'IF (cond) rest' -> (cond, rest); otherwise (None, stmt)."""
    m = re.match(r"^(ELSE\s*IF|IF)\s*\(", stmt)
    if not m:
        return None, stmt
    depth, i = 0, m.end() - 1
    while i < len(stmt):
        if stmt[i] == "(":
            depth += 1
        elif stmt[i] == ")":
            depth -= 1
            if depth == 0:
                return stmt[m.end():i], stmt[i + 1:].strip()
        i += 1
    return stmt[m.end():], ""


def fortran_lint(obj: dict) -> List[str]:
    """Static checks on the inline Fortran of a calculator / design spec / sensitivity block."""
    issues: List[str] = []
    lines = [(" " + f[1:]) if f.startswith("F") else f for f in obj.get("fortran", [])]
    stmts: List[tuple] = []
    for n, l in enumerate(lines, 1):
        if l[:1] in ("C", "c", "*", "!"):
            continue
        if "\t" in l:
            issues.append(f"line {n}: tab character - use spaces (fixed-form Fortran)")
        if len(l.rstrip()) > 72:
            issues.append(f"line {n}: text past column 72 is ignored by the compiler ('{l[72:].strip()[:24]}')")
        body = l[:72]
        if len(body) > 5 and body[5] not in (" ", "0") and stmts:
            stmts[-1] = (stmts[-1][0], stmts[-1][1] + " " + body[6:].strip())
            continue
        label = body[:5].strip()
        if label and not label.isdigit():
            issues.append(f"line {n}: statement starts before column 7")
        stmts.append((n, body[6:].strip() if len(body) > 6 else ""))
    defined = {d["name"].upper() for d in obj.get("defines", [])}
    imports = {v.upper() for v in obj.get("read_vars", [])}
    exports = {v.upper() for v in obj.get("write_vars", [])}
    assigned: set = set()
    all_used: set = set()
    used_unset: "OrderedDict[str, int]" = OrderedDict()
    import_assigned: "OrderedDict[str, int]" = OrderedDict()
    for n, st in stmts:
        su = re.sub(r"'[^']*'", " ", st.upper())
        su = re.sub(r"^\d+\s+", "", su)
        if re.match(r"^FORMAT\s*\(", su):  # edit descriptors (F10.4, E12.5, 1X) are not variables
            continue
        cond, rest = _split_if(su)
        uses: List[str] = _idents(cond) if cond is not None else []
        lhs = None
        dm = re.match(r"^DO\s+(?:\d+\s*,?\s*)?([A-Z][A-Z0-9_]*)\s*=(.*)$", rest)
        am = re.match(r"^([A-Z][A-Z0-9_]*)\s*(\([^=]*\))?\s*=(.*)$", rest)
        if dm:
            lhs, rhs = dm.group(1), dm.group(2)
            uses += _idents(rhs)
        elif am and am.group(1) not in _F_KEYWORDS:
            lhs, rhs = am.group(1), am.group(3)
            uses += _idents(rhs) + (_idents(am.group(2)) if am.group(2) else [])
        else:
            uses += _idents(rest)
        all_used.update(uses)
        for u in uses:
            if u not in assigned and u not in defined and u not in used_unset:
                used_unset[u] = n
        if lhs:
            assigned.add(lhs)
            if lhs in imports and lhs not in import_assigned:
                import_assigned[lhs] = n
    never = [u for u in used_unset if u not in assigned]
    later = [u for u in used_unset if u in assigned]
    if never:
        issues.append("uses names that are neither defined nor set (they start as 0/undefined): "
                      + ", ".join(f"{u} (line {used_unset[u]})" for u in never))
    if later:
        issues.append("used before being set: " + ", ".join(f"{u} (line {used_unset[u]})" for u in later))
    if import_assigned:
        issues.append("assigns to imported (read) variables - copy them to local names first (ADFORT.7): "
                      + ", ".join(import_assigned))
    missing = [e for e in exports if e not in assigned]
    if obj.get("fortran") and missing:
        issues.append("exported (write) variables never assigned: " + ", ".join(sorted(missing)))
    unused = sorted(v for v in imports if v not in all_used and v not in assigned)
    if obj.get("fortran") and unused:
        issues.append("imported variables never used in the code (still count for sequencing; remove if not "
                      "needed): " + ", ".join(unused))
    return issues


def echo_text(d: dict, run_index: int = -1) -> str:
    """Reconstructed input-language text (the .inp) of a run."""
    return "\n".join(t for _, t in d["runs"][run_index]["echo"])


def diff(a: dict, b: dict, context: int = 2) -> str:
    def norm(d):
        out = []
        for _, t in d["runs"][-1]["echo"]:
            if t.startswith(";Input file created") or t.startswith(";Directory"):
                continue
            out.append(t.rstrip())
        return out
    la, lb = norm(a), norm(b)
    return "\n".join(difflib.unified_diff(la, lb, fromfile=Path(a["file"]).name, tofile=Path(b["file"]).name,
                                          n=context, lineterm=""))
