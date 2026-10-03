"""Parsers for .his, .rep and .cpm on synthetic files."""
import pytest

from fwlib import cpm, his, rep


@pytest.fixture
def h(run_files):
    return his.parse(run_files["his"])


def test_his_header_status_and_model(h):
    assert h["header"]["engine"] == "41.0" and h["header"]["release"] == "V15"
    assert h["status"] == "completed: 2 warnings"
    m = h["model"]
    assert m["runid"] == "DEMO"
    assert [c["id"] for c in m["components"]] == ["CO2", "H2O", "N2"]
    assert set(m["blocks"]) == {"MIX1", "R1", "SPLIT"}
    assert "CAP" in m["calculators"] and "DS1" in m["design_specs"]


def test_his_messages_ids_and_iteration_zero(h):
    run = h["runs"][-1]
    ids = {g["id"]: g for g in run["messages"]}
    assert set(ids) == {"PDATAFAP.1", "PSTOP1AP.1", "ADFORT.7", "URE07.3"}  # incl. an ID-only header
    assert ids["PSTOP1AP.1"]["severity"] == "INFORMATION"
    assert ids["URE07.3"]["where"] == ["block R1 (RSTOIC)"]
    assert ids["URE07.3"]["iters"] == [("$OLVER01", 0)]
    assert any("only in iteration 0" in c for c in his.checks(h))


def test_his_convergence_and_trace(h):
    run = h["runs"][-1]
    loop = run["trace"]["loops"]["$OLVER01"]
    assert loop["converged"] and loop["iterations"] == 2
    assert run["analysis"]["computation_order"].startswith("$OLVER01 MIX1 CAP R1 SPLIT")
    rows = {r["block"]: r for r in his.block_rows(run["trace"]["blocks"])}
    assert rows["R1"]["T_C"] == pytest.approx(40.0)
    assert rows["R1"]["duty_kW"] == pytest.approx(-15.0)  # last pass, W -> kW


def test_fortran_lint_finds_the_planted_problems(h):
    issues = his.fortran_lint(h["model"]["calculators"]["CAP"])
    text = "\n".join(issues)
    assert "column 72" in text
    assert "FACTOR" in text                      # used but never defined or set
    assert "ADFORT.7" in text and "TIN" in text  # import assigned
    assert "never used" in text and "FN2" in text


def test_fortran_lint_tabs_and_clean_code():
    obj = {"fortran": ["F     A = B", "F\tC = A"], "defines": [{"name": "B"}], "read_vars": ["B"], "write_vars": ["C"]}
    assert any("tab" in i for i in his.fortran_lint(obj))
    clean = {"fortran": ["C     copy imports", "F     TA = TIN", "F     XOUT = 2.0D0 * TA"],
             "defines": [{"name": "TIN"}, {"name": "XOUT"}], "read_vars": ["TIN"], "write_vars": ["XOUT"]}
    assert his.fortran_lint(clean) == []


def test_his_privacy_and_echo(h):
    out = his.render_markdown(h, fortran=True)
    assert "ACME" not in out and "jdoe" not in out
    echo = his.echo_text(h)
    assert ";Directory <redacted>   Runid DEMO" in echo
    assert "jdoe" not in echo


def test_his_diff_shows_the_one_change(run_files):
    d = his.diff(his.parse(run_files["his"]), his.parse(run_files["his_v2"]))
    assert "-    FRAC RECYCLE 0.3" in d and "+    FRAC RECYCLE 0.4" in d
    assert "Directory" not in d


def test_rep(run_files):
    r = rep.parse(run_files["rep"])
    assert r["engine"] == "41.0" and r["n_pages"] == 5
    assert r["convergence"][0]["status"] == "converged"
    assert r["overall_balance"]["MOLE (KMOL/HR)"][:2] == [100.0, 100.0]
    res = {lab: (unit, val) for lab, unit, val in r["blocks"]["R1"]["results"]}
    assert res["HEAT DUTY"] == ("CAL/SEC", -12345.6)
    assert r["streams"]["PROD"]["MIXED|COMPONENTS: KMOL/HR|H2O"] == "14.0000"
    assert r["problem_status"] == ["Calculations were completed normally"]
    md = rep.render_markdown(r)
    assert "ACME" not in md and "Program Files" not in md
    assert "ACME" not in rep.find(r, "LICENSED") and "Program Files" not in rep.section_text(r, "RUN CONTROL")


def test_rep_numbers():
    assert rep.to_float("1.2104-06") == pytest.approx(1.2104e-06)
    assert rep.to_float("-0.163319+08") == pytest.approx(-1.63319e07)
    assert rep.to_float("9,237,420.") == pytest.approx(9237420.0)
    assert rep.to_float("MISSING") is None


def test_rep_csv(run_files, tmp_path):
    r = rep.parse(run_files["rep"])
    out = tmp_path / "streams.csv"
    rep.write_csv(r, str(out))
    text = out.read_text(encoding="utf-8")
    assert "FEED" in text and "PROD" in text


def test_cpm(run_files):
    c = cpm.parse(run_files["cpm"])
    assert c["completed"]
    loop = c["loops"]["$OLVER01"]
    assert loop["converged"] and loop["max_iteration"] == 2
    assert c["error_summary"]["warnings"]["simulation"] == 1
    assert any(g["where"] == "block R1" for g in c["message_groups"])
    assert "2 warnings" in cpm.render_markdown(c)


def test_fortran_lint_knows_aspen_units_and_format():
    obj = {"fortran": ["F     X = 2.0D0 * A", "F     WRITE(NTERM,100) X", "F 100 FORMAT(1X,'X =',F10.4,E12.5)",
                       "F     WRITE(NHSTRY,*) 'done'", "F     WRITE(NRPT,*) X"],
           "defines": [{"name": "A"}, {"name": "X"}], "read_vars": ["A"], "write_vars": ["X"]}
    assert his.fortran_lint(obj) == []


def test_rep_with_run_title_and_case_insensitive_streams(tmp_path):
    import samples
    titled = samples.REP.replace("PAGE 1\n", "PAGE 1\n DEMO PLANT - BASE CASE\n")
    for k in range(2, 6):
        titled = titled.replace(f"PAGE {k}\n", f"PAGE {k}\n DEMO PLANT - BASE CASE\n")
    r = rep.parse(samples.write(tmp_path / "titled.rep", titled))
    assert r["sections"] == ["RUN CONTROL SECTION", "FLOWSHEET SECTION", "U-O-S BLOCK SECTION", "STREAM SECTION",
                             "PROBLEM STATUS SECTION"]
    assert "R1" in r["blocks"] and r["problem_status"] == ["Calculations were completed normally"]
    assert "| CO2 [kmol/hr] | 10 | 1 |" in rep.stream_table(r, ["feed", "prod"])
    assert rep.stream_table(r, ["ALL"]).startswith("| | FEED | PROD |")
