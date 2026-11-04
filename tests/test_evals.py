"""The agent-neutral evals: case format, triggers, agents.toml, and run.py end to end with a fake
agent and a fake grader (no agent CLI or account needed)."""
import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

from conftest import ROOT

EVALS = ROOT / "evals"
CASES = sorted(p for p in (EVALS / "cases").iterdir() if p.is_dir())
CHECK_TYPES = {"regex", "not_regex", "file_exists", "file_contains", "skill_loaded"}
AGENT_TOOL_NAMES = re.compile(r"\b(TodoWrite|AskUserQuestion|WebFetch|WebSearch)\b|`(Read|Write|Edit|Bash|Glob|Grep|Skill)`"
                              r"|allowed_tools|max_turns|\bClaude\b")


def load_run():
    spec = importlib.util.spec_from_file_location("evals_run", EVALS / "run.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


run = load_run()


def test_twelve_cases_in_the_new_format():
    assert len(CASES) == 12
    assert not [p for p in EVALS.iterdir() if p.is_dir() and (p / "graders").is_dir()], "old format left over"
    for d in CASES:
        meta, prompt = run._front_matter((d / "prompt.md").read_text(encoding="utf-8"))
        assert meta.get("description") and len(prompt) > 40, d.name
        rubric = (d / "rubric.md").read_text(encoding="utf-8")
        assert "PASS" in rubric and "FAIL" in rubric, d.name
        for text in (prompt, rubric):
            assert not AGENT_TOOL_NAMES.search(text), (d.name, AGENT_TOOL_NAMES.search(text).group(0))
        if (d / "checks.json").is_file():
            checks = json.loads((d / "checks.json").read_text(encoding="utf-8"))
            assert checks and all(c["type"] in CHECK_TYPES for c in checks), d.name
            for c in checks:
                if "pattern" in c:
                    re.compile(c["pattern"])
        if meta.get("fixtures") == "true":
            assert (d / "fixtures").is_dir(), d.name


def test_new_cases_from_build_mode_and_freshness():
    ids = {d.name for d in CASES}
    assert {"build-from-paper", "run-review", "stale-files", "automation-sweep"} <= ids


def test_triggers():
    data = json.loads((EVALS / "triggers.json").read_text(encoding="utf-8"))
    prompts = data["prompts"]
    assert len(prompts) == 20 and sum(p["should_trigger"] for p in prompts) == 10
    assert len({p["id"] for p in prompts}) == 20
    near = " ".join(p["prompt"] for p in prompts if not p["should_trigger"]).lower()
    for word in ("hysys", ".ada", "sql server", "coolprop", "colorado", "matlab"):
        assert word in near, word


def test_agents_toml_reader():
    cfg = run.load_toml(EVALS / "agents.toml")
    claude, copilot = cfg["agents"]["claude"], cfg["agents"]["copilot"]
    assert claude["command"][:3] == ["claude", "-p", "--output-format"] and claude["prompt_via"] == "stdin"
    assert "Bash(python *)" in claude["command"] and claude["skill_pattern"].startswith('"name"')
    assert copilot["command"][:3] == ["copilot", "-p", "{prompt}"] and "--no-ask-user" in copilot["command"]
    assert cfg["grader"]["command"][0] == "claude"
    try:
        import tomllib
    except ImportError:
        return
    with open(EVALS / "agents.toml", "rb") as fh:
        assert tomllib.load(fh) == cfg                    # the small reader agrees with tomllib


FAKE_AGENT = r'''
import json, pathlib, subprocess, sys
prompt = sys.stdin.read()
low = prompt.lower()
if "aspen plus" in low or ".rep" in low or "v0.04" in low:
    print(json.dumps({"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": "Skill", "input": {"skill": "aspen-plus"}}]}}))
answer = "I cannot help with that here."
if "v0.04" in prompt:
    fw = pathlib.Path(".claude", "skills", "aspen-plus", "scripts", "fw.py")
    answer = subprocess.run([sys.executable, str(fw), "check", "v0.04/demo.rep", "--expect", "v0.04/expected.csv"],
                            capture_output=True, text=True).stdout
elif "caustic_absorber.inp" in prompt:
    pathlib.Path("caustic_absorber.inp").write_text("PROPERTIES ELECNRTL TRUE-COMPS=YES\n")
    answer = "Wrote caustic_absorber.inp. Open it with File > Open > Input Files."
print(json.dumps({"type": "result", "result": answer}))
'''

FAKE_GRADER = r'''
import sys
text = sys.stdin.read()
print("VERDICT: PASS\nThe table shows the failing temperature." if "Product temperature" in text or "Wrote caustic" in text
      else "VERDICT: FAIL\nNo answer.")
'''


@pytest.fixture
def fake_config(tmp_path):
    agent, grader = tmp_path / "fake_agent.py", tmp_path / "fake_grader.py"
    agent.write_text(FAKE_AGENT, encoding="utf-8")
    grader.write_text(FAKE_GRADER, encoding="utf-8")
    cfg = tmp_path / "agents.toml"
    cfg.write_text(f"""[agents.fake]
command = ['{sys.executable}', '{agent}']
prompt_via = "stdin"
answer = "claude-stream-json"
skill_pattern = '"name"\\s*:\\s*"Skill".{{0,400}}aspen-plus'
install = "claude"

[grader]
command = ['{sys.executable}', '{grader}']
prompt_via = "stdin"
""", encoding="utf-8")
    return cfg


def test_run_end_to_end_with_a_fake_agent(tmp_path, fake_config, capsys):
    out = tmp_path / "results"
    assert run.main(["--agent", "fake", "--config", str(fake_config), "--out", str(out),
                     "--cases", "run-review,inp-electrolyte,export-cpm", "--triggers"]) == 0
    day = next(out.iterdir())
    summary = json.loads((day / "fake" / "summary.json").read_text(encoding="utf-8"))
    res = {r["case"]: r for r in summary["results"]}
    assert res["run-review"]["pass"], res["run-review"]
    assert all(c["ok"] for c in res["run-review"]["checks"]) and res["run-review"]["skill_loaded"]
    assert res["inp-electrolyte"]["pass"] and res["inp-electrolyte"]["checks"][0]["ok"]
    assert (day / "fake" / "inp-electrolyte" / "1" / "files" / "caustic_absorber.inp").is_file()
    assert not res["export-cpm"]["pass"] and res["export-cpm"]["rubric"]["verdict"] == "FAIL"
    trig = summary["triggers"]
    prompts = json.loads((EVALS / "triggers.json").read_text(encoding="utf-8"))["prompts"]
    loads = lambda p: any(w in p.lower() for w in ("aspen plus", ".rep", "v0.04"))
    tp = sum(1 for p in prompts if p["should_trigger"] and loads(p["prompt"]))
    assert trig["precision"] == 1.0 and trig["recall"] == pytest.approx(tp / 10)
    md = (day / "fake" / "summary.md").read_text(encoding="utf-8")
    assert "| run-review | 1 | 1/1 | 1/1 | 1/1 | 1/1 |" in md and "## Triggers" in md and "Precision 1.00" in md


def test_dry_run_prints_the_commands(capsys):
    assert run.main(["--agent", "claude", "--dry-run", "--cases", "stale-files"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("stale-files: claude -p --output-format stream-json") and out.rstrip().endswith("< prompt")
    assert run.main(["--agent", "copilot", "--dry-run", "--cases", "stale-files"]) == 0
    assert "copilot -p <prompt> -s --no-ask-user" in capsys.readouterr().out
