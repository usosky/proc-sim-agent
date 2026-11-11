import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_DIR = ROOT / "plugins" / "proc-sim-agent"
SKILL_DIR = PLUGIN_DIR / "skills" / "aspen-plus"
SCRIPTS = SKILL_DIR / "scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "tools"))

import samples  # noqa: E402


def examples_folder() -> Path:
    """The Aspen Plus examples folder: PSA_ASPEN_EXAMPLES, else the newest one that `setup --auto` finds.
    Skips the calling test when there is none (always so on Linux and in CI)."""
    from fwlib.common import DEFAULT_EXAMPLES_GLOBS, expand_globs, natural_key
    env = os.environ.get("PSA_ASPEN_EXAMPLES")
    if env:
        if not Path(env).is_dir():
            pytest.skip(f"PSA_ASPEN_EXAMPLES is not a folder: {env}")
        return Path(env)
    found = [p for p in expand_globs(DEFAULT_EXAMPLES_GLOBS) if Path(p).is_dir()]
    if not found:
        pytest.skip("no Aspen Plus examples folder; set PSA_ASPEN_EXAMPLES")
    return Path(max(found, key=natural_key))


@pytest.fixture
def mahome(tmp_path, monkeypatch):
    """Isolated proc-sim-agent data folder."""
    home = tmp_path / "mahome"
    monkeypatch.setenv("PROC_SIM_AGENT_HOME", str(home))
    return home


@pytest.fixture
def help_root(tmp_path):
    return samples.make_help(tmp_path / "HtmlHelp")


@pytest.fixture
def run_files(tmp_path):
    d = tmp_path / "runs"
    return {
        "his": samples.write(d / "DEMO.his", samples.HIS),
        "his_v2": samples.write(d / "v2" / "DEMO.his", samples.HIS_V2),
        "rep": samples.write(d / "demo.rep", samples.REP),
        "cpm": samples.write(d / "DEMO.cpm", samples.CPM),
    }


def pytest_configure(config):
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    config.addinivalue_line("markers", "aspen: needs Windows, pywin32 and a licensed Aspen Plus "
                                       "(run with PSA_LIVE_ASPEN=1; see docs/live-tests.md)")
