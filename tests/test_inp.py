"""Input files (.inp): extraction from .his and the checker run before opening a file in Aspen Plus."""
import pytest

from conftest import EXAMPLE, SCRIPTS
from fwlib import his, inp

import samples

INPUT_FILES = sorted((SCRIPTS.parent / "templates").glob("*.inp"))


def _msgs(res, level=None):
    return [f["message"] for f in res["findings"] if level is None or f["level"] == level]


def test_clean_input_has_no_findings_but_the_release_note():
    res = inp.check(samples.INP_FLASH)
    assert res["counts"] == {"error": 0, "warning": 0, "note": 1}
    assert "Aspen Plus V15" in _msgs(res, "note")[0]
    s = res["summary"]
    assert s["feeds"] == ["FEED", "MAKEUP"] and s["products"] == ["LIQ", "VAP"]
    assert s["blocks"] == {"MIX": "MIXER", "HEAT": "HEATER", "FL1": "FLASH2"}
    assert s["calculators"] == ["C-1"] and s["sensitivities"] == ["S-1"]


@pytest.mark.parametrize("path", INPUT_FILES, ids=[p.name for p in INPUT_FILES])
def test_shipped_templates_pass(path):
    res = inp.check(inp.read(path))
    assert res["counts"]["error"] == 0 and res["counts"]["warning"] == 0, res["findings"]
    assert all(len(l) <= 80 for l in path.read_text(encoding="ascii").splitlines())


def test_planted_mistakes_are_found():
    res = inp.check(samples.INP_BAD)
    errors, warnings = "\n".join(_msgs(res, "error")), "\n".join(_msgs(res, "warning"))
    expected_errors = [
        "stream S1 enters more than one block",            # S1 feeds B2 and B3
        "block B4 is in FLOWSHEET but has no",             # no BLOCK paragraph
        "give exactly two of TEMP, PRES, VFRAC",           # FEED has three
        "Flash2 needs exactly two of",                     # B2 has three
        "Heater needs two specifications",                 # B1 has one
        "Compr needs TYPE",
        "reaction 1 has no CONV or EXTENT",
        "component CH4 is not declared",
        "component OH- is not declared",
        "not charge-balanced (net charge +1)",             # H3O+ 2.
        "missing TOL-SPEC",
        "missing RANGE",
        "Z is listed in READ-VARS/WRITE-VARS but not DEFINEd",
        "DISABLE names BLOCK B9",
    ]
    for e in expected_errors:
        assert e in errors, e
    expected_warnings = [
        "no IN-UNITS paragraph",
        "databanks of different releases: V14, V15",
        "chemistry C-2 is defined but no PROPERTIES statement uses it",
        "apparent-component approach (TRUE-COMPS=NO) while chemistry C-1 produces volatile species (CO2)",
        "elements do not balance",                         # RStoic CO2 + H2O -> CH4
        "assigns to imported (read) variables",            # Fortran lint from the .his checks
    ]
    for w in expected_warnings:
        assert w in warnings, w
    lines = {f["message"]: f["line"] for f in res["findings"]}
    assert lines["component CH4 is not declared in COMPONENTS"] == 33   # the BLOCK R1 paragraph


def test_lexical_checks():
    text = samples.INP_FLASH.replace("TITLE 'Methanol-water flash'", "TITLE 'Methanol-water flash")
    text = text.replace("STREAM-REPOR MOLEFLOW MASSFLOW MOLEFRAC",
                        "STREAM-REPOR MOLEFLOW MASSFLOW MOLEFRAC MASSFRAC STDVOLFLOW STDVOLFRAC VOLFLOW  &\n"
                        "    PROPERTIES=XAPP NOZEROFLOW NORESULTS NOCOMPONENTS NOATTR-DESC NOSUBSTREAMS  &")
    res = inp.check(text)
    errs = _msgs(res, "error")
    assert "unbalanced single quote" in errs
    assert any("ends with '&'" in e for e in errs)
    assert any("characters long" in w for w in _msgs(res, "warning"))
    unknown = inp.check(samples.INP_FLASH.replace("    PARAM TEMP=80. PRES=1.", "PARM TEMP=80. PRES=1."))
    assert any("'PARM' is not a paragraph keyword" in n for n in _msgs(unknown, "note"))


def test_templates_exist():
    assert {p.name for p in INPUT_FILES} >= {"flash-calculator-sensitivity.inp", "column-specs.inp",
                                              "electrolyte-absorber.inp"}


def test_radfrac_absorber_needs_no_col_specs():
    absorber = inp.check(inp.read(SCRIPTS.parent / "templates" / "electrolyte-absorber.inp"))
    assert not [f for f in absorber["findings"] if "COL-SPECS" in f["message"]]
    column = inp.read(SCRIPTS.parent / "templates" / "column-specs.inp").replace(
        "    COL-SPECS D:F=0.3 MOLE-RR=1.5\n", "")
    msgs = [f["message"] for f in inp.check(column)["findings"]]
    assert any("needs 2 operating specifications" in m for m in msgs)


def test_formula_elements():
    fe = inp.formula_elements
    assert fe("H2O") == {"H": 2, "O": 1}
    assert fe("CO3-2", "CO3-2") == {"C": 1, "O": 3}
    assert fe("C6H15N-2", "TEA") == {"C": 6, "H": 15, "N": 1}   # isomer suffix
    assert fe("NA2CO3*10W") == {"NA": 2, "C": 1, "O": 13, "H": 20}
    assert fe("NACL") == {"NA": 1, "CL": 1} and fe("HCL") == {"H": 1, "CL": 1}
    assert fe("CO") == {"C": 1, "O": 1} and fe("CS2") == {"C": 1, "S": 2}
    assert fe("CNO999") is None and fe("MEAH+", "MEAH+") is None and fe("") is None


def test_his_to_inp_round_trip(run_files):
    d = his.parse(run_files["his"])
    text = inp.from_his(d, source="DEMO.his")
    assert text.startswith("; Input of run 1 of 1 in DEMO.his")
    assert "FRAC RECYCLE 0.3" in text
    res = inp.check(text)
    assert res["counts"]["error"] == 0, res["findings"]


def test_joule_input_extracts_and_checks():
    d = his.parse(EXAMPLE / "FINAL_FAprocess_50kton_V8_ForEvaluation.his")
    res = inp.check(inp.from_his(d))
    assert res["counts"]["error"] == 0, _msgs(res, "error")
    # the published model defines two chemistry sets that no property method uses
    unused = [m for m in _msgs(res, "warning") if "no PROPERTIES statement uses it" in m]
    assert len(unused) == 2
    assert len(res["summary"]["blocks"]) == 18


def test_inp_diff_by_paragraph():
    a = samples.INP_FLASH
    b = (a.replace("BLOCK FL1 FLASH2\n    PARAM TEMP=80. PRES=1.", "BLOCK FL1 FLASH2\n    PARAM TEMP=75. PRES=1.")
          .replace("PROPERTIES NRTL", "PROPERTIES UNIQUAC")
          .replace("STREAM-REPOR MOLEFLOW", "BLOCK HX2 HEATER\n    PARAM TEMP=30. PRES=0\n\nSTREAM-REPOR MOLEFLOW"))
    res = inp.diff_paragraphs(a, b)
    assert [c["paragraph"] for c in res["changed"]] == ["PROPERTIES", "BLOCK FL1"]
    assert [p["paragraph"] for p in res["added"]] == ["BLOCK HX2"] and not res["removed"]
    md = inp.render_diff(res, "a.inp", "b.inp")
    assert "-PARAM TEMP=80. PRES=1.\n+PARAM TEMP=75. PRES=1." in md
    assert "2 paragraphs changed, 1 added, 0 removed" in md
    assert "No differences" in inp.render_diff(inp.diff_paragraphs(a, a + "\n; a comment\n"), "a", "a")


def test_inp_diff_cli_on_two_his(tmp_path, run_files):
    import json
    import os
    import subprocess
    import sys
    env = dict(os.environ, PROC_SIM_AGENT_HOME=str(tmp_path / "home"), PYTHONIOENCODING="utf-8")
    p = subprocess.run([sys.executable, str(SCRIPTS / "fw.py"), "inp-diff", str(run_files["his"]),
                        str(run_files["his_v2"]), "--json"], capture_output=True, text=True, encoding="utf-8",
                       env=env, timeout=120)
    assert p.returncode == 0, p.stderr
    res = json.loads(p.stdout)
    assert [c["paragraph"] for c in res["changed"]] == ["BLOCK SPLIT"]
    assert "+FRAC RECYCLE 0.4" in res["changed"][0]["diff"]
