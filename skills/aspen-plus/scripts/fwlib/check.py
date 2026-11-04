"""Checks on stream results: block mass balances, element balances, charge balance, apparent vs true
basis, and user-defined metrics.

Input is a report export (.rep) or a stream table copied from Aspen Plus (Stream Results / Stream
Summary grid, pasted into a text file: tab-separated rows 'label <tab> unit <tab> value ...').
The arithmetic is done here, in code, so answers do not rely on numbers retyped from a table.
"""
from __future__ import annotations

import ast
import operator
import re
from collections import OrderedDict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from . import rep
from .bkp import charge_of
from .common import fmt_num, read_text_any
from .inp import formula_elements

# ---------------------------------------------------------------------------
# reading tables
# ---------------------------------------------------------------------------
STATE_ROWS = {"temperature": "T", "pressure": "P", "molar vapor fraction": "VFRAC", "vapor frac": "VFRAC",
              "phase": "PHASE", "from": "FROM", "to": "TO", "ph": "PH"}


def _f(x) -> Optional[float]:
    if x is None:
        return None
    s = str(x).strip().replace("D", "E")
    if not s or s in ("----", "MISSING"):
        return None
    try:
        return float(s)
    except ValueError:
        return rep.to_float(s)  # report style '7.0000-02'


def _new_stream():
    return {"FROM": "", "TO": "", "PHASE": "", "T": None, "P": None, "VFRAC": None, "PH": None,
            "mole": OrderedDict(), "mass": OrderedDict(), "mole_unit": "", "mass_unit": "",
            "mole_total": None, "mass_total": None}


def from_rep(path) -> "OrderedDict[str, dict]":
    d = rep.parse(path)
    out: "OrderedDict[str, dict]" = OrderedDict()
    for name, st in d["streams"].items():
        s = _new_stream()
        s["FROM"], s["TO"] = (st.get("FROM", "").strip("-"), st.get("TO", "").strip("-"))  # '----' = none
        s["PHASE"] = st.get("MIXED|PHASE", "")
        for k, v in st.items():
            parts = k.split("|")
            lab = parts[-1]
            if len(parts) >= 3 and parts[1].startswith("COMPONENTS:"):
                unit = parts[1].split(":", 1)[1].strip().lower()
                if "frac" in unit:
                    continue
                kind = "mole" if "mol" in unit else "mass"
                if parts[0] != "MIXED" and kind in ("mole", "mass"):
                    continue
                val = _f(v)
                if val is not None:
                    s[kind][lab] = val
                    s[kind + "_unit"] = unit
            elif len(parts) >= 2 and parts[-2] == "TOTAL FLOW" and parts[0] == "MIXED":
                unit = lab.lower()
                if "mol" in unit and s["mole_total"] is None:
                    s["mole_total"] = _f(v)
                    s["mole_unit"] = s["mole_unit"] or unit
                elif ("kg" in unit or "lb" in unit) and "cum" not in unit and s["mass_total"] is None:
                    s["mass_total"] = _f(v)
                    s["mass_unit"] = s["mass_unit"] or unit
            elif parts[0] == "MIXED" and lab.startswith("TEMP ") and s["T"] is None:
                s["T"] = _f(v)
            elif parts[0] == "MIXED" and lab.startswith("PRES ") and s["P"] is None:
                s["P"] = _f(v)
            elif parts[0] == "MIXED" and lab == "VFRAC" and s["VFRAC"] is None:
                s["VFRAC"] = _f(v)
        out[name] = s
    return out


FIRST_ROW_LABELS = {"description", "from", "to", "stream class", "phase", "temperature", "mixed substream",
                    "total flow", "maximum relative error"}


def _reflow(text: str) -> str:
    """A table whose line breaks were lost (pasted through a chat box): one long tab-separated line.
    Rebuild rows of 2 + n cells, n = number of stream names after 'Units'."""
    cells = text.split("\t")
    try:
        u = next(i for i, c in enumerate(cells) if c.strip().lower() == "units")
    except StopIteration:
        return text
    n = 0
    while u + 1 + n < len(cells) and cells[u + 1 + n].strip().lower() not in FIRST_ROW_LABELS:
        n += 1
    if not n:
        return text
    rows = ["\t".join([""] + ["Units"] + cells[u + 1:u + 1 + n])]
    rest = cells[u + 1 + n:]
    for k in range(0, len(rest), n + 2):
        rows.append("\t".join(rest[k:k + n + 2]))
    return "\n".join(rows)


def from_text(text: str) -> "OrderedDict[str, dict]":
    """Parse a stream table copied from the Aspen Plus results grid (tab-separated)."""
    text = text.replace("\r\n", "\n")
    if text.count("\n") < 3 and text.count("\t") > 20:
        text = _reflow(text)
    lines = [l.rstrip("\n") for l in text.split("\n")]
    header_i, names = None, []
    for i, l in enumerate(lines):
        cells = l.split("\t")
        if len(cells) >= 3 and cells[1].strip().lower() == "units":
            header_i = i
            names = [c.strip() for c in cells[2:]]
            break
    if header_i is None:  # no tabs: try runs of 2+ spaces
        for i, l in enumerate(lines):
            cells = re.split(r"\s{2,}", l.strip())
            if len(cells) >= 2 and cells[0].lower() == "units":
                header_i, names = i, cells[1:]
                lines = [("\t".join([""] + re.split(r"\s{2,}", x.strip()))) for x in lines]
                break
    if header_i is None:
        raise ValueError("no header row with 'Units' found: copy the stream table including its first row")
    while names and not names[-1]:
        names.pop()
    out: "OrderedDict[str, dict]" = OrderedDict((n, _new_stream()) for n in names)
    section, sec_unit, done_sections = None, "", set()
    for l in lines[header_i + 1:]:
        cells = l.split("\t")
        if not any(c.strip() for c in cells):
            continue
        label, unit = cells[0].strip(), (cells[1].strip() if len(cells) > 1 else "")
        vals = [c.strip() for c in cells[2:2 + len(names)]]
        has_vals = any(v for v in vals)
        low = label.lower()
        if low.endswith(" phase") and not has_vals:  # 'Liquid Phase' sub-tables: totals already read
            break
        if low in ("mole flows", "mass flows"):
            kind = "mole" if low.startswith("mole") else "mass"
            section = kind if kind not in done_sections else None
            sec_unit = unit
            if section:
                for n, v in zip(names, vals):
                    out[n][kind + "_total"] = _f(v)
                    out[n][kind + "_unit"] = unit
            continue
        if section and unit == sec_unit and label and label.lower() not in STATE_ROWS:
            for n, v in zip(names, vals):
                fv = _f(v)
                if fv is not None:
                    out[n][section][label] = fv
            continue
        if section:
            done_sections.add(section)
            section = None
        key = STATE_ROWS.get(low)
        if key:
            for n, v in zip(names, vals):
                if key in ("FROM", "TO", "PHASE"):
                    out[n][key] = v
                elif out[n][key] is None:
                    out[n][key] = _f(v)
    return out


def load(path) -> "OrderedDict[str, dict]":
    p = Path(path)
    if p.suffix.lower() == ".rep":
        return from_rep(p)
    return from_text(read_text_any(p))


# ---------------------------------------------------------------------------
# formulas
# ---------------------------------------------------------------------------
def aliases_from(path) -> Dict[str, str]:
    """Component ID -> databank alias from a .his, .inp or .bkp."""
    p = Path(path)
    if p.suffix.lower() == ".bkp":
        from . import bkp
        return {c["id"].upper(): c.get("alias") or "" for c in bkp.parse(p)["components"]}
    from . import his
    text = his.echo_text(his.parse(p)) if p.suffix.lower() == ".his" else read_text_any(p)
    model = his.parse_input_language(text.split("\n"))
    out = {c["id"].upper(): c.get("databank_name") or "" for c in model["components"]}
    for par in his.paragraphs(text.split("\n")):  # user-defined components: 'formula' is only a name
        if par["key"] == "FORMULA":
            for entry in " ".join([par["header"][len("FORMULA"):]] + par["statements"]).split("/"):
                w = entry.split()
                if w and w[0].upper() in out:
                    out[w[0].upper()] = "?"  # no usable formula
    return out


def formulas(comps: List[str], aliases: Dict[str, str], overrides: Dict[str, str]) -> Tuple[Dict, List[str]]:
    out, guessed = {}, []
    for c in comps:
        u = c.upper()
        if u in overrides:
            fe = formula_elements(overrides[u], c)
        elif aliases.get(u) == "?":
            fe = None
        elif aliases.get(u):
            fe = formula_elements(aliases[u], c)
        else:
            fe = formula_elements(c, c)
            if fe:
                guessed.append(c)
        if fe:
            out[u] = fe
    return out, guessed


# ---------------------------------------------------------------------------
# checks
# ---------------------------------------------------------------------------
def _ions(streams) -> List[str]:
    comps = OrderedDict()
    for s in streams.values():
        for c in s["mole"]:
            comps[c] = 1
        for c in s["mass"]:
            comps[c] = 1
    return [c for c in comps if charge_of(c)]


def analyse(streams, elements: List[str] = None, aliases: Dict[str, str] = None,
            overrides: Dict[str, str] = None, metrics: List[Tuple[str, str]] = None, rel_tol: float = 1e-4) -> dict:
    elements = [e.upper() for e in (elements or [])]
    aliases = aliases or {}
    overrides = {k.upper(): v for k, v in (overrides or {}).items()}
    res = {"streams": OrderedDict(), "blocks": OrderedDict(), "flags": [], "elements": elements,
           "element_table": OrderedDict(), "metrics": [], "guessed_formulas": []}
    all_comps = OrderedDict()
    for s in streams.values():
        for c in list(s["mole"]) + list(s["mass"]):
            all_comps[c] = 1
    fml, guessed = formulas(list(all_comps), aliases, overrides)
    res["guessed_formulas"] = guessed
    ions = [c for c in all_comps if charge_of(c)]
    # basis
    if ions:
        nz = [c for c in ions if any(abs(s["mole"].get(c, 0)) > 0 or abs(s["mass"].get(c, 0)) > 0
                                     for s in streams.values())]
        if not nz:
            res["flags"].append("All ionic species are zero in every stream. Either the table is on the apparent "
                                "basis (ions reconstituted into molecular/salt components; switch to the "
                                "true-component approach to see speciation), or the electrolyte chemistry is not "
                                "active (no Chemistry ID on the property method). Charge balance and speciation "
                                "cannot be checked from this table.")
    # per stream
    for n, s in streams.items():
        row = OrderedDict(FROM=s["FROM"], TO=s["TO"], PHASE=s["PHASE"], T=s["T"], P=s["P"], VFRAC=s["VFRAC"],
                          mole_total=s["mole_total"] if s["mole_total"] is not None else (sum(s["mole"].values()) or None),
                          mass_total=s["mass_total"] if s["mass_total"] is not None else (sum(s["mass"].values()) or None),
                          mole_unit=s["mole_unit"], mass_unit=s["mass_unit"])
        if row["mole_total"] == 0 and row["mass_total"] is None:  # empty stream (e.g. no vapour formed)
            row["mass_total"] = 0.0
        if ions and s["mole"]:
            pos = sum(v * charge_of(c) for c, v in s["mole"].items() if charge_of(c) > 0)
            neg = -sum(v * charge_of(c) for c, v in s["mole"].items() if charge_of(c) < 0)
            if pos or neg:
                row["charge"] = {"positive": pos, "negative": neg, "net": pos - neg,
                                 "rel": (pos - neg) / max(pos, neg)}
                if abs(row["charge"]["rel"]) > 1e-6:
                    res["flags"].append(f"Stream {n} is not electroneutral: net charge {fmt_num(pos - neg)} "
                                        f"{s['mole_unit']} ({row['charge']['rel']:+.2e} relative)")
        if elements and s["mole"]:
            el = OrderedDict()
            missing = [c for c, v in s["mole"].items() if v and c.upper() not in fml]
            for e in elements:
                el[e] = sum(v * fml.get(c.upper(), {}).get(e, 0) for c, v in s["mole"].items())
            res["element_table"][n] = {"values": el, "unknown": missing}
        res["streams"][n] = row
    # per block
    blocks = OrderedDict()
    for n, s in streams.items():
        if s["TO"]:
            blocks.setdefault(s["TO"], {"in": [], "out": []})["in"].append(n)
        if s["FROM"]:
            blocks.setdefault(s["FROM"], {"in": [], "out": []})["out"].append(n)
    for b, io in blocks.items():
        r = OrderedDict(inlets=io["in"], outlets=io["out"])
        if not io["in"] or not io["out"]:
            r["note"] = "inlets or outlets not in this table - no balance"
            res["blocks"][b] = r
            continue
        mi = [res["streams"][x]["mass_total"] for x in io["in"]]
        mo = [res["streams"][x]["mass_total"] for x in io["out"]]
        if None not in mi and None not in mo:
            a, z = sum(mi), sum(mo)
            r["mass_in"], r["mass_out"] = a, z
            r["mass_rel"] = (z - a) / a if a else None
            if a and abs(r["mass_rel"]) > rel_tol:
                res["flags"].append(f"Block {b}: mass out differs from mass in by {r['mass_rel']:+.2e} "
                                    "(check heat/work streams are not counted, or a stream is missing from the table)")
        if elements:
            eb = OrderedDict()
            unknown = sorted({c for x in io["in"] + io["out"] for c in res["element_table"].get(x, {}).get("unknown", [])})
            for e in elements:
                vin = sum(res["element_table"].get(x, {}).get("values", {}).get(e, 0) for x in io["in"])
                vout = sum(res["element_table"].get(x, {}).get("values", {}).get(e, 0) for x in io["out"])
                eb[e] = {"in": vin, "out": vout, "rel": (vout - vin) / vin if vin else None}
                if vin and abs((vout - vin) / vin) > rel_tol and not unknown:
                    res["flags"].append(f"Block {b}: element {e} does not balance ({(vout - vin) / vin:+.2e})")
            r["elements"] = eb
            if unknown:
                r["note"] = ("element balance incomplete: no formula for " + ", ".join(unknown[:8])
                             + " (pass --formula ID=FORMULA)")
        res["blocks"][b] = r
    # metrics
    for name, expr in (metrics or []):
        try:
            val = evaluate(expr, streams, fml)
            res["metrics"].append({"name": name, "expr": expr, "value": val})
        except Exception as e:
            res["metrics"].append({"name": name, "expr": expr, "error": str(e)})
    return res


_FN_RX = re.compile(r"\b(flow|massflow|elem|mole|mass)\(([^()]*)\)", re.I)
_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
        ast.Pow: operator.pow, ast.USub: operator.neg, ast.UAdd: operator.pos}


def evaluate(expr: str, streams, fml) -> float:
    """Evaluate a metric. Functions: flow(STREAM, C1 C2 ...) mole flow summed over components,
    massflow(STREAM, C ...), elem(STREAM, C) moles of an element, mole(STREAM), mass(STREAM).
    Example: flow(GAS-OUT, CO2) / elem(FEED, C)"""
    lut = {k.upper(): k for k in streams}

    def stream(name):
        k = lut.get(name.strip().upper())
        if k is None:
            raise ValueError(f"no stream {name.strip()} in the table")
        return streams[k]

    def fn(m):
        f = m.group(1).lower()
        args = [a.strip() for a in m.group(2).split(",")]
        s = stream(args[0])
        comps = args[1].split() if len(args) > 1 else []
        if f == "flow":
            v = sum(_comp(s["mole"], c) for c in comps)
        elif f == "massflow":
            v = sum(_comp(s["mass"], c) for c in comps)
        elif f == "elem":
            e = comps[0].upper()
            v = sum(val * fml.get(c.upper(), {}).get(e, 0) for c, val in s["mole"].items())
        elif f == "mole":
            v = s["mole_total"] if s["mole_total"] is not None else sum(s["mole"].values())
        else:
            v = s["mass_total"] if s["mass_total"] is not None else sum(s["mass"].values())
        return repr(float(v))

    num_expr = _FN_RX.sub(fn, expr)
    tree = ast.parse(num_expr, mode="eval")

    def ev(node):
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](ev(node.left), ev(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](ev(node.operand))
        raise ValueError("only numbers, + - * / ** and flow()/massflow()/elem()/mole()/mass() are allowed")
    return float(ev(tree))


def _comp(d: Dict[str, float], c: str) -> float:
    for k, v in d.items():
        if k.upper() == c.upper():
            return v
    raise ValueError(f"component {c} not in the table")


def render(res: dict) -> str:
    L = ["# Stream checks"]
    if res["flags"]:
        L.append("")
        L.append("## Findings")
        for f in res["flags"]:
            L.append(f"- {f}")
    else:
        L.append("\nNo balance or electroneutrality problems found in this table.")
    L.append("")
    L.append("## Streams")
    has_charge = any("charge" in r for r in res["streams"].values())
    head = "| Stream | From -> To | Phase | T | P | Mole flow | Mass flow |" + (" Net charge |" if has_charge else "")
    L.append(head)
    L.append("|" + "---|" * (head.count("|") - 1))
    for n, r in res["streams"].items():
        ch = ""
        if has_charge:
            ch = f" {r['charge']['rel']:+.1e} |" if "charge" in r else " |"
        L.append(f"| {n} | {r['FROM'] or '(feed)'} -> {r['TO'] or '(product)'} | {r['PHASE']} | {fmt_num(r['T'])} | "
                 f"{fmt_num(r['P'])} | {fmt_num(r['mole_total'])} {r['mole_unit']} | {fmt_num(r['mass_total'])} "
                 f"{r['mass_unit']} |" + ch)
    if res["blocks"]:
        L.append("")
        L.append("## Block balances")
        for b, r in res["blocks"].items():
            line = f"- {b}: in {' '.join(r['inlets']) or '-'} -> out {' '.join(r['outlets']) or '-'}"
            if r.get("note"):
                line += f" ({r['note']})"
            if r.get("mass_rel") is not None:
                line += f"; mass {fmt_num(r['mass_in'])} -> {fmt_num(r['mass_out'])} ({r['mass_rel']:+.1e})"
            for e, v in (r.get("elements") or {}).items():
                line += f"; {e} {fmt_num(v['in'])} -> {fmt_num(v['out'])}" + (
                    f" ({v['rel']:+.1e})" if v["rel"] is not None else "")
            L.append(line)
    if res["element_table"]:
        L.append("")
        L.append("## Element flows (mole basis)")
        els = res["elements"]
        L.append("| Stream | " + " | ".join(els) + " | Components without formula |")
        L.append("|---|" + "---|" * (len(els) + 1))
        for n, r in res["element_table"].items():
            L.append(f"| {n} | " + " | ".join(fmt_num(r["values"][e]) for e in els) + f" | {' '.join(r['unknown'])} |")
        if res["guessed_formulas"]:
            L.append(f"\nFormulas read from the component IDs (pass --model <.his/.inp/.bkp> or --formula ID=FORMULA "
                     f"to be sure): {', '.join(res['guessed_formulas'])}")
    if res["metrics"]:
        L.append("")
        L.append("## Metrics")
        for m in res["metrics"]:
            L.append(f"- {m['name']} = {fmt_num(m['value'], 6)}" if "value" in m else
                     f"- {m['name']}: error: {m['error']}")
    return "\n".join(L)
