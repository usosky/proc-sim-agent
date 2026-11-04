"""fortran-check: lint of a calculator's Fortran kept as a .txt file, and the gfortran harness."""
import os
import shutil
import subprocess
import sys

import pytest

from conftest import SCRIPTS, SKILL_DIR
from fwlib import check, fortran

TEMPLATES = SKILL_DIR / "templates"
GFORTRAN = shutil.which("gfortran")

BAD = """C Calculator: BAD   Version: v0.01
C Define (name | import/export | type | definition | units):
C   TIN | import | Stream-Var | STREAM=FEED VARIABLE=TEMP | C
C   XOUT | export | Block-Var | BLOCK=R1 VARIABLE=CONV |
      TIN = TIN + 1.0D0
\tXOUT = 0.5
      KRATE = TIN / 2.0D0
 10   CONTINUE
2     CONTINUE
      X = Y + 1.0   ! a comment
      Z = 1.0 + 2.0 + 3.0 + 4.0 + 5.0 + 6.0 + 7.0 + 8.0 + 9.0 + 10.0 + 11.0
F     W = 2.0D0
"""


def write(tmp_path, text, name="calc.txt"):
    f = tmp_path / name
    f.write_text(text, encoding="latin-1")
    return f


def messages(res, level=None):
    return [(f["line"], f["message"]) for f in res["lint"] if level is None or f["level"] == level]


def test_template_is_clean_and_compiles():
    res = fortran.check_file(TEMPLATES / "fortran-calculator.txt")
    assert res["header"]["name"] == "KPI" and res["header"]["version"] == "v1.03"
    assert [(d["name"], d["flow"], d["units"]) for d in res["defines"]] == [
        ("QREB", "import", "kW"), ("FCO2", "import", "kmol/hr"), ("SRD", "export", "GJ/t")]
    assert res["lint"] == []
    if GFORTRAN:
        assert res["compile"]["compiled"] and res["compile"]["ok"] and res["compile"]["messages"] == []
    else:
        assert "not on PATH" in res["compile"]["reason"]


def test_planted_mistakes_are_found(tmp_path):
    res = fortran.check_file(write(tmp_path, BAD), compile_code=False)
    errors = messages(res, "error")
    assert (0, "assigns to imported (read) variables - copy them to local names first (ADFORT.7): TIN") in errors
    assert (6, "tab character - use spaces (fixed-form Fortran)") in errors
    assert any(line == 11 and m.startswith("text past column 72") for line, m in errors)
    assert any(line == 12 and "input-file marker" in m for line, m in errors)
    assert not any(line == 6 and "before column 7" in m for line, m in errors)      # the tab explains it
    warnings = messages(res, "warning")
    assert any(line == 7 and m.startswith("KRATE starts with I-N") for line, m in warnings)
    assert any(line == 9 and m.startswith("label in column 1") for line, m in warnings)
    assert any(line == 10 and m.startswith("'!' comment") for line, m in warnings)
    assert any(m.startswith("uses names that are neither defined nor set") and "Y (line 10)" in m
               and "COMMENT" not in m for _, m in warnings)
    assert fortran.failed(res)
    md = fortran.render(res)
    assert "# Fortran check: BAD v0.01" in md and "Not compiled: --no-compile." in md


def test_no_define_table_skips_the_name_checks(tmp_path):
    res = fortran.check_file(write(tmp_path, "C plain code\n      A = B * 2.0D0\n"), compile_code=False)
    assert not any("neither defined" in m for _, m in messages(res))
    assert any("no Define table" in m for _, m in messages(res, "note"))
    assert not fortran.failed(res)


def test_declared_names_are_not_integer_warnings(tmp_path):
    text = ("C Define (name | import/export | type | definition | units):\n"
            "C   KTOT | export | Parameter | 2 | kmol/hr\n"
            "C Declarations: REAL*8 KTOT, NRAT\n"
            "      NRAT = 0.5D0\n      KTOT = NRAT * 2.0D0\n")
    res = fortran.check_file(write(tmp_path, text), compile_code=False)
    assert not any("I-N" in m for _, m in messages(res)), res["lint"]
    harness, _ = fortran.harness(fortran.parse(text))
    assert "      REAL*8 KTOT, NRAT" in harness


def test_not_compiled_without_gfortran(tmp_path, monkeypatch):
    monkeypatch.setattr(fortran.shutil, "which", lambda name: None)
    res = fortran.check_file(TEMPLATES / "fortran-calculator.txt")
    assert not res["compile"]["compiled"] and "gfortran is not on PATH: not compiled" in res["compile"]["reason"]
    assert "Not compiled: gfortran is not on PATH" in fortran.render(res)


def test_compiler_messages_map_to_lines_of_the_file(tmp_path, monkeypatch):
    p = fortran.parse(BAD)
    _, offset = fortran.harness(p)
    stderr = (f"/tmp/x/calc.f:{offset + 7}:10:\n\n    7 |       KRATE = TIN / 2.0D0\n      |          1\n"
              "Warning: Possible change of value in conversion from REAL(8) to INTEGER(4) at (1) [-Wconversion]\n"
              f"/tmp/x/calc.f:{offset + 12}:1:\n\nError: Non-numeric character in statement label at (1)\n")
    real_run = subprocess.run

    def fake_run(cmd, *a, **k):
        if "--version" in cmd:
            return subprocess.CompletedProcess(cmd, 0, "GNU Fortran (fake) 1.0\n", "")
        return subprocess.CompletedProcess(cmd, 1, "", stderr)
    monkeypatch.setattr(fortran.subprocess, "run", fake_run)
    res = fortran.compile_check(p, gfortran="gfortran-fake")
    monkeypatch.setattr(fortran.subprocess, "run", real_run)
    assert res["compiled"] and not res["ok"]
    assert res["messages"] == [
        {"level": "warning", "line": 7, "message": "Possible change of value in conversion from REAL(8) to "
                                                    "INTEGER(4) at (1) [-Wconversion]"},
        {"level": "error", "line": 12, "message": "Non-numeric character in statement label at (1)"}]


@pytest.mark.skipif(not GFORTRAN, reason="gfortran not installed")
def test_real_gfortran_on_the_planted_mistakes(tmp_path):
    res = fortran.check_file(write(tmp_path, BAD.replace("F     W", "      W")))
    msgs = {(m["line"], m["message"].split(" [")[-1]) for m in res["compile"]["messages"]}
    assert (7, "-Wconversion]") in msgs and (11, "-Wline-truncation]") in msgs


def test_cli_exit_codes(tmp_path):
    env = dict(os.environ, PROC_SIM_AGENT_HOME=str(tmp_path / "home"), PYTHONIOENCODING="utf-8")
    run = lambda *a: subprocess.run([sys.executable, str(SCRIPTS / "fw.py"), "fortran-check", *map(str, a)],
                                    capture_output=True, text=True, encoding="utf-8", env=env, timeout=120)
    assert run(TEMPLATES / "fortran-calculator.txt", "--no-compile").returncode == 0
    p = run(write(tmp_path, BAD), "--no-compile", "--json")
    assert p.returncode == 1 and '"level": "error"' in p.stdout
    assert run(tmp_path / "missing.txt").returncode == 2


def test_build_mode_templates():
    names = {p.name for p in TEMPLATES.iterdir()}
    assert {"build-guide.md", "status.md", "data-card.md", "expected.csv", "fortran-calculator.txt"} <= names
    assert "BUILD.md" not in names
    guide = (TEMPLATES / "build-guide.md").read_text(encoding="utf-8")
    for n in range(10):
        assert f"\n## {n}. " in guide, n
    assert "## Sources" in guide and "## Before delivering this guide" in guide
    status = (TEMPLATES / "status.md").read_text(encoding="utf-8")
    for h in ("Read for this revision", "Checks run here", "Modelling rules kept", "Summary",
              "What to send after each step", "Roadmap", "Version history", "Problems, ranked",
              "Messages and fixes", "Sources"):
        assert f"## {h}" in status, h
    card = (TEMPLATES / "data-card.md").read_text(encoding="utf-8")
    assert "| Item | Value in the model | Unit | Source" in card and "| Point | Data | Card | Deviation |" in card
    rows = check.load_expected(TEMPLATES / "expected.csv")
    assert [r["item"] for r in rows] == ["Overall mass balance", "CO2 captured", "Reboiler duty", "Product temperature"]
    assert rows[2]["tol_rel"] == pytest.approx(0.03)
