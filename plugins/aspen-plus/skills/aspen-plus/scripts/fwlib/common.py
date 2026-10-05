"""Shared helpers: names, data folder, config, console encoding, small utilities.

Everything here is standard-library only so the scripts run on any Python >= 3.8
that ships with Windows, macOS or Linux.
"""
from __future__ import annotations

import datetime as _dt
import glob
import json
import os
import re
import sqlite3
import sys
from pathlib import Path

# The project name lives here (and in the plugin manifests) so a rename is one edit.
APP_NAME = "proc-sim-agent"
APP_TITLE = "proc-sim-agent"
CONFIG_VERSION = 1

# Help systems we know. The root .mcwebhelp file name identifies the product.
PRODUCTS = {
    "aspen-plus": {"title": "Aspen Plus", "root_files": ["apwn.mcwebhelp"]},
    "aspen-hysys": {"title": "Aspen HYSYS", "root_files": ["hysys.mcwebhelp"]},
    "aspen-adsorption": {"title": "Aspen Adsorption", "root_files": ["adsorption.mcwebhelp"]},
}

# Where AspenTech installers usually put the HTML help (checked by `setup --auto`).
DEFAULT_HELP_GLOBS = [
    "C:/ProgramData/AspenTech/*/HtmlHelp",
    "C:/ProgramData/AspenTech/*/*/HtmlHelp",
    "C:/Program Files/AspenTech/*/HtmlHelp",
    "C:/Program Files (x86)/AspenTech/*/HtmlHelp",
]

# Aspen Plus engine version (first line of .bkp, VERSION line of .his) -> release name.
# Engine version printed in .bkp/.his/.rep headers -> release name.
# Engines not listed are shown by their number; add them here when they are confirmed.
ENGINE_TO_RELEASE = {
    "34.0": "V8.8", "35.0": "V9", "36.0": "V10", "37.0": "V11", "38.0": "V12",
    "39.0": "V12.1", "40.0": "V14", "41.0": "V15",
}


def setup_io() -> None:
    """Force UTF-8 console output (Windows consoles default to cp1252)."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # pragma: no cover - very old Pythons / redirected streams
            pass


def data_home() -> Path:
    """Folder that holds config and indexes. Never inside the plugin folder."""
    env = os.environ.get("PROC_SIM_AGENT_HOME")
    base = Path(env).expanduser() if env else Path.home() / ("." + APP_NAME)
    base.mkdir(parents=True, exist_ok=True)
    (base / "index").mkdir(exist_ok=True)
    return base


def config_path() -> Path:
    return data_home() / "config.json"


def load_config() -> dict:
    p = config_path()
    if p.exists():
        try:
            cfg = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            cfg = {}
    else:
        cfg = {}
    cfg.setdefault("version", CONFIG_VERSION)
    cfg.setdefault("help", {})
    cfg.setdefault("library", {"folders": []})
    cfg.setdefault("simulations", {"folders": []})
    return cfg


def save_config(cfg: dict) -> Path:
    cfg["updated"] = now_iso()
    p = config_path()
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(p)
    return p


def now_iso() -> str:
    return _dt.datetime.now().replace(microsecond=0).isoformat()


def fts5_available() -> bool:
    try:
        con = sqlite3.connect(":memory:")
        con.execute("CREATE VIRTUAL TABLE t USING fts5(x)")
        con.close()
        return True
    except sqlite3.Error:
        return False


def natural_key(s: str):
    """Sort '1.10_x' after '1.9_x' and '2.3.3' after '2.3'."""
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


def human_size(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024.0
    return f"{n:.1f} GB"


def mtime_str(p: Path) -> str:
    try:
        return _dt.datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
    except OSError:
        return "?"


def read_text_any(path: Path) -> str:
    """Read a text file whatever its encoding (Aspen writes ANSI/cp1252)."""
    raw = Path(path).read_bytes()
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return raw.decode(enc).replace("\r\n", "\n").replace("\r", "\n")
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1", errors="replace")


def expand_globs(patterns) -> list:
    out = []
    for pat in patterns:
        out.extend(sorted(glob.glob(pat)))
    return out


def safe_name(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", s).strip("-") or "x"


def print_json(obj) -> None:
    print(json.dumps(obj, indent=2, ensure_ascii=False, default=str))


def truncate(s: str, n: int) -> str:
    s = s or ""
    return s if len(s) <= n else s[: max(0, n - 3)].rstrip() + "..."


def fmt_num(x, digits: int = 4) -> str:
    """Compact engineering formatting: 0.000123 -> 1.23e-04, 211.364 -> 211.36, 123456.7 -> 123457."""
    if x is None:
        return ""
    try:
        v = float(x)
    except (TypeError, ValueError):
        return str(x)
    if v == 0:
        return "0"
    a = abs(v)
    if a >= 1e6 or a < 1e-3:
        return f"{v:.{max(digits - 1, 1)}e}"
    if a >= 1e5:
        return f"{v:.0f}"
    if a >= 100:  # keep one or two decimals for values compared with papers (211.36, 9731.6)
        return f"{v:.{max(digits + 1, 5)}g}"
    return f"{v:.{digits}g}"
