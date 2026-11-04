import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "skills" / "aspen-plus"
SCRIPTS = SKILL_DIR / "scripts"
EXAMPLE = ROOT / "examples" / "joule-formic-acid"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "tools"))

import samples  # noqa: E402


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
