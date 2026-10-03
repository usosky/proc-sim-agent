import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "plugins" / "aspen-plus" / "skills" / "aspen-plus" / "scripts"
EXAMPLE = ROOT / "examples" / "joule-formic-acid"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "tools"))

import samples  # noqa: E402


@pytest.fixture
def mahome(tmp_path, monkeypatch):
    """Isolated ModelAide data folder."""
    home = tmp_path / "mahome"
    monkeypatch.setenv("MODELAIDE_HOME", str(home))
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
