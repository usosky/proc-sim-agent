"""Live automation tests (docs/live-tests.md L1-L3, L6). They need Windows, pywin32 and a licensed
Aspen Plus, and run only with PSA_LIVE_ASPEN=1. They copy an official AspenTech example from
PSA_ASPEN_EXAMPLES (default: the examples folder `setup --auto` finds) into a temporary folder;
nothing from the examples is kept or committed."""
import importlib.util
import os
import shutil
import sys
from pathlib import Path

import pytest

from conftest import examples_folder
from fwlib import check, com

LIVE = (sys.platform == "win32" and os.environ.get("PSA_LIVE_ASPEN") == "1"
        and importlib.util.find_spec("win32com") is not None)
pytestmark = [pytest.mark.aspen,
              pytest.mark.skipif(not LIVE, reason="live Aspen Plus tests: Windows, pywin32, PSA_LIVE_ASPEN=1")]


def example(tmp_path, largest=False) -> Path:
    bkps = sorted(examples_folder().rglob("*.bkp"), key=lambda f: f.stat().st_size)
    if not bkps:
        pytest.skip("no .bkp in the examples folder")
    src = bkps[-1] if largest else bkps[0]
    dest = tmp_path / "example"
    dest.mkdir()
    shutil.copy2(src, dest / src.name)
    return dest / src.name


def test_l1_server_starts_and_quits():
    res = com.check(start=True)
    assert res["registry"]["registered"], res
    assert res["start"]["ok"], res["start"]
    assert not res["start"]["warnings"], res["start"]["warnings"]       # no server left running


def test_l2_tree_and_values(tmp_path):
    model = example(tmp_path)
    t = com.tree(model, node="\\Data\\Streams", depth=1)["tree"]
    names = [c["name"] for c in t.get("children", [])]
    assert names, t
    v = com.get(model, [f"\\Data\\Streams\\{names[0]}\\Output\\TEMP_OUT\\MIXED"])["values"][0]
    assert v["found"], v


def test_l3_run_a_copy(tmp_path):
    model = example(tmp_path)
    log = com.run(model, tmp_path / "run1", timeout=600)
    assert log["run"]["status"] == "completed", log["run"]
    out = tmp_path / "run1"
    for ext in (".bkp", ".rep", ".cpm", ".inp"):
        assert (out / (model.stem + ext)).is_file(), log["files"]
    assert check.load(out / (model.stem + ".rep"))
    assert not log["warnings"], log["warnings"]


def test_l6_timeout_stops_and_quits(tmp_path):
    model = example(tmp_path, largest=True)
    log = com.run(model, tmp_path / "slow", timeout=5)
    assert log["run"]["status"] in ("stopped on timeout", "completed"), log["run"]
    assert not log["warnings"], log["warnings"]                       # Aspen quit, no leftover process
