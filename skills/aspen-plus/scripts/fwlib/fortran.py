"""Check a calculator's Fortran kept as a plain-text file (templates/fortran-calculator.txt).

The file is what the user pastes into the Calculator's Fortran sheet: a header of comment lines
(name, version, purpose, the Define table, Parameters, Declarations, rules) and the code.

Lint: fixed form (statements in columns 7-72, C comments in column 1, labels in columns 2-5,
continuation mark in column 6), no tabs, names starting with I-N holding real values, and, when the
header lists the Define table, names that are neither defined nor set (the checks of
his.fortran_lint). Compile: when gfortran is on PATH, the code is compiled in a harness with
-ffixed-form -Wall; otherwise the report says it was not compiled.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional

from . import his
from .common import read_text_any

COMMENT = ("C", "c", "*")
REAL_LITERAL = re.compile(r"(?<![A-Z0-9_])(\d+\.\d*|\.\d+|\d+[ED][+-]?\d+)", re.I)
REAL_FUNCS = re.compile(r"\b(DEXP|DLOG|DLOG10|DSQRT|DABS|DSIN|DCOS|DTAN|EXP|LOG|LOG10|SQRT|ABS|DBLE|"
                        r"DMAX1|DMIN1|AMAX1|AMIN1)\s*\(", re.I)
HEAD_KEYS = {"calculator": "name", "name": "name", "version": "version", "purpose": "purpose", "model": "model"}


def _is_comment(line: str) -> bool:
    return not line.strip() or line[:1] in COMMENT


def parse(text: str) -> dict:
    """Header fields, the Define table, Parameters and Declarations from the leading comments."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    head = {"name": "", "version": "", "purpose": "", "model": ""}
    defines: List[dict] = []
    params: List[str] = []
    declared: set = set()
    declarations: List[str] = []
    section = ""
    has_define_table = False
    for raw in lines:
        if not _is_comment(raw):
            break                                       # the header ends at the first statement
        body = raw[1:].strip() if raw[:1] in COMMENT else raw.strip()
        if not body or set(body) <= set("=-*_ "):
            continue
        low = body.lower()
        if re.match(r"^define\b", low):
            section, has_define_table = "define", True
            continue
        if re.match(r"^parameters?\b", low):
            section = "parameters"
            rest = body.split(":", 1)[1].strip() if ":" in body else ""
            if rest and rest.lower() != "none":
                params.append(rest)
            continue
        if re.match(r"^declarations?\b", low):
            section = "declarations"
            rest = body.split(":", 1)[1].strip() if ":" in body else ""
            if _declared_names(rest):
                declared |= _declared_names(rest)
                declarations.append(rest)
            continue
        if re.match(r"^rules?\b", low):
            section = "rules"
            continue
        for m in re.finditer(r"(?:^|\s{2,})(Calculator|Name|Version|Purpose|Model)\s*:\s*(.*?)(?=\s{2,}\w+\s*:|$)",
                             body, re.I):
            key = HEAD_KEYS[m.group(1).lower()]
            if m.group(2).strip() and not head[key]:
                head[key] = m.group(2).strip()
        if section == "define" and "|" in body:
            cells = [c.strip() for c in body.split("|")]
            if cells[0] and re.match(r"^[A-Za-z][A-Za-z0-9_]*$", cells[0]):
                flow = cells[1].lower() if len(cells) > 1 else ""
                defines.append({"name": cells[0].upper(),
                                "flow": "import" if flow.startswith(("imp", "read")) else
                                        "export" if flow.startswith(("exp", "writ")) else flow,
                                "type": cells[2] if len(cells) > 2 else "",
                                "definition": cells[3] if len(cells) > 3 else "",
                                "units": cells[4] if len(cells) > 4 else ""})
        elif section == "parameters" and body.lower() != "none":
            params.append(body)
        elif section == "declarations" and _declared_names(body):
            declared |= _declared_names(body)
            declarations.append(body)
    return {"lines": lines, "header": head, "defines": defines, "parameters": params, "declared": declared,
            "declarations": declarations, "has_define_table": has_define_table}


def _declared_names(text: str) -> set:
    m = re.match(r"^\s*(?:REAL\s*\*\s*8|DOUBLE\s+PRECISION|REAL|INTEGER|LOGICAL)\s+(.*)$", text, re.I)
    if not m:
        return set()
    return {re.sub(r"\(.*", "", n).strip().upper() for n in m.group(1).split(",") if n.strip()}


_NAME_CHECKS = ("uses names", "used before being set", "assigns to imported", "exported (write)", "imported variables")


def _level(msg: str) -> str:
    if msg.startswith(("tab character", "text past column 72", "statement starts before column 7",
                       "assigns to imported")):
        return "error"
    if msg.startswith("imported variables never used"):
        return "note"
    return "warning"


def lint(p: dict) -> List[dict]:
    """Findings: {level, line, message}; line 0 when the finding is about the whole file."""
    out: List[dict] = []
    lines = p["lines"]
    code_lines = []
    for n, raw in enumerate(lines, 1):
        if _is_comment(raw):
            continue
        code_lines.append(n)
        if raw[:1] == "F" and raw[1:2] == " ":
            out.append({"level": "error", "line": n, "message": "'F' in column 1 is the input-file marker of "
                        "inline Fortran: paste the code into the Fortran sheet without it"})
        elif raw[:1].isdigit():
            out.append({"level": "warning", "line": n, "message": "label in column 1: put labels in columns 2-5 "
                        "(column 1 is for C comments)"})
        code = re.sub(r"'[^']*'", "''", raw[:72])
        if "!" in code[6:]:
            out.append({"level": "warning", "line": n, "message": "'!' comment: not standard fixed form; write the "
                        "comment on its own line with C in column 1"})
    if not code_lines:
        out.append({"level": "error", "line": 0, "message": "no Fortran statements (only comments)"})
    obj = {"fortran": [_strip_bang((" " + l[1:]) if (l[:1] == "F" and l[1:2] == " ") else l) for l in lines],
           "defines": [{"name": d["name"]} for d in p["defines"]],
           "read_vars": [d["name"] for d in p["defines"] if d["flow"] == "import"],
           "write_vars": [d["name"] for d in p["defines"] if d["flow"] == "export"]}
    tabs = set()
    for msg in his.fortran_lint(obj):
        if not p["has_define_table"] and msg.startswith(_NAME_CHECKS):
            continue                                    # no Define table in the header: names unknown
        m = re.match(r"^line (\d+): (.*)$", msg)
        line, text = (int(m.group(1)), m.group(2)) if m else (0, msg)
        if text.startswith("tab character"):
            tabs.add(line)
        elif text.startswith("statement starts before column 7") and line in tabs:
            continue                                    # the tab is the cause
        out.append({"level": _level(text), "line": line, "message": text})
    out += _integer_names(p)
    if not p["has_define_table"]:
        out.append({"level": "note", "line": 0, "message": "the header has no Define table: names were not "
                    "checked against it (templates/fortran-calculator.txt shows the layout)"})
    order = {"error": 0, "warning": 1, "note": 2}
    return sorted(out, key=lambda f: (order[f["level"]], f["line"]))


def _strip_bang(line: str) -> str:
    """The line without a '!' comment (outside quotes), for the name checks."""
    if _is_comment(line) or "!" not in line:
        return line
    quoted = False
    for i, ch in enumerate(line):
        if ch == "'":
            quoted = not quoted
        elif ch == "!" and not quoted and i >= 6:
            return line[:i].rstrip()
    return line


def _integer_names(p: dict) -> List[dict]:
    """Names starting with I-N are INTEGER unless declared: flag those that hold real values."""
    out = []
    real_defines = {d["name"] for d in p["defines"]}
    seen = set()
    for d in p["defines"]:
        if d["name"][:1] in "IJKLMN" and d["name"] not in p["declared"]:
            out.append({"level": "warning", "line": 0, "message": f"Define variable {d['name']} starts with I-N: a "
                        "local copy of it is an INTEGER unless declared; prefer a name starting A-H or O-Z"})
            seen.add(d["name"])
    for n, raw in enumerate(p["lines"], 1):
        if _is_comment(raw) or (len(raw) > 5 and raw[5] not in " 0"):
            continue
        st = re.sub(r"^\s*\d+\s+", "", raw[6:72]).strip()
        m = re.match(r"^(?:IF\s*\(.*\)\s*)?([A-Za-z][A-Za-z0-9_]*)\s*=\s*(.+)$", st, re.I)
        if not m or re.match(r"^DO\b", st, re.I):
            continue
        name, rhs = m.group(1).upper(), m.group(2)
        if name[:1] not in "IJKLMN" or name in p["declared"] or name in seen:
            continue
        rhs_names = set(re.findall(r"[A-Z][A-Z0-9_]*", rhs.upper()))
        if REAL_LITERAL.search(rhs) or REAL_FUNCS.search(rhs) or rhs_names & real_defines or "/" in rhs:
            out.append({"level": "warning", "line": n, "message": f"{name} starts with I-N, so it is an INTEGER: "
                        "the real value assigned here is truncated. Rename it (A-H, O-Z) or declare it REAL*8 "
                        "in the Declarations sheet"})
            seen.add(name)
    return out


# ---------------------------------------------------------------------------
# compiling (gfortran)
# ---------------------------------------------------------------------------
def harness(p: dict) -> (str, int):
    """A subroutine around the code, as Aspen compiles it: Define variables as arguments in double
    precision, implicit double precision for A-H and O-Z. Returns the text and the line offset."""
    names = [d["name"] for d in p["defines"]]
    head = ["      SUBROUTINE PSACAL(" + ", ".join(names) + ")" if names else "      SUBROUTINE PSACAL",
            "      IMPLICIT DOUBLE PRECISION (A-H, O-Z)"]
    if names:
        head.append("      DOUBLE PRECISION " + ", ".join(names))
    head += ["      " + d for d in p.get("declarations", [])]          # the Declarations sheet
    # wrap long argument lists with continuation lines (column 6)
    wrapped = []
    for l in head:
        while len(l) > 72:
            wrapped.append(l[:72])
            l = "     &" + l[72:]
        wrapped.append(l)
    body = []
    for l in p["lines"]:
        if re.match(r"^\s+INCLUDE\b", l, re.I):
            body.append("C     (INCLUDE left out by the harness) " + l.strip()[:30])
        elif l[:1] == "F" and l[1:2] == " ":
            body.append(" " + l[1:])
        else:
            body.append(l)
    text = "\n".join(wrapped + body + ["      RETURN", "      END", ""])
    return text, len(wrapped)


def compile_check(p: dict, gfortran: Optional[str] = None, timeout: int = 60) -> dict:
    exe = gfortran or shutil.which("gfortran")
    if not exe:
        return {"compiled": False, "reason": "gfortran is not on PATH: not compiled. Install it (MinGW-w64, MSYS2 "
                "or a package manager) or test the code as in calculators.md section 10"}
    text, offset = harness(p)
    tmp = tempfile.mkdtemp(prefix="psa-fortran-")
    try:
        src = os.path.join(tmp, "calc.f")
        with open(src, "w", encoding="latin-1", errors="replace", newline="\n") as fh:
            fh.write(text)
        cmd = [exe, "-ffixed-form", "-Wall", "-c", src, "-o", os.path.join(tmp, "calc.o")]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, errors="replace", timeout=timeout, cwd=tmp,
                               env=dict(os.environ, LC_ALL="C", LANG="C"))
        except (OSError, subprocess.SubprocessError) as e:
            return {"compiled": False, "reason": f"gfortran could not run: {e}"}
        version = ""
        try:
            v = subprocess.run([exe, "--version"], capture_output=True, text=True, errors="replace", timeout=30)
            version = v.stdout.splitlines()[0] if v.stdout else ""
        except (OSError, subprocess.SubprocessError, IndexError):
            pass
        msgs = _gfortran_messages(r.stderr, offset)
        return {"compiled": True, "ok": r.returncode == 0, "version": version,
                "flags": "-ffixed-form -Wall", "messages": msgs}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _gfortran_messages(stderr: str, offset: int) -> List[dict]:
    """'calc.f:12:10:' ... 'Warning: ...' -> {line (in the .txt), level, message}."""
    out, loc = [], None
    for l in stderr.splitlines():
        m = re.match(r"^.*?calc\.f:(\d+):(\d+)?:?\s*$", l)
        if m:
            loc = int(m.group(1)) - offset
            continue
        m = re.match(r"^(Error|Warning|Fatal Error):\s*(.*)$", l)
        if m:
            line = loc if loc and loc > 0 else 0
            out.append({"level": "error" if "Error" in m.group(1) else "warning", "line": line,
                        "message": m.group(2).strip()})
            loc = None
    return out


def check_file(path, gfortran: Optional[str] = None, compile_code: bool = True) -> dict:
    text = read_text_any(Path(path))
    p = parse(text)
    res = {"file": str(path), "header": p["header"], "defines": p["defines"], "parameters": p["parameters"],
           "lint": lint(p)}
    res["compile"] = compile_check(p, gfortran) if compile_code else {"compiled": False, "reason": "--no-compile"}
    return res


def render(res: dict) -> str:
    h = res["header"]
    title = " ".join(x for x in (h.get("name"), h.get("version")) if x) or Path(res["file"]).name
    L = [f"# Fortran check: {title} ({Path(res['file']).name})"]
    if h.get("purpose"):
        L.append(f"- Purpose: {h['purpose']}")
    if res["defines"]:
        L.append("- Define rows: " + ", ".join(f"{d['name']} ({d['flow'] or '?'}"
                                              + (f", {d['units']}" if d["units"] else "") + ")" for d in res["defines"]))
    L.append("")
    L.append("## Lint")
    if not res["lint"]:
        L.append("No findings.")
    for f in res["lint"]:
        where = f"line {f['line']}: " if f["line"] else ""
        L.append(f"- {f['level'].upper()} {where}{f['message']}")
    L.append("")
    L.append("## Compile")
    c = res["compile"]
    if not c.get("compiled"):
        L.append(f"Not compiled: {c.get('reason')}.")
    else:
        status = "compiles" if c["ok"] else "does NOT compile"
        L.append(f"{status} with {c.get('version') or 'gfortran'} ({c['flags']}, in a harness that declares the "
                 "Define variables as double precision arguments)" + (":" if c["messages"] else "; no warnings."))
        for m in c["messages"]:
            where = f"line {m['line']}: " if m["line"] else ""
            L.append(f"- {m['level'].upper()} {where}{m['message']}")
    return "\n".join(L)


def failed(res: dict) -> bool:
    c = res["compile"]
    return any(f["level"] == "error" for f in res["lint"]) or (c.get("compiled") and not c.get("ok"))

