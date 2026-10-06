"""fw.py end to end, as Claude runs it (subprocess, isolated data folder)."""
import json
import os
import subprocess
import sys

import pytest

from conftest import SCRIPTS

import samples

FW = SCRIPTS / "fw.py"


def run(args, home, ok=(0,)):
    env = dict(os.environ, PROC_SIM_AGENT_HOME=str(home), PYTHONIOENCODING="utf-8")
    p = subprocess.run([sys.executable, str(FW)] + [str(a) for a in args], capture_output=True, text=True,
                       encoding="utf-8", env=env, timeout=300)
    assert p.returncode in ok, f"exit {p.returncode}\n{p.stdout}\n{p.stderr}"
    return p


def test_setup_index_search_read(tmp_path, help_root):
    home = tmp_path / "home"
    out = run(["setup", "--help-root", help_root], home).stdout
    assert "help: Aspen Plus V15" in out and "help-index" in out
    assert "complete" in run(["help-index"], home).stdout
    hits = json.loads(run(["help-search", "secant bracket", "--json"], home).stdout)
    assert hits[0]["title"] == "Secant Method"
    text = run(["help-read", "Secant Method"], home).stdout
    assert "Check Bounds" in text
    assert "DemoReactor Setup Sheet" in run(["help-read", "830001"], home).stdout
    assert "democonv" in run(["help-toc"], home).stdout
    status = run(["status"], home).stdout
    assert "complete" in status and "7 topics" in status


def test_help_index_reports_incomplete_with_exit_code_3(tmp_path, help_root):
    home = tmp_path / "home"
    run(["setup", "--help-root", help_root], home)
    p = run(["help-index", "--books", "demoblock"], home, ok=(3,))
    assert "INCOMPLETE" in p.stdout
    assert "complete" in run(["help-index"], home).stdout


def test_search_without_index_explains_setup(tmp_path):
    p = run(["help-search", "anything"], tmp_path / "home", ok=(2,))
    assert "setup" in p.stderr


def test_run_file_commands(tmp_path, run_files):
    home = tmp_path / "home"
    out = run(["his", run_files["his"], "--fortran"], home).stdout
    assert "URE07.3" in out and "ACME" not in out and "jdoe" not in out
    assert "FRAC RECYCLE 0.4" in run(["his-diff", run_files["his"], run_files["his_v2"]], home).stdout
    out = run(["rep", run_files["rep"], "--streams", "FEED,PROD"], home).stdout
    assert "| CO2 [kmol/hr] | 10 | 1 |" in out
    assert "Calculations were completed normally" in run(["rep", run_files["rep"]], home).stdout
    assert "converged" in run(["cpm", run_files["cpm"]], home).stdout
    assert "DEMO" in run(["sim-scan", run_files["his"].parent], home).stdout


@pytest.mark.parametrize("cmd", [["his", "--help"], ["rep", "--help"], ["help-index", "--help"]])
def test_help_texts(tmp_path, cmd):
    assert "usage" in run(cmd, tmp_path / "home").stdout.lower()


def test_relative_paths_are_stored_absolute(tmp_path):
    home = tmp_path / "home"
    lib = tmp_path / "work" / "papers"
    lib.mkdir(parents=True)
    (lib / "n.md").write_text("# Notes\n\nWegstein acceleration bounds.\n", encoding="utf-8")
    env = dict(os.environ, PROC_SIM_AGENT_HOME=str(home), PYTHONIOENCODING="utf-8")
    subprocess.run([sys.executable, str(FW), "setup", "--library", "papers"], cwd=lib.parent, env=env,
                   capture_output=True, timeout=120, check=True)
    cfg = json.loads((home / "config.json").read_text(encoding="utf-8"))
    assert cfg["library"]["folders"] == [str(lib.resolve())]
    out = subprocess.run([sys.executable, str(FW), "docs-index"], cwd=tmp_path, env=env, capture_output=True,
                         text=True, timeout=120)
    assert "complete" in out.stdout
    assert "Wegstein" in run(["docs-search", "Wegstein"], home).stdout


def test_examples_commands(tmp_path):
    home = tmp_path / "home"
    root = samples.make_example_library(tmp_path / "Examples")
    assert "examples-index" in run(["setup", "--examples", root], home).stdout
    assert "complete" in run(["examples-index"], home).stdout
    out = run(["examples-search", "brine", "--has", "electrolyte"], home).stdout
    assert "brine_absorber" in out and "guide: brine_absorber.pdf" in out
    hits = json.loads(run(["examples-search", "--block", "RADFRAC", "--json"], home).stdout)
    assert {h["name"] for h in hits} == {"methanol_column", "packed_column"}
    assert "HB.P1" in run(["examples-show", "brine"], home).stdout
    assert "DISS NACL NA+ 1. / CL- 1." in run(["examples-show", "brine", "--chemistry-inp"], home).stdout
    assert "PARAM TEMP=25." in run(["examples-show", "brine", "--section", "BLOCK FLASH2"], home).stdout
    assert "Carbon Capture/Brine absorber" in run(["examples-list"], home).stdout
    assert "examples: 3 models (complete)" in run(["status"], home).stdout
    run(["examples-show", "nothing-like-this"], home, ok=(1,))


def test_examples_without_index_explains_setup(tmp_path):
    p = run(["examples-search", "x"], tmp_path / "home", ok=(2,))
    assert "setup --examples" in p.stderr


def test_inp_check_exit_codes_and_his_export(tmp_path, run_files):
    home = tmp_path / "home"
    good = samples.write(tmp_path / "good.inp", samples.INP_FLASH)
    assert "0 errors" in run(["inp-check", good], home).stdout
    bad = samples.write(tmp_path / "bad.inp", samples.INP_BAD)
    assert "ERROR" in run(["inp-check", bad], home, ok=(1,)).stdout
    out_inp = tmp_path / "demo.inp"
    assert "File > Open" in run(["his", run_files["his"], "--inp", out_inp], home).stdout
    assert "FRAC RECYCLE 0.3" in out_inp.read_text(encoding="utf-8")
    run(["his", run_files["his"], "--inp", out_inp], home, ok=(2,))          # exists and no --force
    run(["his", run_files["his"], "--inp", out_inp, "--force"], home)
    assert "0 errors" in run(["inp-check", run_files["his"]], home).stdout    # a .his is checked via its input


def test_check_command(tmp_path):
    home = tmp_path / "home"
    t = samples.write(tmp_path / "table.txt", samples.STREAM_TABLE)
    out = run(["check", t, "--elements", "C", "--metric", "recovery=flow(GAS, CO2)/elem(FEED, C)"], home).stdout
    assert "recovery = 0.2" in out
    res = json.loads(run(["check", t, "--json", "--streams", "FEED,GAS"], home).stdout)
    assert list(res["streams"]) == ["FEED", "GAS"]
    run(["check", t, "--metric", "no-equals-sign"], home, ok=(2,))
