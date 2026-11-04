"""The skill follows the Agent Skills specification (agentskills.io) and the portability rules of
this repository: no agent-specific keys, paths, tool names or shell syntax."""
import re

import pytest

import skillmeta
from conftest import SKILL_DIR

SKILL = SKILL_DIR / "SKILL.md"
ALLOWED_KEYS = {"name", "description", "license", "compatibility", "metadata"}
TEXT_FILES = [SKILL] + sorted((SKILL_DIR / "references").glob("*.md"))

# agent-specific variables, tool names used as tool references, Claude-only frontmatter keys
FORBIDDEN = [
    r"\$\{?CLAUDE_[A-Z_]+", r"\bCLAUDE_PLUGIN_ROOT\b", r"\bClaude\b",
    r"\b(TodoWrite|AskUserQuestion|WebFetch|WebSearch)\b",
    r"`(Read|Write|Edit|Bash|Glob|Grep|Skill|Task)`",
    r"\b(Read|Write|Edit|Bash|Glob|Grep|Skill|Task) tool\b", r"\bBash\(",
    r"^(allowed-tools|argument-hint|context|disable-model-invocation|user-invocable):",
]
# shell syntax that does not work in both PowerShell and Git Bash
NOT_PORTABLE = [r"^\s*export \w+=", r"\$\(", r"&&", r"\|\|", r";\s*(fw|python|py) "]


def frontmatter():
    fm, body, _ = skillmeta.read(SKILL)
    return fm, body


def test_frontmatter_keys():
    fm, _ = frontmatter()
    assert set(fm) <= ALLOWED_KEYS, set(fm) - ALLOWED_KEYS
    assert {"name", "description"} <= set(fm)


def test_name():
    name = frontmatter()[0]["name"]
    assert re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", name), "lowercase letters, digits, single hyphens"
    assert len(name) <= 64 and name == SKILL_DIR.name


def test_description_fits_the_budget():
    # the spec allows 1,024 characters; Copilot and Codex fit every skill's description into a
    # shared budget, so stay at 800 or less
    d = frontmatter()[0]["description"]
    assert 200 <= len(d) <= 800, len(d)
    for word in ("Aspen Plus", ".bkp", ".inp", ".his", ".rep", "RadFrac", "Design Spec", "convergence"):
        assert word in d, word


def test_license_compatibility_metadata():
    fm, _ = frontmatter()
    assert fm["license"] == "MIT"
    assert 1 <= len(fm["compatibility"]) <= 500
    meta = fm["metadata"]
    assert isinstance(meta, dict) and meta, "metadata is a map"
    assert all(isinstance(k, str) and isinstance(v, str) for k, v in meta.items())
    assert {"author", "version", "homepage", "aspen-plus-tested", "last-reviewed"} <= set(meta)
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", meta["last-reviewed"])


def test_size():
    _, body = frontmatter()
    assert len(SKILL.read_text(encoding="utf-8").splitlines()) < 500
    assert len(body) / 4 < 5000, "about 5,000 tokens at most (4 characters per token)"


@pytest.mark.parametrize("path", TEXT_FILES, ids=lambda p: p.name)
def test_no_agent_specific_tokens(path):
    text = path.read_text(encoding="utf-8")
    for rx in FORBIDDEN:
        m = re.search(rx, text, re.M)
        assert not m, f"{path.name}: {m.group(0)!r}"


@pytest.mark.parametrize("path", TEXT_FILES, ids=lambda p: p.name)
def test_commands_work_in_powershell_and_git_bash(path):
    text = path.read_text(encoding="utf-8")
    for rx in NOT_PORTABLE:
        m = re.search(rx, text, re.M)
        assert not m, f"{path.name}: {m.group(0)!r}"
    assert "```bash" not in text, "use ```text for commands: they must run in PowerShell too"


def test_references_are_linked_and_exist():
    _, body = frontmatter()
    linked = set(re.findall(r"references/([A-Za-z0-9_.-]+\.md)", body))
    present = {p.name for p in (SKILL_DIR / "references").glob("*.md")}
    assert linked == present, {"not linked": present - linked, "missing": linked - present}


def test_links_are_one_level_deep():
    _, body = frontmatter()
    for ref in re.findall(r"\b((?:references|templates|scripts|assets)/[^\s`)\]|,;]+)", body):
        ref = ref.rstrip(".:")
        assert ref.count("/") == 1, f"{ref}: keep file references one level deep"
        assert (SKILL_DIR / ref).exists() or ref.endswith(("/", "...")), ref


def test_no_symlinks_in_the_skill():
    assert not [p for p in SKILL_DIR.rglob("*") if p.is_symlink()]


def test_skill_ships_only_what_an_agent_loads():
    tops = {p.name for p in SKILL_DIR.iterdir() if p.name != "__pycache__"}
    assert tops <= {"SKILL.md", "references", "templates", "scripts", "assets"}, tops
