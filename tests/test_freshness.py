"""WP4: run stamps inside the files decide which run each file describes (never file times),
several runs in one .his, sim-scan notes, and the run-review table of `check --expect`.
Every file here is synthetic."""
import json
import os
import subprocess
import sys
import time
from datetime import datetime

import pytest

from conftest import SCRIPTS
from fwlib import check, freshness, his, sims

import samples

FW = SCRIPTS / "fw.py"


def run(args, home, ok=(0,)):
    env = dict(os.environ, PROC_SIM_AGENT_HOME=str(home), PYTHONIOENCODING="utf-8")
    p = subprocess.run([sys.executable, str(FW)] + [str(a) for a in args], capture_output=True, text=True,
                       encoding="utf-8", env=env, timeout=300)
    assert p.returncode in ok, f"exit {p.returncode}\n{p.stdout}\n{p.stderr}"
    return p


def same_mtime(*paths):
    """What a cloud sync leaves behind: every file with the same modification time."""
    t = time.time()
    for f in paths:
        os.utime(f, (t, t))


@pytest.mark.parametrize("text, want", [
    ("OCTOBER 2, 2026 11:02:41 P.M.", datetime(2026, 10, 2, 23, 2, 41)),
    ("SEPTEMBER 28, 2023  12:45:10 P.M.", datetime(2023, 9, 28, 12, 45, 10)),
    ("MARCH 3, 2026 12:05:00 A.M.", datetime(2026, 3, 3, 0, 5, 0)),
    ("23:02:40 Fri Oct 2, 2026", datetime(2026, 10, 2, 23, 2, 40)),
    ("Thu Sep 28 12:45:40 2023", datetime(2023, 9, 28, 12, 45, 40)),
    ("Mon Oct  5 10:00:00 2026", datetime(2026, 10, 5, 10, 0, 0)),
    ("OKTOBER 2, 2026 11:02:41 P.M.", None),        # not an English month name
    ("FEBRUARY 30, 2026 10:00:00 A.M.", None),      # no such day
    ("x", None),
])
def test_dates_as_aspen_writes_them(text, want):
    assert freshness.parse_datetime(text) == want


def test_stamps_of_each_file_type(tmp_path):
    d = tmp_path / "v1"
    h = samples.write(d / "M.his", samples.his_at("OCTOBER 2, 2026", "11:02:41 P.M.", "_0003ynx"))
    r = samples.write(d / "m.rep", samples.rep_at("OCTOBER 2, 2026", "11:02:44 P.M.", "_0003ynx"))
    b = samples.write(d / "M.bkp", samples.bkp_at("OCTOBER 2, 2026  11:02:44 P.M.", "_0003ynx"))
    c = samples.write(d / "M.cpm", samples.cpm_at("23:02:38 Fri Oct 2, 2026", "23:03:03 Fri Oct 2, 2026"))
    s = samples.write(d / "M.sum", ' DSET RUN-STATUS IT @IT ( "OCTOBER 2, 2026  11:02:44 P.M." "_0003ynx.inm" 4)\n'
                                   ' DSET RUN-STATUS RUNID @RUNID ("_0003ynx")\n')
    st = {p.suffix: freshness.stamp(p) for p in (h, r, b, c, s)}
    assert st[".his"]["time"] == datetime(2026, 10, 2, 23, 2, 41) and st[".his"]["run_id"] == "_0003ynx"
    assert st[".his"]["role"] == "start" and st[".his"]["run_type"] == "ORIGINAL RUN"
    assert st[".rep"]["time"] == datetime(2026, 10, 2, 23, 2, 44) and st[".rep"]["run_id"] == "_0003ynx"
    assert st[".bkp"]["time"] == datetime(2026, 10, 2, 23, 2, 44) and st[".bkp"]["has_results"]
    assert st[".bkp"]["saved"] == datetime(2026, 10, 5, 10, 0, 0)
    assert st[".cpm"]["time"] == datetime(2026, 10, 2, 23, 3, 3) and st[".cpm"]["event"] == "Report exported"
    assert st[".sum"]["time"] == datetime(2026, 10, 2, 23, 2, 44) and st[".sum"]["run_id"] == "_0003ynx"
    res = freshness.check_case(h)
    assert res["verdict"] == "fresh" and not res["stale"], res
    assert freshness.warning_lines(r, res) == []


def test_the_owners_case_bkp_run_four_days_after_his_and_rep(tmp_path):
    """A version folder: the .bkp holds a run of Oct 6, the .his and .rep next to it a run of Oct 2;
    a cloud sync left all three with the same file time."""
    d = tmp_path / "proj" / "v1.03"
    h = samples.write(d / "FA.his", samples.his_at("OCTOBER 2, 2026", "11:02:41 P.M.", "_0003ynx"))
    r = samples.write(d / "fa.rep", samples.rep_at("OCTOBER 2, 2026", "11:02:44 P.M.", "_0003ynx"))
    b = samples.write(d / "FA.bkp", samples.bkp_at("OCTOBER 6, 2026  09:14:20 A.M.", "_7731qke",
                                                   saved="Tue Oct  6 09:15:02 2026"))
    same_mtime(h, r, b)
    res = freshness.check_case(b)
    assert res["verdict"] == "stale" and sorted(res["stale"]) == ["FA.his", "fa.rep"]
    assert res["files"]["FA.his"]["than"] == "FA.bkp" and res["files"]["FA.his"]["older_by"] == "3 days 10 h"
    assert res["last_run"]["file"] == "FA.bkp"

    home = tmp_path / "home"
    out = run(["sim-scan", tmp_path / "proj"], home).stdout
    top = out.split("| Folder |")[0]
    assert "## Warnings: files from an older run" in top
    assert "v1.03/FA: FA.his is 3 days 10 h older than the run in FA.bkp" in top
    assert "fa.rep is 3 days 10 h older than the run in FA.bkp" in top
    assert "Fix: run, save, then File > Export > Report." in top
    assert "completed: 2 warnings - from a stale .his" in out     # the status no longer looks current
    for cmd, f in (("his", h), ("rep", r), ("check", r)):
        first = run([cmd, f], home).stdout.lstrip().splitlines()[0]
        assert first.startswith(f"WARNING: {f.name} describes an older run than FA.bkp"), (cmd, first)
        assert "run, save, then File > Export > Report" in first
    data = json.loads(run(["his", h, "--json"], home).stdout)
    assert data["freshness"]["files"]["FA.his"]["verdict"] == "stale"
    data = json.loads(run(["rep", d, "--json"], home).stdout)       # a folder: the note goes to stderr
    assert data["freshness"]["verdict"] == "stale"


def test_file_times_are_never_used(tmp_path):
    """Consistent stamps with a .his whose file time is a day older: no warning. Stale stamps with
    newer file times: still flagged."""
    d = tmp_path / "ok"
    h = samples.write(d / "M.his", samples.HIS)
    r = samples.write(d / "m.rep", samples.rep_at("MARCH 3, 2026", "10:15:40 A.M."))
    b = samples.write(d / "M.bkp", samples.bkp_at("MARCH 3, 2026  10:15:40 A.M.", saved="Tue Mar  3 10:16:00 2026"))
    old = time.time() - 86400
    os.utime(h, (old, old))
    assert freshness.check_case(h)["verdict"] == "fresh"
    assert not [n for f in sims.scan([str(tmp_path)]) for n in f["notes"] + f["warnings"] if "stale" in n]
    d2 = tmp_path / "stale"
    h2 = samples.write(d2 / "M.his", samples.HIS)
    b2 = samples.write(d2 / "M.bkp", samples.bkp_at("MARCH 9, 2026  10:15:40 A.M.", "_9999zzz"))
    os.utime(b2, (old, old))                                          # the newer run has the older file time
    assert freshness.check_case(h2)["stale"] == ["M.his"]
    assert r.exists()


def test_a_long_run_is_not_a_stale_file(tmp_path):
    """The .rep and the results in the .bkp are written as the run ends: three hours after the
    start in the .his, same run ID."""
    d = tmp_path / "v"
    samples.write(d / "M.his", samples.his_at("MARCH 3, 2026", "10:00:00 A.M."))
    samples.write(d / "m.rep", samples.rep_at("MARCH 3, 2026", "01:00:00 P.M."))
    samples.write(d / "M.bkp", samples.bkp_at("MARCH 3, 2026  01:00:00 P.M."))
    assert freshness.check_case(d / "M.his")["verdict"] == "fresh"


def test_report_exported_before_the_last_run_started(tmp_path):
    """Same session (same run ID): the report was exported after run 1, then the input changed and
    an edit run started; the .his records it, the .rep is from run 1."""
    d = tmp_path / "v"
    samples.write(d / "M.his", samples.HIS_TWO_RUNS)                      # last run: MARCH 4, 09:00
    samples.write(d / "m.rep", samples.rep_at("MARCH 3, 2026", "10:15:40 A.M."))
    res = freshness.check_case(d / "m.rep")
    assert res["stale"] == ["m.rep"] and res["files"]["m.rep"]["than"] == "M.his"
    assert res["files"]["m.rep"]["older_by"] == "22 h 44 min"


def test_a_report_with_only_the_page_date(tmp_path):
    """No first-page header: the page header date (month first) stands for the whole day."""
    d = tmp_path / "v"
    samples.write(d / "M.his", samples.HIS)                              # MARCH 3, 10:15:02
    samples.write(d / "m.rep", samples.REP)                              # 03/03/2026
    st = freshness.stamp(d / "m.rep")
    assert st["precision"] == "day" and st["time"] == datetime(2026, 3, 3)
    assert freshness.check_case(d / "m.rep")["verdict"] == "fresh"
    samples.write(d / "m.rep", samples.REP.replace("03/03/2026", "03/01/2026"))
    res = freshness.check_case(d / "m.rep")
    assert res["stale"] == ["m.rep"] and "date only" in res["files"]["m.rep"]["time"]


def test_cpm_is_compared_but_never_makes_other_files_stale(tmp_path):
    d = tmp_path / "v"
    samples.write(d / "M.his", samples.HIS)                              # MARCH 3, 10:15:02
    samples.write(d / "M.cpm", samples.cpm_at("10:15:00 Tue Mar 3, 2026", "09:30:00 Tue Mar 10, 2026"))
    assert freshness.check_case(d / "M.his")["verdict"] == "fresh"       # an export a week later
    samples.write(d / "M.cpm", samples.cpm_at("08:00:00 Mon Mar 2, 2026", "08:05:00 Mon Mar 2, 2026"))
    res = freshness.check_case(d / "M.his")
    assert res["stale"] == ["M.cpm"] and res["files"]["M.cpm"]["event"] == "Report exported"


def test_bkp_saved_without_results_after_the_run(tmp_path):
    d = tmp_path / "v"
    samples.write(d / "M.his", samples.HIS)                              # MARCH 3, 10:15:02
    samples.write(d / "M.bkp", samples.BKP_COLUMN.replace("Mon Oct  5 11:00:00 2026", "Wed Mar  4 16:20:00 2026"))
    res = freshness.check_case(d / "M.his")
    assert res["files"]["M.bkp"]["has_results"] is False
    assert res["notes"] and "holds no results and was saved on 2026-03-04 16:20:00" in res["notes"][0]
    assert any(line.startswith("Note: M.bkp holds no results") for line in freshness.warning_lines(d / "M.his", res))


def test_several_runs_in_one_his(tmp_path):
    f = samples.write(tmp_path / "M.his", samples.HIS_TWO_RUNS)
    d = his.parse(f)
    assert d["n_runs"] == 2 and d["status"] == "completed: no errors or warnings"   # the last run's summary
    md = his.render_markdown(d)
    assert "run MARCH 4, 2026 09:00:00 A.M." in md
    assert "This file holds 2 runs; the digest describes the last one (edit run 2 of 2" in md
    assert "FRAC RECYCLE 0.4" in his.echo_text(d)
    st = freshness.stamp(f)
    assert st["runs"] == 2 and st["run_type"] == "EDIT RUN" and st["time"] == datetime(2026, 3, 4, 9, 0)
    (tmp_path / "M.bkp").write_text('MM "41.0" VERSION "41.0" DATETIME "x"\n', encoding="latin-1")
    m = sims.scan([str(tmp_path)])[0]["models"]["m"]
    assert m["status"] == "completed, no errors or warnings (last of 2 runs in the .his)"


def test_last_run_without_error_summary_does_not_borrow_the_first(tmp_path):
    two = samples.HIS_TWO_RUNS
    cut = two.rindex(" *** SUMMARY OF ERRORS ***")
    f = samples.write(tmp_path / "M.his", two[:cut])
    d = his.parse(f)
    assert d["error_summary"] is None and not d["status"].startswith("completed")
    (tmp_path / "M.bkp").write_text('MM "41.0" VERSION "41.0" DATETIME "x"\n', encoding="latin-1")
    assert not sims.scan([str(tmp_path)])[0]["models"]["m"]["status"].startswith("completed")


@pytest.mark.parametrize("rel, stem, want", [
    (".", "FA", "FA"), ("FA_v1.03", "FA_v1.03", "FA_v1.03"), ("proj/fa-v1.03", "FA_V1.03", "proj/fa-v1.03"),
    ("proj/v1.03", "FA", "proj/v1.03/FA"),
])
def test_note_says_the_case_once(rel, stem, want):
    assert sims._where(rel, stem) == want


def test_sim_scan_notes_do_not_repeat_the_case_name(tmp_path):
    d = tmp_path / "sims" / "FA_v1.03"
    (d).mkdir(parents=True)
    (d / "FA_v1.03.bkp").write_text('MM "41.0" VERSION "41.0" DATETIME "x"\n', encoding="latin-1")
    out = sims.render_markdown(sims.scan([str(tmp_path / "sims")]))
    assert "- FA_v1.03: no .rep export" in out and "FA_v1.03: FA_v1.03" not in out


def test_picking_a_file_of_a_folder_uses_run_stamps(tmp_path):
    d = tmp_path / "v"
    newer = samples.write(d / "B.his", samples.his_at("MARCH 9, 2026", "10:00:00 A.M.", "_2222bbb"))
    older = samples.write(d / "A.his", samples.HIS)
    t = time.time()
    os.utime(newer, (t - 86400, t - 86400))                       # file times say the opposite
    os.utime(older, (t, t))
    out = run(["his", d], tmp_path / "home").stdout
    assert "(using B.his; 2 .his files here, pass the file to choose another)" in out


def test_find_all_across_chunks(tmp_path):
    f = tmp_path / "x.his"
    f.write_bytes(b"ab*** INPUT SUMMARY ***cd" * 3)
    assert freshness._find_all(f, freshness.RUN_MARK, chunk=7) == [2, 27, 52]


# ---------------------------------------------------------------------------
# check --expect: the run-review table
# ---------------------------------------------------------------------------
EXPECTED_CSV = """# item, source, expected, tolerance (absolute or relative)
item,source,expected,tol_abs,tol_rel,unit
CO2 in the product,"flow(PROD, CO2)",1.0,,0.1%,kmol/hr
CO2 removed,"1 - flow(PROD, CO2)/flow(FEED, CO2)",0.9,0.001,,
Product temperature,temp(PROD),45,0.5,,C
R1 duty,"block(R1, HEAT DUTY)",-12345.6,,3%,
Mass balance,balance(MASS),0,1e-6,,
Make-up water,"flow(MAKEUP, H2O)",1.5,,1%,kmol/hr
"""


def test_review_table_from_a_report(tmp_path):
    rows = check.load_expected(samples.write(tmp_path / "expected.csv", EXPECTED_CSV, crlf=True))
    assert [r["item"] for r in rows][0] == "CO2 in the product" and rows[0]["tol_rel"] == pytest.approx(0.001)
    r = samples.write(tmp_path / "m.rep", samples.REP)
    from fwlib import rep
    report = rep.parse(r)
    res = check.analyse(check.from_rep(r, report), expect=rows, report=report)
    v = {x["item"]: x for x in res["expect"]}
    assert v["CO2 in the product"]["verdict"] == "pass"
    assert v["CO2 removed"]["verdict"] == "pass" and v["CO2 removed"]["model"] == pytest.approx(0.9)
    assert v["Product temperature"]["verdict"] == "fail"                      # 40 C in the report
    assert v["R1 duty"]["verdict"] == "pass" and v["R1 duty"]["model_unit"] == "CAL/SEC"
    assert v["Mass balance"]["verdict"] == "pass"
    assert v["Make-up water"]["verdict"] == "missing" and "no stream MAKEUP" in v["Make-up water"]["why"]
    md = check.render(res)
    assert "| Item | Expected | Model | Verdict |" in md
    assert "| Product temperature | 45 C (+/- 0.5) | 40 C | fail (-11.11 %) |" in md
    assert "| Make-up water | 1.5 kmol/hr (+/- 1 %) | - | missing: no stream MAKEUP in the table |" in md
    assert "6 checks: 4 pass, 1 fail, 1 missing." in md


def test_check_expect_cli_exit_codes_and_json(tmp_path):
    home = tmp_path / "home"
    r = samples.write(tmp_path / "m.rep", samples.REP)
    bad = samples.write(tmp_path / "expected.csv", EXPECTED_CSV)
    out = run(["check", r, "--expect", bad], home, ok=(1,)).stdout
    assert "## Run review" in out and "fail" in out
    good = tmp_path / "expected.json"
    good.write_text(json.dumps([{"item": "R1 outlet T", "source": "block(R1, OUTLET TEMP)", "expected": 40,
                                 "tol_abs": 0.1},
                                {"item": "Feed flow", "source": "mole(FEED)", "expected": 100}]), encoding="utf-8")
    res = json.loads(run(["check", r, "--expect", good, "--json"], home).stdout)
    assert [x["verdict"] for x in res["expect"]] == ["pass", "pass"]
    assert res["expect"][1]["tol_rel"] == check.DEFAULT_TOL_REL
    broken = samples.write(tmp_path / "broken.csv", "item,source,expected\nX,mole(FEED),lots\n")
    err = run(["check", r, "--expect", broken], home, ok=(2,)).stderr
    assert "expected and tolerances must be numbers" in err
    err = run(["check", r, "--expect", samples.write(tmp_path / "e.csv", "item,expected\nX,1\n")], home, ok=(2,)).stderr
    assert "no source" in err


def test_metric_functions_for_state_and_blocks():
    t = check.from_text(samples.STREAM_TABLE)
    with pytest.raises(ValueError, match="needs a .rep"):
        check.evaluate("block(R1, HEAT DUTY)", t, {})
    with pytest.raises(ValueError, match="only numbers"):
        check.evaluate("__import__('os')", t, {})
