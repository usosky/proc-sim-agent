"""The published Joule example: every parser on real files, and the check against the SI."""
import subprocess
import sys

import pytest

from conftest import EXAMPLE, ROOT
from fwlib import bkp, cpm, his, rep, sims

BKP = EXAMPLE / "FINAL_FAprocess_50kton_V8_ForEvaluation.bkp"
HIS = EXAMPLE / "FINAL_FAprocess_50kton_V8_ForEvaluation.his"
REP = EXAMPLE / "final_faprocess_50kton_v8_forevaluation.rep"
CPM = EXAMPLE / "FINAL_FAprocess_50kton_V8_ForEvaluation.cpm"


def test_bkp_structure():
    d = bkp.parse(BKP)
    assert d["engine"] == "39.0" and d["release"] == "V12.1"
    assert len(d["components"]) == 27
    assert len(d["blocks"]) == 18
    assert d["blocks"]["C311"]["model"] == "RadFrac"
    assert d["blocks"]["C311"]["in"] == ["TO-C3", "TEMP-REC"]
    assert sorted(d["calculators"]) == ["AECREC", "C-2", "H2OCONC"]
    assert len(d["disabled"]) == 4
    md = bkp.render_markdown(d)
    assert "DESKTOP" not in md and "Streams with input values" not in md


def test_his_digest():
    h = his.parse(HIS)
    run = h["runs"][-1]
    assert h["header"]["release"] == "V15"
    assert run["trace"]["loops"]["$OLVER01"]["converged"]
    assert run["trace"]["loops"]["$OLVER01"]["iterations"] == 2
    ids = {g["id"] for g in run["messages"]}
    assert {"PRPCHK.1", "URE07.2", "URE07.5", "VFLASH.1"} <= ids
    checks = his.checks(h)
    assert any(c.startswith("URE07.2") and "iteration 0" in c for c in checks)
    lint = his.fortran_lint(h["model"]["calculators"]["C-2"])
    assert any("never used" in i and "CONV" in i for i in lint)
    rows = {r["block"]: r for r in his.block_rows(run["trace"]["blocks"])}
    assert rows["COMPH2"]["duty_kW"] == pytest.approx(326.036, rel=1e-3)
    assert rows["PRES-H2O"]["P_bar"] is None  # results-generation flashes are not outlet states


def test_rep_values():
    r = rep.parse(REP)
    res = {lab: val for lab, unit, val in r["blocks"]["C311"]["results"]}
    assert res["REBOILER DUTY"] == pytest.approx(9237420.0)
    assert res["CONDENSER DUTY (W/O SUBCOOL)"] == pytest.approx(-16331900.0)
    assert r["problem_status"][0] == "Calculations were completed normally"
    assert rep.to_float(r["streams"]["C4-DIS"]["MIXED|COMPONENTS: KMOL/HR|HCOOH"]) == pytest.approx(211.3636)


def test_cpm_summary():
    c = cpm.parse(CPM)
    assert c["completed"]
    assert c["loops"]["$OLVER01"]["converged"]
    assert c["error_summary"]["warnings"]["simulation"] == 3


def test_sim_scan_links_lowercase_report():
    folders = sims.scan([str(EXAMPLE.parent)])
    models = [m for f in folders for m in f["models"].values()]
    joule = [m for m in models if m["name"].upper().startswith("FINAL_FAPROCESS")]
    assert len(joule) == 1, "the lower-case .rep must group with the model"
    assert joule[0]["release"] == "V12.1 file, run in V15"


def test_check_against_si_script():
    out = subprocess.run([sys.executable, str(EXAMPLE / "check_against_si.py")], cwd=ROOT,
                         capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr
    assert "| AEC (C311) reboiler | 38,675.2 | 38,675.4 |" in out.stdout
    assert "85.2 kt/y" in out.stdout


def test_example_files_are_scrubbed():
    import scrub_aspen_files as scrub
    for f in EXAMPLE.iterdir():
        if f.suffix.lower() in scrub.EXTS:
            text = f.read_bytes().decode("latin-1")
            new, changes = scrub.scrub_text(text, f.suffix.lower())
            assert not changes, f"{f.name} still has private lines: {changes[:2]}"
            assert not scrub.suspects(new), f"{f.name}: {scrub.suspects(new)[:2]}"
