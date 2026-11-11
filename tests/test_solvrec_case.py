"""The synthetic SolvRec case (tests/samples.py): every reader on one consistent set of run files.

It takes the place of the published example model that left the repository in 0.3.1: a backup with
calculators, disabled objects and a results section; a history with message IDs, a converged tear
loop and a calculator whose imported variable is never used; a multi-page report with a RadFrac
block and stream tables; a Control Panel export with an error summary; a lower-case report grouped
with its model; and a backup older than the history and report of the same case."""
import pytest

from fwlib import bkp, check, cpm, freshness, his, inp, rep, sims

import samples
import scrub_aspen_files as scrub


@pytest.fixture
def case(tmp_path):
    return samples.write_solvrec(tmp_path / "SolvRec" / "v0.07")


def test_bkp_structure(case):
    d = bkp.parse(case / "SolvRec.bkp")
    assert d["engine"] == "39.0" and d["release"] == "V12.1"
    assert len(d["components"]) == 10 and d["ions"] == ["H3O+", "OH-", "HCO3-"]
    assert list(d["blocks"]) == ["FEEDPUMP", "PREHEAT", "MIXREC", "RX-STAGE", "COL1", "SPLIT1", "GASCOMP"]
    assert d["blocks"]["COL1"]["model"] == "RadFrac" and d["blocks"]["COL1"]["out"] == ["DIST", "BTMS"]
    assert d["blocks"]["MIXREC"]["in"] == ["S2", "RECYCLE"]
    assert d["calculators"] == ["RATIO"] and d["design_specs"] == ["DS-PUR", "DS-RR"]
    assert d["disabled"] == ["DESIGN-SPEC DS-PUR", "DESIGN-SPEC DS-RR"]
    assert d["fortran"]["CALCULATOR RATIO"]["lines"] == ["      XEXT = 0.75D0 + 0.0D0 * FIPA"]
    assert [x["name"] for x in d["fortran"]["CALCULATOR RATIO"]["defines"]] == ["FIPA", "XEXT", "FSPARE"]
    assert d["reactions"] == ["R-COND REAC-DIST"] and d["tears"] == ["RECYCLE"]
    assert d["conv_options"][0] == "TEAR-METHOD=WEGSTEIN CHECKSEQ=NO"
    assert "SETUP UNITS-SET US-1" in d["sections"]          # a record with a bare list after its keys
    assert d["henry"] == {"HC-1": ["H2", "CO2", "N2"]}
    run = d["run"]
    assert run["has_results"] and run["last_run"] == "MAY 12, 2026 09:40:55 A.M."
    assert run["run_engine"] == "39.0" and "HENRY COMPONENTS ARE DEFINED" in run["messages"][0]
    md = bkp.render_markdown(d)
    for text in ("- Reaction sets: R-COND REAC-DIST", "- Disabled: DESIGN-SPEC DS-PUR, DESIGN-SPEC DS-RR",
                 "- Convergence options: TEAR-METHOD=WEGSTEIN", "## Stored run-status messages",
                 "- CALCULATOR RATIO: 3 defined variables, 1 Fortran lines"):
        assert text in md, text
    assert "DESKTOP" not in md and "Streams with input values" not in md


def test_his_digest(case):
    h = his.parse(case / "SolvRec.his")
    run = h["runs"][-1]
    assert h["header"]["release"] == "V15" and h["status"] == "completed: 2 warnings"
    assert run["trace"]["loops"]["$OLVER01"]["converged"]
    assert run["trace"]["loops"]["$OLVER01"]["iterations"] == 2
    assert {g["id"] for g in run["messages"]} == {"PRPCHK.1", "PSTOP1AP.1", "URE07.2"}
    ure = next(g for g in run["messages"] if g["id"] == "URE07.2")
    assert ure["where"] == ["block RX-STAGE (RSTOIC)"]          # a header wrapped over two lines
    assert any(c.startswith("URE07.2") and "iteration 0" in c for c in his.checks(h))
    lint = his.fortran_lint(h["model"]["calculators"]["RATIO"])
    assert any("never used" in i and "FSPARE" in i for i in lint)
    m = h["model"]
    assert m["prop_data"]["NRTL-1"] == {"params": ["NRTL"], "components": ["WATER", "IPA"]}
    assert m["prop_data"]["PLXANT-1"]["params"] == ["PLXANT", "MW"]
    assert m["conv_options"] == ["PARAM TEAR-METHOD=WEGSTEIN CHECKSEQ=NO", "WEGSTEIN MAXIT=100 QMIN=-5. QMAX=0."]
    assert m["reactions"]["R-COND"]["type"] == "REAC-DIST" and m["disabled"] == ["DESIGN-SPEC DS-PUR"]
    rows = {r["block"]: r for r in his.block_rows(run["trace"]["blocks"])}
    assert rows["GASCOMP"]["duty_kW"] == pytest.approx(25.94) and rows["GASCOMP"]["other"] == "eff 0.75"
    assert rows["FEEDPUMP"]["duty_kW"] == pytest.approx(1.4914)
    assert rows["FEEDPUMP"]["other"] == "dP 4.987 bar; eff 0.60"
    assert rows["FEEDPUMP"]["P_bar"] is None        # results-generation flashes are not outlet states
    md = his.render_markdown(h)
    assert "NORTHWIND" not in md and "jsmith" not in md


def test_rep_values(case):
    r = rep.parse(case / "solvrec.rep")
    assert r["n_pages"] == 10 and r["engine"] == "41.0"
    assert r["sections"] == ["RUN CONTROL SECTION", "FLOWSHEET SECTION", "U-O-S BLOCK SECTION", "STREAM SECTION",
                             "PROBLEM STATUS SECTION"]
    res = {lab: val for lab, unit, val in r["blocks"]["COL1"]["results"]}
    assert res["REBOILER DUTY"] == pytest.approx(1482650.0)
    assert res["CONDENSER DUTY (W/O SUBCOOL)"] == pytest.approx(-1217330.0)
    assert not any(lab.startswith("WATER") for lab in res)        # split-fraction rows are not results
    assert r["problem_status"][0] == "Calculations were completed normally"
    assert rep.to_float(r["streams"]["BTMS"]["MIXED|COMPONENTS: KMOL/HR|HEAVY"]) == pytest.approx(0.053363)
    assert r["streams"]["S4"]["FROM"] == "RX-STAGE" and len(r["streams"]) == 11
    assert r["overall_balance"]["MASS (KG/HR)"][:2] == [5448.11, 5448.11]
    md = rep.render_markdown(r)
    assert "NORTHWIND" not in md and "jsmith" not in md and "Program Files" not in md


def test_cpm_summary(case):
    c = cpm.parse(case / "SolvRec.cpm")
    assert c["completed"] and c["loops"]["$OLVER01"]["converged"]
    assert c["error_summary"]["warnings"] == {"physical_property": 0, "system": 1, "simulation": 1}
    assert c["radfrac"]["COL1"] == {"iterations": 2, "last": "2 2 5 0.52007"}
    assert c["translation_note"] == "Warning(s) were issued during Input Translation"
    assert c["executions"]["COL1"]["count"] == 2 and c["executions"]["RATIO"]["count"] == 2
    assert "Input Translation" in cpm.render_markdown(c)


def test_sim_scan_groups_the_lowercase_report(case):
    folders = sims.scan([str(case.parent)])
    assert len(folders) == 1
    models = list(folders[0]["models"].values())
    assert len(models) == 1, "the lower-case .rep must group with the model"
    m = models[0]
    assert sorted(m["files"]) == [".bkp", ".cpm", ".his", ".rep"]
    assert m["release"] == "V12.1 file, run in V15" and m["status"] == "completed: 2 warnings"
    assert folders[0]["warnings"] == [
        "v0.07/SolvRec: SolvRec.bkp is 101 days older than the run in solvrec.rep. "
        "Fix: run, save, then File > Export > Report."]
    assert "## Warnings: files from an older run" in sims.render_markdown(folders)


def test_run_stamps(case):
    res = freshness.check_case(case / "SolvRec.his")
    files = res["files"]
    assert res["stale"] == ["SolvRec.bkp"] and files["SolvRec.bkp"]["older_by"] == "101 days"
    assert files["SolvRec.bkp"]["time"] == "2026-05-12 09:40:55" and files["SolvRec.bkp"]["run_id"] == "_7350klm"
    assert files["SolvRec.his"]["time"] == "2026-08-21 14:30:41"
    assert files["solvrec.rep"]["time"] == "2026-08-21 14:30:52"
    assert files["SolvRec.cpm"]["event"] == "Report exported"
    assert {files[n]["run_id"] for n in ("SolvRec.his", "solvrec.rep")} == {"_2207pqr"}
    assert freshness.describe(res) == "SolvRec.bkp is 101 days older than the run in solvrec.rep"


def test_check_with_formulas_from_the_his(case):
    streams = check.load(case / "solvrec.rep")
    aliases = check.aliases_from(case / "SolvRec.his")
    res = check.analyse(streams, elements=["C", "H", "O", "N"], aliases=aliases)
    assert res["streams"]["FEED"]["mass_unit"] == "kg/hr"
    assert res["streams"]["DIST"]["VFRAC"] == pytest.approx(0.5263)
    for b in ("FEEDPUMP", "PREHEAT", "MIXREC", "RX-STAGE", "COL1", "SPLIT1", "GASCOMP"):
        assert abs(res["blocks"][b]["mass_rel"]) < 1e-4, b
    for b in ("FEEDPUMP", "PREHEAT", "GASCOMP"):      # every component has a formula
        assert all(abs(v["rel"] or 0) < 1e-9 for v in res["blocks"][b]["elements"].values()), b
    assert "no formula for HEAVY" in res["blocks"]["RX-STAGE"]["note"]
    assert any("apparent basis" in f for f in res["flags"])     # ions zero: the chemistry is not used


def test_input_from_the_his(case):
    res = inp.check(inp.from_his(his.parse(case / "SolvRec.his")))
    assert res["counts"]["error"] == 0, [f["message"] for f in res["findings"] if f["level"] == "error"]
    unused = [f for f in res["findings"] if "no PROPERTIES statement uses it" in f["message"]]
    assert len(unused) == 2
    assert len(res["summary"]["blocks"]) == 7


def test_scrub_tool_on_the_case(case):
    """What tools/scrub_aspen_files.py removes from these files, and that nothing is left after."""
    found = {}
    for f in sorted(case.iterdir()):
        text = f.read_bytes().decode("latin-1")
        new, changes = scrub.scrub_text(text, f.suffix.lower())
        found[f.name] = len(changes)
        assert not scrub.suspects(new), (f.name, scrub.suspects(new)[:2])
        assert "NORTHWIND" not in new and "jsmith" not in new
    assert found == {"SolvRec.bkp": 0, "SolvRec.cpm": 0, "SolvRec.his": 2, "solvrec.rep": 3}
