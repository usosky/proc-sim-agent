"""Anthropic's plugin directory checks as offline tests (P1-P16), so that a change that would block
or hold a submission fails here and in CI. Source: the directory's pre-submission checklist
(claude.com/docs/plugins/pre-submission-checklist), read on 10 Nov 2026.

The plugin folder is the folder that holds .claude-plugin/plugin.json: plugins/proc-sim-agent.
People who install the plugin receive exactly that folder, and the directory scans every file in
it. File checks use the tracked files (git ls-files) where git is available, else a walk of the
folder without __pycache__."""
import ast
import json
import re
import shutil
import struct
import subprocess
from collections import defaultdict

import pytest

import skillmeta
from conftest import PLUGIN_DIR, ROOT, SKILL_DIR

NAME = "proc-sim-agent"
PLUGIN = "plugins/proc-sim-agent"
SCHEMA = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
INSTALL_LINE = "/plugin install proc-sim-agent --marketplace usosky/proc-sim-agent"
BINARY_OK = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ttf", ".otf", ".woff", ".woff2"}
IMAGES_AND_FONTS = BINARY_OK | {".svg"}
OS_JUNK = {".ds_store", "thumbs.db", "desktop.ini", "__macosx"}
DEVICE_NAMES = {"CON", "PRN", "AUX", "NUL"} | {f"COM{i}" for i in range(1, 10)} | {f"LPT{i}" for i in range(1, 10)}
LFS_POINTER = b"version https://git-lfs.github.com/spec/"


def _json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _manifest():
    return _json(PLUGIN_DIR / ".claude-plugin" / "plugin.json")


def _git(*args):
    if not shutil.which("git"):
        return None
    p = subprocess.run(["git", *args], cwd=ROOT, capture_output=True)
    return p.stdout.decode("utf-8") if p.returncode == 0 else None


def repo_files(prefix: str = "") -> list:
    """Tracked files under prefix (POSIX paths from the repository root)."""
    out = _git("ls-files", "-z", "--", prefix or ".")
    if out is not None:
        return sorted(f for f in out.split("\0") if f and (ROOT / f).exists())
    base = ROOT / prefix if prefix else ROOT
    skip = {".git", "__pycache__", ".pytest_cache"}
    return sorted(p.relative_to(ROOT).as_posix() for p in base.rglob("*")
                  if p.is_file() and not skip & set(p.relative_to(ROOT).parts))


def plugin_files() -> list:
    return repo_files(PLUGIN)


# ---------------------------------------------------------------------------
# manifests
# ---------------------------------------------------------------------------
def test_p1_one_plugin_manifest_in_the_plugin_folder():
    found = sorted(p.relative_to(ROOT).as_posix() for p in ROOT.rglob("plugin.json")
                   if p.parent.name == ".claude-plugin" and ".git" not in p.relative_to(ROOT).parts)
    assert found == [f"{PLUGIN}/.claude-plugin/plugin.json"]


def test_p2_name():
    name = _manifest()["name"]
    assert name == NAME
    assert len(name) <= 64 and re.fullmatch(r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?", name)


def test_p3_display_name_and_author():
    m = _manifest()
    assert m["displayName"] == m["name"]
    assert m["author"]["name"] == "Denis Usosky"


def test_p4_required_fields_and_urls():
    m = _manifest()
    for key in ("description", "author", "version", "license"):
        assert m.get(key), f"{key} is not set"
    assert re.fullmatch(r"\d+\.\d+\.\d+", m["version"])
    for key in ("homepage", "repository"):
        assert m[key].startswith("https://"), key


def test_p5_marketplace():
    market = _json(ROOT / ".claude-plugin" / "marketplace.json")
    assert market["name"] == NAME
    [entry] = market["plugins"]
    assert entry["name"] == _manifest()["name"]
    assert entry["source"] == f"./{PLUGIN}"
    assert not {"strict", "skills", "version"} & set(entry), "the plugin manifest is the one source"


def test_p6_agent_plugins_manifest_agrees():
    ap, m = _json(PLUGIN_DIR / "plugin.json"), _manifest()
    assert ap["$schema"] == SCHEMA
    for key in ("name", "version", "description", "license"):
        assert ap[key] == m[key], key


def test_p7_one_version_everywhere():
    """Both manifests, SKILL.md metadata.version, fwlib.__version__, CITATION.cff and .zenodo.json."""
    from fwlib import __version__
    version = _manifest()["version"]
    found = {
        "plugin.json (Agent Plugins)": _json(PLUGIN_DIR / "plugin.json")["version"],
        "SKILL.md metadata.version": skillmeta.read(SKILL_DIR / "SKILL.md")[0]["metadata"]["version"],
        "fwlib.__version__": __version__,
        ".zenodo.json": _json(ROOT / ".zenodo.json")["version"],
    }
    m = re.search(r"^version:\s*\"?([^\"\s]+)\"?\s*$", (ROOT / "CITATION.cff").read_text(encoding="utf-8"), re.M)
    found["CITATION.cff"] = m.group(1) if m else None
    assert {k: v for k, v in found.items() if v != version} == {}, f".claude-plugin/plugin.json has {version}"


# ---------------------------------------------------------------------------
# README and LICENSE in the plugin folder
# ---------------------------------------------------------------------------
def test_p8_plugin_readme():
    text = (PLUGIN_DIR / "README.md").read_text(encoding="utf-8")
    prose = re.sub(r"^(```|~~~).*?^\1", "", text, flags=re.M | re.S)
    assert len(re.findall(r"[A-Za-z0-9]+(?:['-][A-Za-z0-9]+)*", prose)) >= 40
    assert INSTALL_LINE in text


def test_p9_plugin_licence_is_the_root_licence():
    assert (PLUGIN_DIR / "LICENSE").read_bytes() == (ROOT / "LICENSE").read_bytes()


# ---------------------------------------------------------------------------
# files
# ---------------------------------------------------------------------------
def _file_problems(rel: str, p) -> list:
    """What the directory would block or hold for one file of the plugin folder."""
    problems = []
    parts = rel.lower().split("/")
    if OS_JUNK & set(parts):
        problems.append(f"{rel}: operating-system file")
    if "__pycache__" in parts or p.suffix.lower() in {".pyc", ".pyo"}:
        problems.append(f"{rel}: compiled Python")
    if p.is_symlink():
        return problems + [f"{rel}: symlink"]
    data = p.read_bytes()
    if data.startswith(LFS_POINTER):
        problems.append(f"{rel}: Git LFS pointer")
    if p.suffix.lower() in BINARY_OK:
        return problems
    if len(data) > 256 * 1024:
        problems.append(f"{rel}: {len(data) // 1024} KiB (limit 256 KiB)")
    try:
        data.decode("utf-8")
    except UnicodeDecodeError as e:
        problems.append(f"{rel}: not UTF-8 ({e.reason} at byte {e.start})")
    return problems


def test_p10_plugin_folder_files():
    files = plugin_files()
    assert 0 < len(files) <= 512, len(files)
    problems = [x for f in files for x in _file_problems(f, ROOT / f)]
    staged = _git("ls-files", "-s", "--", PLUGIN)
    if staged is not None:                       # mode 120000 is a symlink, 160000 a submodule
        problems += [f"{line.split(chr(9))[-1]}: git mode {line.split()[0]}" for line in staged.splitlines()
                     if line.split()[0] in {"120000", "160000"}]
    assert not problems, "\n".join(problems)


def test_p10_file_rules(tmp_path):
    files = {"big.md": b"x" * (256 * 1024 + 1), "latin.inp": "TEMP=25 \xb0C".encode("latin-1"),
             "model.bkp": LFS_POINTER + b"v1\noid sha256:0\nsize 1\n", "Thumbs.db": b"",
             "fw.cpython-38.pyc": b"", "logo.png": b"\x89PNG" + bytes(300 * 1024), "ok.md": "°C".encode("utf-8")}
    for name, data in files.items():
        (tmp_path / name).write_bytes(data)
    found = {n: _file_problems(n, tmp_path / n) for n in files}
    assert "256 KiB" in found["big.md"][0] and "not UTF-8" in found["latin.inp"][0]
    assert "LFS" in found["model.bkp"][0] and "operating-system" in found["Thumbs.db"][0]
    assert "compiled" in found["fw.cpython-38.pyc"][0]
    assert found["logo.png"] == [] and found["ok.md"] == []


def _invalid_name(name: str) -> str:
    if re.search(r'[<>:"|?*\\\x00-\x1f]', name):
        return "a character Windows does not allow"
    if name.endswith((".", " ")):
        return "a trailing dot or space"
    if name.split(".")[0].upper() in DEVICE_NAMES:
        return "a Windows device name"
    return ""


def test_p11_names_are_valid_on_windows_and_macos():
    files = repo_files()
    problems = []
    for f in files:
        problems += [f"{f}: {why}" for why in map(_invalid_name, f.split("/")) if why]
    paths = set(files) | {"/".join(f.split("/")[:i]) for f in files for i in range(1, f.count("/") + 1)}
    by_case = defaultdict(list)
    for p in paths:
        by_case[p.lower()].append(p)
    problems += [f"differ only by case: {', '.join(sorted(v))}" for v in by_case.values() if len(v) > 1]
    assert not problems, "\n".join(problems)


def test_p11_name_rules():
    assert _invalid_name("a:b.md") and _invalid_name("notes. ") and _invalid_name("nul.txt")
    assert _invalid_name("COM1") and _invalid_name("x?.md") and not _invalid_name("console.md")
    assert not _invalid_name("CHANGELOG.md") and not _invalid_name(".gitattributes")


def test_p12_gitattributes_rewrite_nothing():
    files = [f for f in repo_files() if f.split("/")[-1] == ".gitattributes"]
    problems = []
    for f in files:
        for n, line in enumerate((ROOT / f).read_text(encoding="utf-8").splitlines(), 1):
            parts = line.split()
            if not parts or parts[0].startswith("#"):
                continue
            problems += [f"{f}:{n}: {attr}" for attr in parts[1:] if attr != "-text"]
    assert not problems, "only -text is allowed (no export-ignore, export-subst, filter, eol, ident, " \
                         "working-tree-encoding or LFS):\n" + "\n".join(problems)


def _png_size(path):
    head = path.read_bytes()[:24]
    sig, _, chunk, width, height = struct.unpack(">8sI4sII", head)
    assert sig == b"\x89PNG\r\n\x1a\n" and chunk == b"IHDR", f"{path.name} is not a PNG"
    return width, height


def test_p13_images_fonts_and_icon():
    files = plugin_files()
    media = [f for f in files if (ROOT / f).suffix.lower() in IMAGES_AND_FONTS]
    manifests = {f"{PLUGIN}/.claude-plugin/plugin.json", f"{PLUGIN}/plugin.json"}
    icon_name = f"{PLUGIN}/.claude-plugin/icon.png"
    problems = []
    for f in files:
        if f in media or (ROOT / f).suffix.lower() in BINARY_OK:
            continue
        text = (ROOT / f).read_bytes().decode("utf-8", errors="replace")     # P10 reports non-UTF-8
        for m in media:
            name = m.split("/")[-1]
            if name in text and not (m == icon_name and f in manifests):    # the manifest may name its icon
                problems.append(f"{f} mentions {name}")
    icon = ROOT / icon_name
    if icon.exists():
        w, h = _png_size(icon)
        if w != h or not 512 <= w <= 2048:
            problems.append(f"icon.png is {w} x {h} px: it must be square, 512 to 2048 px a side")
        if icon.stat().st_size >= 2 * 1024 * 1024:
            problems.append("icon.png is 2 MB or larger")
    assert not problems, "\n".join(problems)


def test_p13_png_header_reader(tmp_path):
    png = tmp_path / "icon.png"
    png.write_bytes(b"\x89PNG\r\n\x1a\n" + struct.pack(">I4sII", 13, b"IHDR", 1024, 1024) + b"\x08\x06\x00\x00\x00")
    assert _png_size(png) == (1024, 1024)


# ---------------------------------------------------------------------------
# disclosure guard: what the scripts can start, open or reach
# ---------------------------------------------------------------------------
WATCHED = ("subprocess", "os.system", "os.popen", "socket", "urllib", "http.client", "ftplib", "smtplib",
           "requests", "winreg", "ctypes", "webbrowser")
# 10 Nov 2026: tasklist and the registry (com.py), gfortran (fortran.py), pdftotext (docsdb.py)
DISCLOSED = {"fwlib/com.py": {"subprocess", "winreg"}, "fwlib/fortran.py": {"subprocess"},
             "fwlib/docsdb.py": {"subprocess"}}


def _watched_uses(source: str) -> set:
    names = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            names |= {node.module} | {f"{node.module}.{a.name}" for a in node.names}
        elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            names.add(f"{node.value.id}.{node.attr}")
        elif isinstance(node, ast.Call) and node.args and isinstance(node.args[0], ast.Constant) \
                and isinstance(node.args[0].value, str):
            func = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", "")
            if func in {"__import__", "import_module"}:
                names.add(node.args[0].value)
    return {w for w in WATCHED if any(n == w or n.startswith(w + ".") for n in names)}


def test_p14_disclosure_guard():
    scripts = SKILL_DIR / "scripts"
    found = {}
    for py in sorted(scripts.rglob("*.py")):
        uses = _watched_uses(py.read_text(encoding="utf-8"))
        if uses:
            found[py.relative_to(scripts).as_posix()] = uses
    assert found == DISCLOSED, (
        "the scripts now start programs or reach resources differently: update the plugin README section "
        "\"What it runs, reads, writes and sends\" and DISCLOSED in this test")
    readme = (PLUGIN_DIR / "README.md").read_text(encoding="utf-8")
    for word in ("gfortran", "pdftotext", "tasklist", "registry"):
        assert word in readme, word
    assert "The scripts use no network" in readme


def test_p14_guard_sees_imports_and_calls():
    src = ("import subprocess\nfrom os import system\nimport urllib.request\nimport importlib\n"
           "importlib.import_module('socket')\nimport os\nos.popen('x')\nimport http\nhttp.client\n")
    assert _watched_uses(src) == {"subprocess", "os.system", "urllib", "socket", "os.popen", "http.client"}
    assert _watched_uses("import json, csv\nfrom pathlib import Path\n") == set()


# ---------------------------------------------------------------------------
# layout
# ---------------------------------------------------------------------------
def test_p15_layout():
    files = repo_files()
    top = {f.split("/")[0] for f in files}
    assert not {"skills", "plugin.json", "examples"} & top, "the skill, the manifest and examples moved or left"
    assert {f.split("/")[1] for f in files if f.startswith("plugins/")} == {NAME}
    assert {f.split("/")[2] for f in plugin_files()} == {".claude-plugin", "plugin.json", "README.md", "LICENSE",
                                                          "skills"}
    assert (SKILL_DIR / "SKILL.md").is_file()
    assert not (SKILL_DIR / "tests").exists() and not (SKILL_DIR / "evals").exists()


def test_p16_aspen_format_files_only_as_fixtures_and_templates():
    """The repository holds synthetic fixtures and templates, no models."""
    allowed = re.compile(r"^(evals/cases/[^/]+/fixtures/|plugins/proc-sim-agent/skills/aspen-plus/templates/)")
    found = [f for f in repo_files() if f.lower().endswith((".bkp", ".his", ".rep", ".cpm", ".inp", ".sum"))]
    assert found, "the eval fixtures and the templates should be found"
    assert [f for f in found if not allowed.match(f)] == []
