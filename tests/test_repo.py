"""Repository consistency: layout, manifests, one version, SKILL.md, privacy of tracked files."""
import json
import re

import skillmeta
from conftest import ROOT, SKILL_DIR

SKILL = SKILL_DIR / "SKILL.md"
SCHEMA = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"


def _json(*parts):
    return json.loads(ROOT.joinpath(*parts).read_text(encoding="utf-8"))


def test_layout():
    """One copy of the skill, at skills/aspen-plus; tests and evals outside it."""
    assert SKILL.is_file()
    assert not (ROOT / "plugins").exists(), "the old plugins/ tree must be gone"
    assert not (SKILL_DIR / "tests").exists() and not (SKILL_DIR / "evals").exists()
    # Claude Code reads .claude-plugin/plugin.json; with "strict": false it would conflict
    # with the marketplace entry's skills list, so there must be none anywhere
    assert not list(ROOT.rglob(".claude-plugin/plugin.json"))


def test_agent_plugins_manifest():
    plugin = _json("plugin.json")
    assert plugin["$schema"] == SCHEMA
    assert plugin["name"] == "proc-sim-agent" and plugin["license"] == "MIT"


def test_claude_marketplace_entry():
    market = _json(".claude-plugin", "marketplace.json")
    assert market["name"] == "proc-sim-agent"
    entry = next(p for p in market["plugins"] if p["name"] == "aspen-plus")
    assert entry["source"] == "./" and entry["strict"] is False
    assert entry["skills"] == ["./skills/aspen-plus"]


def test_one_version_everywhere():
    """plugin.json, the marketplace entry (Claude Code reads the version there, as the entry is
    the manifest), SKILL.md metadata, fwlib.__version__, CITATION.cff and .zenodo.json carry the
    same version."""
    from fwlib import __version__
    version = _json("plugin.json")["version"]
    entry = next(p for p in _json(".claude-plugin", "marketplace.json")["plugins"] if p["name"] == "aspen-plus")
    assert entry["version"] == version
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
    shipped = [str(p.relative_to(ROOT)) for d in ("skills", "evals", "tools", "tests", "examples", "docs",
                                                  ".claude-plugin")
               for p in (ROOT / d).rglob("*") if p.is_file() and "__pycache__" not in p.parts
               and not (d == "evals" and "results" in p.relative_to(ROOT / d).parts[:1])]   # local eval output
    shipped.append("plugin.json")
    res = subprocess.run(["git", "check-ignore", "--no-index", "--stdin"], cwd=ROOT, input="\n".join(shipped),
                         capture_output=True, text=True)
    assert res.stdout.strip() == "", f"ignored by .gitignore: {res.stdout}"
