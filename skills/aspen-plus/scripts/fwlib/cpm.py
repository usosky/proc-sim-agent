"""Read an Aspen Plus Control Panel messages export (.cpm).

The .cpm is what the Control Panel showed: input-processing messages, flowsheet
analysis (convergence blocks, computation order), the run progress block by block,
convergence-loop iterations (nested loops are marked '>' / '>>'), RadFrac iteration
tables, warnings/errors (without message IDs) and the summary of simulation errors.
"""
from __future__ import annotations

import re
from collections import OrderedDict
from pathlib import Path
from typing import List

from .common import read_text_any
from .his import HEAD_RX, SEV_ORDER

LOOP_RX = re.compile(r"^(>+)\s*(Beginning Convergence Loop|Loop)\s+(\S+)\s+Method:\s*(\S+)(?:\s+Iteration\s+(\d+))?")
BLOCK_RX = re.compile(r"^\s+Block:\s+(\S+)\s+Model:\s+(\S+)")
CALC_RX = re.compile(r"^\s+Calculator Block\s+(\S+)")


def parse(path) -> dict:
    lines = read_text_any(Path(path)).split("\n")
    out = OrderedDict(file=str(path), markers=[], progress=[], convergence_blocks=OrderedDict(),
                      computation_order="", loops=OrderedDict(), executions=OrderedDict(), radfrac=OrderedDict(),
                      messages=[], error_summary=None, translation_note="", completed=False)
    cur_block = None
    cur_loop = None
    i, n = 0, len(lines)
    while i < n:
        l = lines[i]
        st = l.strip()
        m = re.match(r"^<<\s*(.*?)\s*>>", st)
        if m:
            out["markers"].append(m.group(1))
            i += 1
            continue
        if st.startswith("->"):
            out["progress"].append(st[2:].strip())
            if "Simulation calculations completed" in st:
                out["completed"] = True
            i += 1
            continue
        m = re.match(r"^\s*Block\s+(\S+)\s+\(Method:\s*([^)]+?)\s*\)\s+has been defined to converge", l)
        if m:
            what = lines[i + 1].strip() if i + 1 < n else ""
            out["convergence_blocks"][m.group(1)] = {"method": m.group(2).strip(), "converges": what}
            i += 2
            continue
        if st.startswith("COMPUTATION ORDER FOR THE FLOWSHEET"):
            j = i + 1
            parts = []
            while j < n and lines[j].strip() and not lines[j].strip().startswith("->"):
                parts.append(lines[j].strip())
                j += 1
            out["computation_order"] = " / ".join(parts)
            i = j
            continue
        m = LOOP_RX.match(l)
        if m:
            depth, kind, name, method, it = len(m.group(1)), m.group(2), m.group(3), m.group(4), m.group(5)
            lp = out["loops"].setdefault(name, {"method": method, "depth": depth, "starts": 0, "iterations": 0,
                                                "max_iteration": 0, "last": "", "converged": None, "converges": ""})
            if kind.startswith("Beginning"):
                lp["starts"] += 1
            else:
                lp["iterations"] += 1
                lp["max_iteration"] = max(lp["max_iteration"], int(it or 0))
            cur_loop = name
            cur_block = None
            i += 1
            continue
        if cur_loop and re.match(r"^\s*Converging (tear streams|specs)\s*:", l):
            out["loops"][cur_loop]["converges"] = st.split(":", 1)[1].strip()
            i += 1
            continue
        m = re.match(r"^\s*(?:(\d+)\s+vars not converged|#\s*Converged)\s*,?\s*Max Err/Tol\s+([-+0-9.E]+)", l, re.I)
        if m and cur_loop:
            lp = out["loops"][cur_loop]
            lp["last"] = st
            lp["converged"] = m.group(1) is None
            lp["max_err_tol"] = m.group(2)
            i += 1
            continue
        m = BLOCK_RX.match(l)
        if m:
            cur_block = m.group(1)
            ex = out["executions"].setdefault(cur_block, {"model": m.group(2), "count": 0})
            ex["count"] += 1
            i += 1
            continue
        m = CALC_RX.match(l)
        if m:
            cur_block = m.group(1)
            ex = out["executions"].setdefault(cur_block, {"model": "CALCULATOR", "count": 0})
            ex["count"] += 1
            i += 1
            continue
        if st.startswith("Convergence iterations:") and cur_block:
            j = i + 1
            rows = []
            while j < n and lines[j].strip() and not lines[j].strip().startswith(("Block:", "*", "->", ">")):
                toks = lines[j].split()
                if toks and toks[0].isdigit():
                    rows.append(toks)
                j += 1
            if rows:
                out["radfrac"][cur_block] = {"iterations": len(rows), "last": " ".join(rows[-1])}
            i = j
            continue
        if "Summary of Simulation Errors" in st:
            tab = {}
            for j in range(i + 1, min(i + 10, n)):
                mm = re.match(r"^\s*(Terminal Errors|Severe Errors|Errors|Warnings)\s+(\d+)\s+(\d+)\s+(\d+)", lines[j], re.I)
                if mm:
                    tab[mm.group(1).lower()] = {"physical_property": int(mm.group(2)), "system": int(mm.group(3)),
                                                "simulation": int(mm.group(4))}
            out["error_summary"] = tab
            i += 1
            continue
        if re.search(r"were issued during Input Translation", st, re.I):
            out["translation_note"] = st.strip("* ").strip()
            i += 1
            continue
        hm = HEAD_RX.match(l)
        if hm:
            sev = hm.group(2)
            context = (hm.group(3) or "").strip()
            body = []
            j = i + 1
            # the .cpm drops the '(ID)' line of two-line headers and leaves a blank line in its place
            if j + 1 < n and not lines[j].strip() and lines[j + 1].startswith("      ") \
                    and not HEAD_RX.match(lines[j + 1]):
                j += 1
            while j < n and lines[j].strip() and not HEAD_RX.match(lines[j]) and not BLOCK_RX.match(lines[j]) \
                    and not CALC_RX.match(lines[j]) and not LOOP_RX.match(lines[j]) and lines[j].startswith("   ") \
                    and len(body) < 20:
                body.append(lines[j].strip())
                j += 1
            where = f"block {cur_block}" if cur_block else (context.lower() or "input processing")
            out["messages"].append({"severity": sev, "context": context, "where": where, "body": body,
                                    "loop": cur_loop})
            i = j
            continue
        i += 1
    out["message_groups"] = _group(out["messages"])
    return out


def _group(msgs: List[dict]) -> List[dict]:
    g: "OrderedDict[tuple, dict]" = OrderedDict()
    for m in msgs:
        first = m["body"][0] if m["body"] else m["context"]
        key = (m["severity"], m["where"], first[:60])
        e = g.setdefault(key, {"severity": m["severity"], "where": m["where"], "first_line": first, "count": 0})
        e["count"] += 1
    out = list(g.values())
    out.sort(key=lambda x: -SEV_ORDER.get(x["severity"], 0))
    return out


def render_markdown(d: dict) -> str:
    L = [f"# Control panel: {Path(d['file']).name}"]
    if d["markers"]:
        L.append("- " + "; ".join(d["markers"]))
    status = "completed" if d["completed"] else "NOT completed (no 'Simulation calculations completed' line)"
    es = d["error_summary"]
    if es:
        tot = {k: sum(v.values()) for k, v in es.items()}
        status += " - " + ", ".join(f"{v} {k}" for k, v in tot.items() if v) if any(tot.values()) else \
            " - no errors or warnings in simulation"
    L.append(f"- Status: {status}")
    if d["translation_note"]:
        L.append(f"- Input translation: {d['translation_note']}")
    if d["convergence_blocks"]:
        L.append("- Convergence blocks: " + "; ".join(f"{k} ({v['method']}) {v['converges']}"
                                                    for k, v in d["convergence_blocks"].items()))
    if d["computation_order"]:
        L.append(f"- Computation order: {d['computation_order']}")
    if d["loops"]:
        L.append("")
        L.append("## Convergence loops")
        L.append("| Loop | Method | Nest level | Starts | Iterations (total / max) | Last state |")
        L.append("|---|---|---|---|---|---|")
        for k, v in d["loops"].items():
            state = "converged" if v["converged"] else ("NOT converged" if v["converged"] is False else "?")
            L.append(f"| {k} | {v['method']} | {v['depth']} | {v['starts']} | {v['iterations']} / {v['max_iteration']} | "
                     f"{state} (max err/tol {v.get('max_err_tol', '?')}) |")
    if d["radfrac"]:
        L.append("")
        L.append("## Column iterations (last row: OL ML IL Err/Tol)")
        for k, v in d["radfrac"].items():
            L.append(f"- {k}: {v['iterations']} rows, last: {v['last']}")
    if d["message_groups"]:
        L.append("")
        L.append("## Messages (the .cpm has no message IDs; see the .his for IDs)")
        L.append("| Severity | Where | Count | First line |")
        L.append("|---|---|---|---|")
        for g in d["message_groups"]:
            L.append(f"| {g['severity']} | {g['where']} | {g['count']} | {g['first_line'][:110]} |")
    return "\n".join(L)
