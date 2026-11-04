"""Automation (COM) against a fake Aspen Plus server: set, run, timeout, export, edit, sweep, and
every refusal. No pywin32 and no Aspen Plus needed; the live tests are in test_com_live.py."""
import hashlib
import json
import os
import subprocess
import sys

import pytest

from conftest import SCRIPTS
from fwlib import com

import fake_aspen
import samples

sys.path.insert(0, str(SCRIPTS))
import fw  # noqa: E402


@pytest.fixture
def model(tmp_path):
    """A version folder with a model, its embedded-objects file and a note."""
    d = tmp_path / "proj" / "v1.03"
    samples.write(d / "Plant.bkp", samples.BKP_DEMO)
    (d / "Plant.apmbd").write_bytes(b"\x00embedded")
    (d / "notes.md").write_text("# v1.03\n", encoding="utf-8")
    return d / "Plant.bkp"


def digest(folder):
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(folder.iterdir()) if p.is_file()}


@pytest.fixture
def server(monkeypatch):
    """Replace the real server with the fake for fw.py and fwlib.com."""
    srv = fake_aspen.FakeAspen()
    monkeypatch.setattr(com, "start_server", fake_aspen.factory(srv))
    monkeypatch.setattr(com, "server_processes", lambda: {})
    return srv


def fw_main(args, capsys):
    try:
        fw.main([str(a) for a in args])
        code = 0
    except SystemExit as e:
        code = e.code or 0
    out = capsys.readouterr()
    return code, out.out, out.err


# ---------------------------------------------------------------------------
# no pywin32, no Windows
# ---------------------------------------------------------------------------
def test_import_is_lazy_and_help_works_without_pywin32():
    code = ("import sys; sys.path.insert(0, %r); import fw; from fwlib import com; "
            "assert 'win32com' not in sys.modules and 'pythoncom' not in sys.modules; print('ok')" % str(SCRIPTS))
    p = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=60)
    assert p.returncode == 0 and "ok" in p.stdout, p.stderr


@pytest.mark.skipif(sys.platform == "win32", reason="pywin32 may be installed on Windows")
def test_without_pywin32_the_message_says_how_to_install(model, tmp_path):
    with pytest.raises(com.AutomationError, match="python -m pip install pywin32"):
        com.get(model, ["\\Data"], processes=lambda: {})


@pytest.mark.parametrize("err, want", [
    ("(-2147221005, 'Invalid class string', None, None)", "not registered for automation"),
    ("License checkout failed for feature AspenPlus", "No Aspen Plus licence is available"),
    ("Something else", "Aspen Plus automation failed: Something else"),
])
def test_com_errors_are_explained(err, want):
    assert want in str(com.explain(RuntimeError(err)))


class FakeRegistry:
    def __init__(self, keys):
        self.keys = keys

    def default(self, key):
        return self.keys.get(key)

    def progids(self):
        return [k for k in self.keys if "\\" not in k]


def test_registry_versions_map_to_releases():
    reg = FakeRegistry({"Apwn.Document": "", "Apwn.Document\\CLSID": "{00000000-AAAA}",
                        "Apwn.Document\\CurVer": "Apwn.Document.41.0", "Apwn.Document.40.0": "",
                        "Apwn.Document.41.0": "", "Apwn.Document.99.1": ""})
    info = com.registry_info(reg)
    assert info["registered"] and info["current_release"] == "V15"
    assert [(v["engine"], v["release"]) for v in info["versions"]] == [("40.0", "V14"), ("41.0", "V15"),
                                                                       ("99.1", "")]
    assert not com.registry_info(FakeRegistry({}))["registered"]


def test_com_check_start(monkeypatch):
    srv = fake_aspen.FakeAspen()
    res = com.check(start=True, factory=fake_aspen.factory(srv), processes=lambda: {})
    assert res["start"]["ok"] and res["start"]["version"] == "41.0" and srv.quit == 1
    text = com.render_check(res)
    assert "Server start: ok" in text and "licence released" in text
    assert "Members: Version yes; Engine.IsRunning yes" in text
    assert "IAP_REINIT_SIMULATION 3; HAP_ENTERABLE 7; export codes as documented" in text
    odd = fake_aspen.factory(fake_aspen.FakeAspen(), constants={"HAPEXP_REPORT": 9})
    text = com.render_check(com.check(start=True, factory=odd, processes=lambda: {}))
    assert "export codes differ from the help: REPORT 2->9" in text

    def no_licence(visible=False):
        raise com.explain(RuntimeError("License checkout failed"))
    res = com.check(start=True, factory=no_licence, processes=lambda: {})
    assert not res["start"]["ok"] and "licence" in res["start"]["error"]


# ---------------------------------------------------------------------------
# reading: com-get, com-tree (a temporary copy; the source is never opened)
# ---------------------------------------------------------------------------
def test_get_values_and_units_from_a_temporary_copy(model, server, capsys):
    before = digest(model.parent)
    code, out, _ = fw_main(["com-get", model, "--path", "\\Data\\Streams\\FEED\\Input\\TEMP\\MIXED",
                            "--path", "\\Data\\Blocks\\R1\\Input", "--path", "\\Data\\Blocks\\NOPE"], capsys)
    assert code == 1                                          # one path not found
    assert "| \\Data\\Streams\\FEED\\Input\\TEMP\\MIXED | 25.0 | C |" in out
    assert "a folder of 3 nodes" in out and "not found (check the path with com-tree)" in out
    assert digest(model.parent) == before
    opened = server.opened[0]
    assert os.path.dirname(opened) != str(model.parent) and not os.path.exists(opened)   # temp copy, removed
    assert server.quit == 1 and server.SuppressDialogs == 1 and server.exports == []


def test_tree_depth_and_render(model, server, capsys):
    res = com.tree(model, node="\\Data\\Streams", depth=1)
    t = res["tree"]
    assert t["count"] == 2 and [c["name"] for c in t["children"]] == ["FEED", "PROD"]
    assert t["children"][0]["count"] == 2 and "children" not in t["children"][0]
    deep = com.render_tree(com.tree(model, node="\\Data\\Streams\\FEED\\Input", depth=3))
    assert "MIXED = 25.0 C" in deep and "TOTFLOW" in deep
    small = com.tree(model, node="\\Data\\Streams", depth=2, max_children=1)["tree"]
    assert small["omitted"] == 1
    code, _, err = fw_main(["com-tree", model, "--node", "\\Data\\Nothing"], capsys)
    assert code == 2 and "no node \\Data\\Nothing" in err


# ---------------------------------------------------------------------------
# com-run
# ---------------------------------------------------------------------------
def test_run_a_copy_with_one_change(model, server, tmp_path, capsys):
    before = digest(model.parent)
    out = tmp_path / "runs" / "v1.03-auto1"
    code, text, _ = fw_main(["com-run", model, "--out", out, "--set",
                             "\\Data\\Blocks\\R1\\Input\\TEMP=60", "--reinit"], capsys)
    assert code == 0, text
    assert digest(model.parent) == before                    # the source folder is unchanged
    assert sorted(p.name for p in out.iterdir()) == ["Plant.apmbd", "Plant.bkp", "Plant.cpm", "Plant.inp",
                                                     "Plant.rep", "automation-log.json"]
    log = json.loads((out / "automation-log.json").read_text(encoding="utf-8"))
    assert log["changes"] == [{"path": "\\Data\\Blocks\\R1\\Input\\TEMP", "old": 40.0, "new": 60, "unit": "C"}]
    assert log["run"]["status"] == "completed" and log["run"]["verdict"] == "ok"
    assert log["run"]["flags"] == {"CVSTAT": 0, "RSTAT": 0, "PPSTAT": 0} and log["reinit"]
    assert server.Engine.reinits == [3] and server.runs == [1] and server.quit == 1
    assert server.opened == [str(out / "Plant.bkp")]
    assert "- set \\Data\\Blocks\\R1\\Input\\TEMP: 40.0 C -> 60 C" in text
    assert "# Report digest" in text or "Calculations were completed normally" in text
    assert "## Stream checks (fw check)" in text


def test_run_errors_set_the_exit_code(model, server, tmp_path, capsys):
    code, text, _ = fw_main(["com-run", model, "--out", tmp_path / "hot", "--set",
                             "\\Data\\Blocks\\R1\\Input\\TEMP=900"], capsys)
    assert code == 1 and "status flags: errors" in text and "CVSTAT (convergence): error" in text


def test_timeout_stops_the_run_and_quits(model, monkeypatch, tmp_path):
    srv = fake_aspen.FakeAspen(run_polls=None)                # never finishes
    log = com.run(model, tmp_path / "slow", timeout=5, factory=fake_aspen.factory(srv), processes=lambda: {})
    assert log["run"]["status"] == "stopped on timeout" and srv.Engine.stops == 1 and srv.quit == 1
    assert log["files"][".rep"].startswith("not written") and log["files"][".cpm"] == "written"
    assert (tmp_path / "slow" / "automation-log.json").is_file()


def test_run_that_fails_and_a_server_without_isrunning(model, tmp_path):
    srv = fake_aspen.FakeAspen(fail_run=True)
    log = com.run(model, tmp_path / "f", factory=fake_aspen.factory(srv), processes=lambda: {})
    assert log["run"]["status"] == "failed" and "internal error" in log["run"]["error"] and srv.quit == 1
    srv = fake_aspen.FakeAspen(has_is_running=False)
    log = com.run(model, tmp_path / "sync", factory=fake_aspen.factory(srv), processes=lambda: {})
    assert srv.runs == [0] and "timeout was not enforced" in log["run"]["note"]


@pytest.mark.parametrize("args, why", [
    (["--set", "\\Data\\Streams\\PROD\\Output\\TEMP_OUT\\MIXED=50"], "is a result (Output)"),
    (["--set", "\\Data\\Blocks\\R9\\Input\\TEMP=50"], "no node \\Data\\Blocks\\R9\\Input\\TEMP"),
    (["--set", "\\Data\\Blocks\\R1\\Input=50"], "holds 3 nodes, not a value"),
    (["--set", "\\Data\\Blocks\\R1\\Input\\CALC=2"], "cannot be entered"),
    (["--set", "\\Data\\Blocks\\R1\\Input\\TEMP=rejected"], "did not accept 'rejected'"),
    (["--set", "TEMP=50"], "must start with \\Data"),
    (["--set", "\\Data\\Blocks\\R1\\Input\\TEMP"], "needs PATH=VALUE"),
])
def test_run_refusals_change_nothing(model, server, tmp_path, capsys, args, why):
    out = tmp_path / "refused"
    code, _, err = fw_main(["com-run", model, "--out", out] + args, capsys)
    assert code == 2 and why in err, err
    assert not out.exists() and server.runs == []           # nothing ran, the new folder was removed


def test_output_folder_rules(model, server, tmp_path, capsys):
    afile = tmp_path / "a-file.txt"
    afile.write_text("x", encoding="utf-8")
    for out, why in ((model.parent, "outside the model's folder"), (model.parent / "auto", "outside the model's folder"),
                     (afile, "is a file")):
        code, _, err = fw_main(["com-run", model, "--out", out], capsys)
        assert code == 2 and why in err, err
    full = tmp_path / "full"
    full.mkdir()
    (full / "old.rep").write_text("x", encoding="utf-8")
    code, _, err = fw_main(["com-run", model, "--out", full], capsys)
    assert code == 2 and "is not empty" in err
    assert server.opened == []


def test_reinit_needs_the_constant(model, tmp_path):
    srv = fake_aspen.FakeAspen()
    with pytest.raises(com.Refused, match="IAP_REINIT_SIMULATION"):
        com.run(model, tmp_path / "r", reinit=True, factory=fake_aspen.factory(srv, constants={}),
                processes=lambda: {})
    assert srv.Engine.reinits == [] and srv.runs == [] and srv.quit == 1


@pytest.mark.parametrize("marker, status", [
    ("FROZEN", None), ("frozen.md", None),
    (None, "| Version | Adds | Status |\n|---|---|---|\n| v1.03 | gate | frozen |\n"),
    (None, "- v1.03: frozen on 2026-10-01\n"),
    (None, "Next: build on the frozen v1.03.\n"),
])
def test_frozen_gates_are_refused(model, server, tmp_path, marker, status):
    if marker:
        (model.parent / marker).write_text("", encoding="utf-8")
    if status:
        (model.parent.parent / "STATUS.md").write_text("# Status\n" + status, encoding="utf-8")
    with pytest.raises(com.Refused, match="frozen gate"):
        com.run(model, tmp_path / "g")
    for fn in (lambda: com.sweep(model, tmp_path / "g2", ["\\Data\\Blocks\\R1\\Input\\TEMP=1,2"], ["\\Data"]),
               lambda: com.edit(model, tmp_path / "g3", add_streams=["S9"])):
        with pytest.raises(com.Refused, match="frozen gate"):
            fn()
    assert com.get(model, ["\\Data\\Blocks\\R1\\Input\\TEMP"])["values"][0]["value"] == 40.0   # reading is fine


def test_status_lines_that_do_not_freeze(model):
    (model.parent.parent / "STATUS.md").write_text(
        "| Version | Status |\n|---|---|\n| v1.02 | frozen |\n| v1.03 | in progress |\n"
        "v1.03 is based on the frozen v1.02.\n", encoding="utf-8")
    assert com.frozen_reason(model) == ""


def test_server_left_running_is_reported_not_killed(model, tmp_path):
    srv = fake_aspen.FakeAspen()
    calls = iter([{1: "AspenPlus.exe"}, {1: "AspenPlus.exe", 4242: "AspenPlus.exe"}])
    s = com.Session(fake_aspen.factory(srv), processes=lambda: next(calls, {1: "AspenPlus.exe", 4242: "AspenPlus.exe"}),
                    wait_exit=0, sleep=lambda s: None)
    with s:
        pass
    assert srv.quit == 1 and len(s.warnings) == 1
    assert "PID 4242" in s.warnings[0] and "other Aspen sessions were not touched" in s.warnings[0]


# ---------------------------------------------------------------------------
# com-sweep
# ---------------------------------------------------------------------------
def test_sweep_three_points(model, server, tmp_path, capsys):
    out = tmp_path / "sweep"
    code, text, _ = fw_main(["com-sweep", model, "--out", out, "--vary", "\\Data\\Blocks\\R1\\Input\\TEMP=30,600,50",
                             "--read", "\\Data\\Streams\\PROD\\Output\\TEMP_OUT\\MIXED,\\Data\\Blocks\\R1\\Output\\QCALC"],
                            capsys)
    assert code == 1                                         # the 600 C point has errors
    rows = (out / "sweep.csv").read_text(encoding="utf-8").splitlines()
    assert rows[0] == ("point,\\Data\\Blocks\\R1\\Input\\TEMP [C],status,verdict,CVSTAT,RSTAT,SENSSTAT,PROPSTAT,PPSTAT,"
                       "PCESSTAT,CSSTAT,\\Data\\Streams\\PROD\\Output\\TEMP_OUT\\MIXED [C],"
                       "\\Data\\Blocks\\R1\\Output\\QCALC [cal/sec]")
    assert rows[1].startswith("1,30,completed,ok,0,0,,,0,,,30,-12345.6")
    assert rows[2].startswith("2,600,completed,errors,1")
    assert len(rows) == 4 and server.runs == [1, 1, 1] and server.quit == 1
    assert "| 3 | R1 Input\\TEMP=50 | completed (ok) | 50 C; -12345.6 cal/sec |" in text


def test_sweep_refusals(model, server, tmp_path):
    with pytest.raises(com.Refused, match="same number of values"):
        com.sweep(model, tmp_path / "a", ["\\Data\\Blocks\\R1\\Input\\TEMP=1,2", "\\Data\\Blocks\\R1\\Input\\PRES=1"],
                  ["\\Data"])
    with pytest.raises(com.Refused, match="at least one result path"):
        com.sweep(model, tmp_path / "b", ["\\Data\\Blocks\\R1\\Input\\TEMP=1,2"], [" "])
    with pytest.raises(com.Refused, match="no node"):
        com.sweep(model, tmp_path / "c", ["\\Data\\Blocks\\XX\\Input\\TEMP=1,2"], ["\\Data"])
    assert not (tmp_path / "c").exists()


def test_sweep_continues_after_a_rejected_value(model, server, tmp_path):
    log = com.sweep(model, tmp_path / "s", ["\\Data\\Blocks\\R1\\Input\\TEMP=30,rejected,50"],
                    ["\\Data\\Streams\\PROD\\Output\\TEMP_OUT\\MIXED"])
    assert [p["status"] for p in log["points"]] == ["completed", "failed: value not accepted", "completed"]


# ---------------------------------------------------------------------------
# com-edit
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("direct", [True, False], ids=["port.Add", "port.Elements.Add"])
def test_edit_adds_a_heater_with_two_streams(model, tmp_path, monkeypatch, capsys, direct):
    srv = fake_aspen.FakeAspen(direct_ports=direct)
    monkeypatch.setattr(com, "start_server", fake_aspen.factory(srv))
    monkeypatch.setattr(com, "server_processes", lambda: {})
    out = tmp_path / "edit1"
    code, text, _ = fw_main(["com-edit", model, "--out", out, "--add-stream", "S9", "--add-stream", "S10!MATERIAL",
                             "--add-block", "H1!HEATER", "--connect", "H1:F(IN)=S9", "--connect", "h1:p(out)=s10",
                             "--set", "\\Data\\Blocks\\H1\\Input\\TEMP=80"], capsys)
    assert code == 0, text
    ports = srv.find("\\Data\\Blocks\\H1\\Ports")
    assert [s.Name for s in ports.Elements.Item("F(IN)").Elements] == ["S9"]
    assert [s.Name for s in ports.Elements.Item("P(OUT)").Elements] == ["S10"]
    assert "; block H1" in (out / "Plant.bkp").read_text(encoding="latin-1")
    assert (out / "Plant.inp").is_file() and not (out / "Plant.rep").exists()     # no --run: no report
    log = json.loads((out / "automation-log.json").read_text(encoding="utf-8"))
    assert [e["op"] for e in log["edits"]] == ["add-stream", "add-stream", "add-block", "connect", "connect"]
    assert log["edits"][2]["ports"] == ["F(IN)", "P(OUT)"]
    assert "Open " in text and "Plant.bkp in Aspen Plus to see the change" in text


@pytest.mark.parametrize("args, why", [
    ([], "nothing to do"),
    (["--add-block", "H1"], "needs NAME!TYPE"),
    (["--add-block", "TOOLONGNAME!HEATER"], "needs NAME!TYPE"),
    (["--add-block", "R1!HEATER"], "block R1 exists already"),
    (["--add-stream", "FEED"], "stream FEED exists already"),
    (["--add-stream", "Q1!ENERGY"], "use MATERIAL, HEAT or WORK"),
    (["--connect", "R1:F(IN)=S77"], "no stream S77 (there are: FEED, PROD); add it with --add-stream"),
    (["--connect", "R1:Q(IN)=FEED"], "no port Q(IN) on R1 (there are: F(IN), P(OUT))"),
    (["--connect", "R1-F(IN)-FEED"], "needs BLOCK:PORT=STREAM"),
    (["--disconnect", "R1:P(OUT)=FEED"], "stream FEED is not connected to R1 port P(OUT)"),
    (["--remove-block", "R9"], "no block R9"),
])
def test_edit_refusals(model, server, tmp_path, capsys, args, why):
    code, _, err = fw_main(["com-edit", model, "--out", tmp_path / "e"] + args, capsys)
    assert code == 2 and why in err, err
    assert not (tmp_path / "e").exists()


def test_edit_remove_disconnect_and_run(model, server, tmp_path):
    log = com.edit(model, tmp_path / "e2", disconnect=["R1:F(IN)=FEED"], remove_blocks=[], add_blocks=["B2=HEATER"],
                   run_after=True)
    assert [s.Name for s in server.find("\\Data\\Blocks\\R1\\Ports\\F(IN)").Elements] == []
    assert log["run"]["status"] == "completed" and (tmp_path / "e2" / "Plant.rep").is_file()
    log = com.edit(model, tmp_path / "e3", remove_blocks=["r1"])
    assert log["edits"] == [{"op": "remove-block", "block": "R1"}]
