"""Repository consistency: release metadata, privacy of tracked files, .gitignore. The layout, the
manifests and the one-version rule are in test_directory_preflight.py (P1-P16)."""
import json
import re

from conftest import ROOT


def _json(*parts):
    return json.loads(ROOT.joinpath(*parts).read_text(encoding="utf-8"))


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
    # the plugin folder (with its .claude-plugin), the marketplace and everything else that is shipped
    shipped = [str(p.relative_to(ROOT)) for d in ("plugins", ".claude-plugin", "evals", "tools", "tests", "docs",
                                                  "assets", ".github")
               for p in (ROOT / d).rglob("*") if p.is_file() and "__pycache__" not in p.parts
               and not (d == "evals" and "results" in p.relative_to(ROOT / d).parts[:1])]   # local eval output
    shipped += [f for f in ("README.md", "LICENSE", "NOTICE.md", "CHANGELOG.md", "CITATION.cff", ".zenodo.json",
                            "CONTRIBUTING.md", ".gitattributes") if (ROOT / f).is_file()]
    assert "plugins/proc-sim-agent/.claude-plugin/plugin.json" in [s.replace("\\", "/") for s in shipped]
    res = subprocess.run(["git", "check-ignore", "--no-index", "--stdin"], cwd=ROOT, input="\n".join(shipped),
                         capture_output=True, text=True)
    assert res.stdout.strip() == "", f"ignored by .gitignore: {res.stdout}"
