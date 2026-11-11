"""Repository consistency: layout, manifests, one version, SKILL.md, privacy of tracked files."""
import json
import re

import skillmeta
from conftest import PLUGIN_DIR, ROOT, SKILL_DIR

SKILL = SKILL_DIR / "SKILL.md"
SCHEMA = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"


def _json(*parts):
    return json.loads(ROOT.joinpath(*parts).read_text(encoding="utf-8"))


def test_layout():
    """One copy of the skill, in the plugin folder plugins/proc-sim-agent; tests and evals outside it."""
    assert SKILL.is_file()
    assert not (ROOT / "skills").exists() and not (ROOT / "plugin.json").exists()
    assert not (SKILL_DIR / "tests").exists() and not (SKILL_DIR / "evals").exists()
    found = [p.relative_to(ROOT).as_posix() for p in ROOT.rglob(".claude-plugin/plugin.json")]
    assert found == ["plugins/proc-sim-agent/.claude-plugin/plugin.json"]


def test_agent_plugins_manifest():
    plugin = json.loads((PLUGIN_DIR / "plugin.json").read_text(encoding="utf-8"))
    assert plugin["$schema"] == SCHEMA
    assert plugin["name"] == "proc-sim-agent" and plugin["license"] == "MIT"


def test_claude_marketplace_entry():
    market = _json(".claude-plugin", "marketplace.json")
    assert market["name"] == "proc-sim-agent"
    [entry] = market["plugins"]
    assert entry["name"] == "proc-sim-agent" and entry["source"] == "./plugins/proc-sim-agent"
    assert not {"strict", "skills", "version"} & set(entry)       # the plugin manifest is the one source


def test_one_version_everywhere():
    """Both manifests in the plugin folder, SKILL.md metadata, fwlib.__version__, CITATION.cff and
    .zenodo.json carry the same version; the marketplace entry carries none."""
    from fwlib import __version__
    version = json.loads((PLUGIN_DIR / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))["version"]
    assert json.loads((PLUGIN_DIR / "plugin.json").read_text(encoding="utf-8"))["version"] == version
    assert __version__ == version
    assert re.search(rf"^version: {re.escape(version)}$", (ROOT / "CITATION.cff").read_text(encoding="utf-8"), re.M)
    assert _json(".zenodo.json")["version"] == version
    assert skillmeta.read(SKILL)[0]["metadata"]["version"] == version


def test_zenodo_funding():
    zen = _json(".zenodo.json")
    assert zen["license"] == "MIT" and zen["grants"][0]["id"].endswith("101177949")


def test_no_private_or_vendor_files_tracked():
    bad_ext = {".apw", ".apwz", ".def", ".scr", ".sqlite", ".mcwebhelp"}
    for f in ROOT.rglob("*"):
        if ".git" in f.parts or "__pycache__" in f.parts or ".pytest_cache" in f.parts:
            continue
        if f.is_file():
            assert f.suffix.lower() not in bad_ext, f
            assert not re.match(r"^_[0-9a-z]{7}\.", f.name), f


def test_no_licence_lines_or_user_names_in_text_files():
    # placeholders such as "<organisation>" or "..." in the documentation are fine
    rx = re.compile(r"LICENSED TO (?!\[removed\]|<|\.\.\.)\S|DESKTOP-[A-Z0-9]{5,}|\\Users\\[A-Za-z]")
    for f in ROOT.rglob("*"):
        if not f.is_file() or ".git" in f.parts or f.suffix.lower() not in {".his", ".rep", ".cpm", ".bkp", ".md",
                                                                           ".txt", ".json"}:
            continue
        text = f.read_bytes().decode("latin-1")
        assert not rx.search(text), f"{f}: {rx.search(text).group(0)}"


def test_gitignore_does_not_hide_shipped_files():
    import shutil
    import subprocess
    import pytest
    if not shutil.which("git"):
        pytest.skip("git not installed")
    inside = subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], cwd=ROOT, capture_output=True, text=True)
    if inside.returncode != 0:
        pytest.skip("not a git checkout")
    shipped = [str(p.relative_to(ROOT)) for d in ("plugins", "evals", "tools", "tests", "docs",
                                                  ".claude-plugin")
               for p in (ROOT / d).rglob("*") if p.is_file() and "__pycache__" not in p.parts
               and not (d == "evals" and "results" in p.relative_to(ROOT / d).parts[:1])]   # local eval output
    res = subprocess.run(["git", "check-ignore", "--no-index", "--stdin"], cwd=ROOT, input="\n".join(shipped),
                         capture_output=True, text=True)
    assert res.stdout.strip() == "", f"ignored by .gitignore: {res.stdout}"
