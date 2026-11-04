"""tools/install_skill.py: copies the skill (no symlinks), never touches the data folder,
warns about duplicate copies."""
import os
import subprocess
import sys

import pytest

from conftest import ROOT, SKILL_DIR

TOOL = ROOT / "tools" / "install_skill.py"


@pytest.fixture
def home(tmp_path):
    h = tmp_path / "profile"
    (h / ".proc-sim-agent" / "index").mkdir(parents=True)
    (h / ".proc-sim-agent" / "config.json").write_text("{}", encoding="utf-8")
    return h


def run(home, *args, ok=(0,)):
    env = dict(os.environ, HOME=str(home), USERPROFILE=str(home))
    p = subprocess.run([sys.executable, str(TOOL), *map(str, args)], capture_output=True, text=True,
                       encoding="utf-8", env=env, timeout=120)
    assert p.returncode in ok, f"exit {p.returncode}\n{p.stdout}\n{p.stderr}"
    return p.stdout + p.stderr


def test_install_update_uninstall(home):
    dest = home / ".claude" / "skills" / "aspen-plus"
    out = run(home, "--target", "claude")
    assert (dest / "SKILL.md").is_file() and (dest / "scripts" / "fw.py").is_file()
    assert not list(dest.rglob("__pycache__")) and not [p for p in dest.rglob("*") if p.is_symlink()]
    assert sorted(p.name for p in dest.iterdir()) == sorted(p.name for p in SKILL_DIR.iterdir()
                                                            if p.name != "__pycache__")
    assert "Start a new agent session" in out
    assert "already exists" in run(home, "--target", "claude", ok=(1,))
    (dest / "stale.txt").write_text("old", encoding="utf-8")
    run(home, "--target", "claude", "--force")
    assert not (dest / "stale.txt").exists()
    run(home, "--target", "claude", "--uninstall")
    assert not dest.exists()
    assert (home / ".proc-sim-agent" / "config.json").read_text(encoding="utf-8") == "{}"   # untouched


def test_dry_run_changes_nothing(home):
    out = run(home, "--target", "copilot", "--dry-run")
    assert "would copy" in out and not (home / ".copilot").exists()


@pytest.mark.parametrize("kind, folder", [("github", ".github"), ("claude", ".claude"), ("agents", ".agents")])
def test_project_install(home, tmp_path, kind, folder):
    proj = tmp_path / "My Project"
    run(home, "--project", proj, "--project-kind", kind)
    assert (proj / folder / "skills" / "aspen-plus" / "SKILL.md").is_file()


def test_duplicate_copies_are_reported(home):
    run(home, "--target", "copilot")
    out = run(home, "--target", "agents")          # Copilot reads both ~/.copilot and ~/.agents
    assert "GitHub Copilot will see 2 copies" in out
    out = run(home, "--target", "claude")          # Claude Code reads only ~/.claude: no warning for it
    assert "Claude Code will see" not in out


def test_refuses_to_remove_a_folder_that_is_not_the_skill(home):
    other = home / ".claude" / "skills" / "aspen-plus"
    other.mkdir(parents=True)
    (other / "SKILL.md").write_text("---\nname: something-else\ndescription: x\n---\n", encoding="utf-8")
    assert "not removing" in run(home, "--target", "claude", "--uninstall", ok=(1,))
    assert "not replacing" in run(home, "--target", "claude", "--force", ok=(1,))
    assert other.exists()
