"""Repository consistency: manifests, SKILL.md, references, privacy of tracked files."""
import json
import re

from conftest import ROOT

PLUGIN = ROOT / "plugins" / "aspen-plus"
SKILL = PLUGIN / "skills" / "aspen-plus" / "SKILL.md"


def _frontmatter(path):
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    assert m, f"{path} has no frontmatter"
    fm = {}
    for line in m.group(1).splitlines():
        k, v = line.split(":", 1)
        fm[k.strip()] = v.strip()
    return fm, text[m.end():]


def test_manifests_agree():
    market = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    plugin = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    entry = next(p for p in market["plugins"] if p["name"] == plugin["name"])
    assert entry["source"] == "./plugins/aspen-plus"
    # the version lives only in plugin.json (Claude Code docs: don't set it in both places)
    assert "version" not in entry
    from fwlib import __version__
    assert __version__ == plugin["version"]
    cff = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
    assert f"version: {plugin['version']}" in cff
    zen = json.loads((ROOT / ".zenodo.json").read_text(encoding="utf-8"))
    assert zen["license"] == "MIT" and zen["grants"][0]["id"].endswith("101177949")


def test_skill_frontmatter_and_size():
    fm, body = _frontmatter(SKILL)
    assert fm["name"] == "aspen-plus" and len(fm["name"]) <= 64
    assert 100 < len(fm["description"]) <= 1024
    assert len(body.splitlines()) < 500


def test_skill_references_exist():
    _, body = _frontmatter(SKILL)
    refs = set(re.findall(r"references/([a-z-]+\.md)", body))
    assert refs, "SKILL.md should point to its references"
    for r in refs:
        assert (SKILL.parent / "references" / r).is_file(), r
    for f in (SKILL.parent / "references").glob("*.md"):
        assert f.name in refs, f"{f.name} is not mentioned in SKILL.md"


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
    shipped = [str(p.relative_to(ROOT)) for d in ("plugins", "tools", "tests", "examples", "docs", ".claude-plugin")
               for p in (ROOT / d).rglob("*") if p.is_file() and "__pycache__" not in p.parts]
    res = subprocess.run(["git", "check-ignore", "--no-index", "--stdin"], cwd=ROOT, input="\n".join(shipped),
                         capture_output=True, text=True)
    assert res.stdout.strip() == "", f"ignored by .gitignore: {res.stdout}"
