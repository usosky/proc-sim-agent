"""Aspen Plus automation (COM): read values, run copies, sweep inputs, edit flowsheets.

Every command opens a copy, never the user's file. pywin32 (win32com, pythoncom) is imported only
when a command starts Aspen Plus, so `fw <command> -h` works without it. Each command starts its
own Aspen Plus server, which takes a licence like the GUI, and always quits it: the licence is
released only then. Processes this command did not start are never touched.

Facts come from the Aspen Plus V15 help, "Using Aspen Plus Via Automation (Happ)" (topic titles in
references/automation.md). Members marked "confirm live" there were not checked against a running
Aspen Plus when this module was written; docs/live-tests.md lists the checks.

Every function takes a `factory` that returns an `Aspen` object, so tests can use a fake server.
"""
from __future__ import annotations

import csv
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from . import __version__
from .common import ENGINE_TO_RELEASE

PROGID = "Apwn.Document"
# Export file types (help topic "Members of Class HappLS"); the server's type library wins
HAPEXP = {"BACKUP": 1, "REPORT": 2, "SUMMARY": 3, "INPUT": 4, "INPUT_GRAPHICS": 5, "RUNMSG": 6,
          "REPORT_INPUT": 7, "REPORT_SUMMARY": 8, "INPUT_WITH_GRAPHICS": 18}
STATUS_PATH = "\\Data\\Results Summary\\Run-Status\\Output"
STATUS_FLAGS = ("CVSTAT", "RSTAT", "SENSSTAT", "PROPSTAT", "PPSTAT", "PCESSTAT", "CSSTAT")
FLAG_TEXT = {0: "no error", 1: "error", 2: "warning"}
FLAG_MEANING = {"CVSTAT": "convergence", "RSTAT": "Calculator and Transfer", "SENSSTAT": "sensitivity",
                "PROPSTAT": "properties", "PPSTAT": "physical properties", "PCESSTAT": "property estimation",
                "CSSTAT": "case study"}
SERVER_IMAGES = ("aspenplus.exe", "apwn.exe", "apmain.exe")
MODEL_EXTS = (".bkp", ".apw")
FROZEN_NAMES = ("frozen", "frozen.md", "frozen.txt")


class AutomationError(RuntimeError):
    """Why automation cannot go on, in words the user can act on."""


class Refused(AutomationError):
    """The command will not act: frozen gate, output folder in use, unknown or read-only node."""


# ---------------------------------------------------------------------------
# the server
# ---------------------------------------------------------------------------
def _pywin32():
    try:
        import pythoncom
        import win32com.client
    except ImportError:
        raise AutomationError("pywin32 is not installed for this Python. Install it, then check again:\n"
                              "  python -m pip install pywin32\n  python scripts/fw.py com-check") from None
    return pythoncom, win32com.client


def explain(err: Exception) -> AutomationError:
    """A COM error as a message the user can act on."""
    text = str(err)
    low = text.lower()
    if "invalid class string" in low or "-2147221005" in low:
        return AutomationError("Aspen Plus is not registered for automation on this PC (no Apwn.Document). "
                               "Run fw com-check; repair the Aspen Plus installation if it is missing.")
    if "licen" in low:
        return AutomationError("No Aspen Plus licence is available (all seats in use, or the licence server "
                               "cannot be reached). Close other Aspen sessions or try later. Details: " + text)
    return AutomationError(f"Aspen Plus automation failed: {text}")


def typelib_constants(app) -> Dict[str, int]:
    """Enum values from the type library of the running server (help: constants such as
    IAP_REINIT_SIMULATION). Read from the installed server, never from a copied file."""
    out: Dict[str, int] = {}
    try:
        import pythoncom
        tlb, _ = app._oleobj_.GetTypeInfo().GetContainingTypeLib()
        for i in range(tlb.GetTypeInfoCount()):
            if tlb.GetTypeInfoType(i) != pythoncom.TKIND_ENUM:
                continue
            ti = tlb.GetTypeInfo(i)
            for j in range(ti.GetTypeAttr().cVars):
                vd = ti.GetVarDesc(j)
                out[ti.GetNames(vd.memid)[0]] = vd.value
    except Exception:       # no type information: the documented defaults apply
        return out
    return out


def _get(obj, attr, default=None):
    try:
        return getattr(obj, attr)
    except Exception:
        return default


def _plain(v):
    """A COM value as JSON-friendly Python."""
    if v is None or isinstance(v, (bool, int, float, str)):
        return v
    if isinstance(v, (list, tuple)):
        return [_plain(x) for x in v]
    return str(v)


def children(node) -> list:
    coll = _get(node, "Elements")
    if coll is None:
        return []
    try:
        return list(coll)
    except Exception:
        n = _get(coll, "Count", 0) or 0
        out = []
        for i in range(n):
            try:
                out.append(coll.Item(i))
            except Exception:
                break
        return out


def _unit(node) -> str:
    u = _get(node, "UnitString", "")            # confirm live (L2)
    return "" if u is None else str(u).strip()


def _try_calls(*calls) -> None:
    """Run the first call that works (for members whose exact form is confirmed live)."""
    err = None
    for c in calls:
        try:
            c()
            return
        except AttributeError as e:
            err = e
        except Exception as e:      # a COM error from the right member: report it
            raise explain(e) from None
    raise AutomationError(f"this Aspen Plus has none of the expected members ({err})")


class Aspen:
    """One Aspen Plus server started by this command."""

    def __init__(self, app, constants: Optional[Dict[str, int]] = None, pump: Callable = None,
                 sleep: Callable = time.sleep, clock: Callable = time.monotonic):
        self.app = app
        self.const = dict(constants or {})
        self.pump = pump or (lambda: None)
        self.sleep, self.clock = sleep, clock

    # files -----------------------------------------------------------------
    def open(self, path: Path) -> None:
        full = os.path.abspath(str(path))
        try:
            if path.suffix.lower() == ".bkp":
                self.app.InitFromArchive2(full)
            else:
                self.app.InitFromFile2(full)
        except Exception as e:
            raise explain(e) from None

    def version(self) -> str:
        for attr in ("Version", "ApplicationVersion"):        # confirm live (L1)
            v = _get(self.app, attr)
            if v:
                return str(v)
        return ""

    def members(self) -> dict:
        """Which of the members this module relies on the server has (com-check --start)."""
        m = {"Version": bool(self.version())}
        try:
            self._running(self.app.Engine)
            m["Engine.IsRunning"] = True
        except Exception:
            m["Engine.IsRunning"] = False
        m["constants"] = len(self.const)
        for k in ("IAP_REINIT_SIMULATION", "HAP_ENTERABLE"):
            m[k] = self.const.get(k)
        m["export_codes_differ"] = {k: [v, self.const["HAPEXP_" + k]] for k, v in HAPEXP.items()
                                    if "HAPEXP_" + k in self.const and self.const["HAPEXP_" + k] != v}
        return m

    def export(self, kind: str, path: Path) -> str:
        """Write one file; '' when done, else the reason."""
        code = self.const.get("HAPEXP_" + kind, HAPEXP[kind])
        full = os.path.abspath(str(path))
        try:
            self.app.Export(code, full)
        except Exception as e:
            if kind != "BACKUP":
                return str(explain(e))
            try:
                self.app.WriteArchive2(full)
            except Exception as e2:
                return str(explain(e2))
        return "" if os.path.exists(full) else "Aspen reported no error but wrote no file"

    def close(self) -> None:
        try:
            self.app.Quit()
        except Exception:
            pass

    # the tree --------------------------------------------------------------
    def node(self, path: str):
        try:
            return self.app.Tree.FindNode(path)
        except Exception:
            return None

    def value(self, path: str) -> dict:
        n = self.node(path)
        if n is None:
            return {"path": path, "found": False}
        kids = children(n)
        if kids:
            return {"path": path, "found": True, "folder": True, "children": len(kids)}
        return {"path": path, "found": True, "value": _plain(_get(n, "Value")), "unit": _unit(n)}

    def tree(self, path: str, depth: int = 2, max_children: int = 60) -> dict:
        root = self.node(path)
        if root is None:
            raise Refused(f"no node {path} in this model (start from com-tree --node \"\\Data\")")
        return _walk(root, path, depth, max_children)

    def set(self, path: str, value) -> dict:
        if re.search(r"\\output(\\|$)", path, re.I):
            raise Refused(f"{path} is a result (Output): only input nodes can be set")
        n = self.node(path)
        if n is None:
            raise Refused(f"no node {path}: find the path with com-tree")
        kids = children(n)
        if kids:
            raise Refused(f"{path} holds {len(kids)} nodes, not a value: give the full path to one value")
        ent = self.const.get("HAP_ENTERABLE")
        if ent is not None:
            try:
                enterable = n.AttributeValue(ent)
            except Exception:
                enterable = True
            if not enterable:
                raise Refused(f"{path} cannot be entered (Aspen marks it as calculated or read-only)")
        old, unit = _plain(_get(n, "Value")), _unit(n)
        try:
            n.Value = value
        except Exception as e:
            raise Refused(f"Aspen did not accept {value!r} for {path}: {e}") from None
        return {"path": path, "old": old, "new": _plain(_get(n, "Value")), "unit": unit}

    # runs ------------------------------------------------------------------
    def reinit(self) -> None:
        c = self.const.get("IAP_REINIT_SIMULATION")
        if c is None:
            raise Refused("this server's type library has no IAP_REINIT_SIMULATION, and Engine.Reinit() "
                          "without it opens a dialog. Run without --reinit, or reinitialize in the GUI.")
        try:
            self.app.Engine.Reinit(c)
        except Exception as e:
            raise explain(e) from None

    def _running(self, eng) -> bool:
        return bool(eng.IsRunning)                              # confirm live (L3)

    def run(self, timeout: float = 900, poll: float = 0.5, grace: float = 3.0) -> dict:
        eng = self.app.Engine
        t0 = self.clock()
        try:
            self._running(eng)
            can_poll = True
        except Exception:
            can_poll = False
        try:
            eng.Run2(1 if can_poll else 0)       # asynchronous when the wait below can poll it
        except Exception as e:
            return {"status": "failed", "seconds": round(self.clock() - t0, 1), "error": str(explain(e))}
        if not can_poll:
            return {"status": "completed", "seconds": round(self.clock() - t0, 1),
                    "note": "Engine.IsRunning not available: ran synchronously, the timeout was not enforced"}
        while not self._running(eng) and self.clock() - t0 < grace:    # the engine may flag the start late
            self.pump()
            self.sleep(poll)
        while self._running(eng):
            if self.clock() - t0 > timeout:
                try:
                    eng.Stop()
                except Exception:
                    pass
                t1 = self.clock()
                while self._running(eng) and self.clock() - t1 < 60:
                    self.pump()
                    self.sleep(poll)
                return {"status": "stopped on timeout", "seconds": round(self.clock() - t0, 1),
                        "timeout": timeout, "still_running": self._running(eng)}
            self.pump()
            self.sleep(poll)
        return {"status": "completed", "seconds": round(self.clock() - t0, 1)}

    def status_flags(self) -> Dict[str, object]:
        out = {}
        for f in STATUS_FLAGS:
            n = self.node(STATUS_PATH + "\\" + f)
            if n is not None:                   # missing: the feature is not used
                out[f] = _plain(_get(n, "Value"))
        return out

    # flowsheet edits ---------------------------------------------------------
    def _names(self, path: str) -> List[str]:
        n = self.node(path)
        return [str(_get(c, "Name", "")) for c in children(n)] if n is not None else []

    def add_block(self, spec: str) -> dict:
        name, typ = _split_type(spec, "--add-block", needs_type=True)
        if name.upper() in {x.upper() for x in self._names("\\Data\\Blocks")}:
            raise Refused(f"block {name} exists already")
        blocks = self.node("\\Data\\Blocks")
        try:
            blocks.Elements.Add(f"{name}!{typ}")
        except Exception as e:
            raise Refused(f"Aspen did not add block {name} of type {typ}: {e}") from None
        return {"op": "add-block", "block": name, "type": typ, "ports": self.ports(name)}

    def add_stream(self, spec: str) -> dict:
        name, typ = _split_type(spec, "--add-stream", needs_type=False)
        typ = typ or "MATERIAL"
        if typ not in ("MATERIAL", "HEAT", "WORK"):
            raise Refused(f"stream type {typ}: use MATERIAL, HEAT or WORK")
        if name.upper() in {x.upper() for x in self._names("\\Data\\Streams")}:
            raise Refused(f"stream {name} exists already")
        try:
            self.node("\\Data\\Streams").Elements.Add(f"{name}!{typ}")
        except Exception as e:
            raise Refused(f"Aspen did not add stream {name}: {e}") from None
        return {"op": "add-stream", "stream": name, "type": typ}

    def remove_block(self, name: str) -> dict:
        real = self._match(self._names("\\Data\\Blocks"), name, "block")
        try:
            self.node("\\Data\\Blocks").Elements.Remove(real)
        except Exception as e:
            raise Refused(f"Aspen did not remove block {real}: {e}") from None
        return {"op": "remove-block", "block": real}

    def ports(self, block: str) -> List[str]:
        return self._names(f"\\Data\\Blocks\\{block}\\Ports")

    def _match(self, names: List[str], want: str, what: str, where: str = "", hint: str = "") -> str:
        hit = next((n for n in names if n.upper() == want.strip().upper()), None)
        if hit is None:
            raise Refused(f"no {what} {want.strip()}{where}" + (f" (there are: {', '.join(names[:30])})" if names else "")
                          + hint)
        return hit

    def _port(self, spec: str, flag: str) -> Tuple[str, str, str]:
        m = re.match(r"^\s*([^:=]+?)\s*:\s*([^=]+?)\s*=\s*(\S+)\s*$", spec)
        if not m:
            raise Refused(f"{flag} needs BLOCK:PORT=STREAM, e.g. \"H1:F(IN)=S9\", got {spec!r}")
        block = self._match(self._names("\\Data\\Blocks"), m.group(1), "block")
        port = self._match(self.ports(block), m.group(2), "port", where=f" on {block}")
        stream = self._match(self._names("\\Data\\Streams"), m.group(3), "stream", hint="; add it with --add-stream")
        return block, port, stream

    def connect(self, spec: str) -> dict:
        block, port, stream = self._port(spec, "--connect")
        p = self.node(f"\\Data\\Blocks\\{block}\\Ports\\{port}")
        _try_calls(lambda: p.Add(stream), lambda: p.Elements.Add(stream))    # confirm live (L4)
        return {"op": "connect", "block": block, "port": port, "stream": stream}

    def disconnect(self, spec: str) -> dict:
        block, port, stream = self._port(spec, "--disconnect")
        p = self.node(f"\\Data\\Blocks\\{block}\\Ports\\{port}")
        if stream.upper() not in {x.upper() for x in self._names(f"\\Data\\Blocks\\{block}\\Ports\\{port}")}:
            raise Refused(f"stream {stream} is not connected to {block} port {port}")
        _try_calls(lambda: p.Remove(stream), lambda: p.Elements.Remove(stream))
        return {"op": "disconnect", "block": block, "port": port, "stream": stream}


def _split_type(spec: str, flag: str, needs_type: bool) -> Tuple[str, str]:
    """'H1!HEATER' (Aspen's notation) or 'H1=HEATER' (no '!' for an interactive Git Bash)."""
    m = re.match(r"^\s*([A-Za-z][A-Za-z0-9_\-]{0,7})\s*(?:[!=]\s*([A-Za-z][A-Za-z0-9\-]*))?\s*$", spec or "")
    if not m or (needs_type and not m.group(2)):
        raise Refused(f"{flag} needs NAME!TYPE, e.g. \"H1!HEATER\" (IDs: 8 characters at most), got {spec!r}")
    return m.group(1).upper(), (m.group(2) or "").upper()


def _walk(node, path: str, depth: int, max_children: int) -> dict:
    kids = children(node)
    d = {"name": str(_get(node, "Name", "") or path.rsplit("\\", 1)[-1]), "path": path}
    if not kids:
        d["value"], d["unit"] = _plain(_get(node, "Value")), _unit(node)
        return d
    d["count"] = len(kids)
    if depth <= 0:
        return d
    d["children"] = [_walk(k, path.rstrip("\\") + "\\" + str(_get(k, "Name", "?")), depth - 1, max_children)
                     for k in kids[:max_children]]
    if len(kids) > max_children:
        d["omitted"] = len(kids) - max_children
    return d


def start_server(visible: bool = False) -> Aspen:
    """Start a new Aspen Plus automation server (it takes a licence until close())."""
    pythoncom, client = _pywin32()
    pythoncom.CoInitialize()
    try:
        app = client.Dispatch(PROGID)
    except Exception as e:
        raise explain(e) from None
    for attr, val in (("SuppressDialogs", 1), ("Visible", 1 if visible else 0)):   # Suppressing Dialog Boxes
        try:
            setattr(app, attr, val)
        except Exception:
            pass
    return Aspen(app, constants=typelib_constants(app), pump=pythoncom.PumpWaitingMessages)


# ---------------------------------------------------------------------------
# processes, registry, files
# ---------------------------------------------------------------------------
def server_processes() -> Dict[int, str]:
    """Aspen Plus processes now running (Windows tasklist); {} elsewhere."""
    if sys.platform != "win32":
        return {}
    try:
        out = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True, text=True, errors="replace",
                             timeout=30).stdout
    except (OSError, subprocess.SubprocessError):
        return {}
    procs = {}
    for row in csv.reader(out.splitlines()):
        if len(row) >= 2 and row[0].lower() in SERVER_IMAGES:
            try:
                procs[int(row[1])] = row[0]
            except ValueError:
                pass
    return procs


class Session:
    """Start one server, always quit it, and report Aspen processes this command left behind."""

    def __init__(self, factory: Optional[Callable] = None, visible: bool = False, processes: Optional[Callable] = None,
                 wait_exit: float = 20, sleep: Callable = time.sleep):
        self.factory = factory or start_server              # looked up now: tests replace start_server
        self.processes = processes or server_processes
        self.visible = visible
        self.wait_exit, self.sleep = wait_exit, sleep
        self.warnings: List[str] = []
        self.aspen: Optional[Aspen] = None

    def __enter__(self) -> Aspen:
        self.before = self.processes()
        self.aspen = self.factory(visible=self.visible)
        return self.aspen

    def __exit__(self, *exc):
        if self.aspen is not None:
            self.aspen.close()
        left = {}
        deadline = time.monotonic() + self.wait_exit
        while True:
            now = self.processes()
            left = {pid: name for pid, name in now.items() if pid not in self.before}
            if not left or time.monotonic() > deadline:
                break
            self.sleep(1)
        for pid, name in sorted(left.items()):
            self.warnings.append(f"Aspen Plus did not exit: {name} (PID {pid}) started during this command. If it "
                                 "stays and is not a session you opened meanwhile, end it in Task Manager; "
                                 "other Aspen sessions were not touched.")
        return False


class _WinRegistry:
    def __init__(self):
        import winreg
        self.w = winreg

    def default(self, key: str) -> Optional[str]:
        try:
            with self.w.OpenKey(self.w.HKEY_CLASSES_ROOT, key) as k:
                return self.w.QueryValue(k, None) or None
        except OSError:
            return None

    def progids(self) -> List[str]:
        out, i = [], 0
        while True:
            try:
                name = self.w.EnumKey(self.w.HKEY_CLASSES_ROOT, i)
            except OSError:
                return out
            if name.lower().startswith("apwn.document"):
                out.append(name)
            i += 1


def registry_info(reg=None) -> dict:
    """Apwn.Document in HKEY_CLASSES_ROOT: CLSID, current version, every versioned ProgID."""
    if reg is None:
        if sys.platform != "win32":
            return {"checked": False}
        reg = _WinRegistry()
    info = {"checked": True, "clsid": reg.default(PROGID + "\\CLSID"), "current": reg.default(PROGID + "\\CurVer"),
            "versions": []}
    info["registered"] = bool(info["clsid"] or info["current"])
    for p in sorted(set(reg.progids())):
        m = re.match(r"^Apwn\.Document\.(\d+\.\d+)$", p, re.I)
        if m:
            info["versions"].append({"progid": p, "engine": m.group(1),
                                     "release": ENGINE_TO_RELEASE.get(m.group(1), "")})
    m = re.match(r"^Apwn\.Document\.(\d+\.\d+)$", info["current"] or "", re.I)
    info["current_release"] = ENGINE_TO_RELEASE.get(m.group(1), "") if m else ""
    return info


def frozen_reason(src: Path) -> str:
    """Why the model is a frozen gate: a FROZEN marker in its folder, or STATUS.md (in the folder
    or up to two levels above) listing its version folder or file name as frozen."""
    folder = src.parent
    try:
        for f in folder.iterdir():
            if f.is_file() and f.name.lower() in FROZEN_NAMES:
                return f"{f.name} marker in {folder.name}"
    except OSError:
        pass
    names = {folder.name.lower(), src.stem.lower()}
    for d in [folder] + list(folder.parents)[:2]:
        st = d / "STATUS.md"
        try:
            lines = st.read_text(encoding="utf-8", errors="replace").splitlines() if st.is_file() else []
        except OSError:
            lines = []
        for line in lines:
            if not re.search(r"\bfrozen\b", line, re.I):
                continue
            if line.lstrip().startswith("|"):
                cells = [c.strip().strip("`*").lower() for c in line.strip().strip("|").split("|")]
                if names & set(cells):
                    return f"STATUS.md row: {line.strip()[:120]}"
            else:
                for n in names:
                    name = r"(?<![\w.\-])" + re.escape(n) + r"(?![\w\-]|\.\w)"
                    if re.search(name + r"\s*(?:[:(\-]|is)?\s*frozen\b", line, re.I) or \
                            re.search(r"\bfrozen\s+(?:gate\s+|version\s+)?" + name, line, re.I):
                        return f"STATUS.md: {line.strip()[:120]}"
    return ""


def check_source(src, editing: bool) -> Path:
    p = Path(src).expanduser()
    if not p.is_file():
        raise Refused(f"no file {p}")
    if p.suffix.lower() not in MODEL_EXTS:
        raise Refused(f"automation opens .bkp or .apw files, not {p.suffix or 'this file'}")
    if editing:
        why = frozen_reason(p)
        if why:
            raise Refused(f"{p.parent.name} is a frozen gate ({why}). Gate files are never changed: Save As the "
                          "next version in Aspen and automate that copy.")
    return p.resolve()


def prepare_out(out, src: Path) -> Tuple[Path, bool]:
    o = Path(out).expanduser().resolve()
    srcdir = src.parent.resolve()
    if o == srcdir or srcdir in o.parents:
        raise Refused(f"--out must be outside the model's folder ({srcdir}); use a new sibling folder")
    if o.exists():
        if not o.is_dir():
            raise Refused(f"--out {o} is a file")
        if any(o.iterdir()):
            raise Refused(f"--out {o} is not empty: give a new folder (results are never mixed)")
        return o, False
    o.mkdir(parents=True)
    return o, True


def copy_model(src: Path, dest: Path) -> List[Path]:
    """The model and its embedded-objects file (.apmbd, same name)."""
    out = [Path(shutil.copy2(str(src), str(dest / src.name)))]
    for f in src.parent.iterdir():
        if f.is_file() and f.suffix.lower() == ".apmbd" and f.stem.lower() == src.stem.lower():
            out.append(Path(shutil.copy2(str(f), str(dest / f.name))))
    return out


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _value(text: str):
    t = text.strip()
    if len(t) >= 2 and t[0] == t[-1] and t[0] in "'\"":
        return t[1:-1]
    for conv in (int, float):
        try:
            return conv(t)
        except ValueError:
            pass
    return t


def parse_set(spec: str) -> Tuple[str, object]:
    if "=" not in spec:
        raise Refused(f"--set needs PATH=VALUE, e.g. \"\\Data\\Streams\\FEED\\Input\\TEMP\\MIXED=40\", got {spec!r}")
    path, val = spec.split("=", 1)
    if not path.strip().startswith("\\"):
        raise Refused(f"--set path must start with \\Data or another root node: {path!r}")
    return path.strip(), _value(val)


def verdict(flags: Dict[str, object]) -> str:
    vals = set(flags.values())
    if not flags:
        return "no status flags"
    if 1 in vals:
        return "errors"
    if 2 in vals:
        return "warnings"
    return "ok" if vals <= {0} else "unknown flags"


def _log(command: str, src: Path, out: Optional[Path]) -> dict:
    return {"tool": f"proc-sim-agent {__version__}", "command": command, "source": str(src),
            "out": str(out) if out else "", "started": _now(), "aspen": {}, "changes": [], "warnings": []}


def _finish(log: dict, session: Session, out: Optional[Path]) -> dict:
    log["ended"] = _now()
    log["warnings"] += session.warnings
    if out is not None:
        (out / "automation-log.json").write_text(json.dumps(log, indent=2, default=str), encoding="utf-8")
    return log


def _cleanup(created: bool, out: Path, written: List[Path]) -> None:
    for f in written:
        try:
            f.unlink()
        except OSError:
            pass
    if created:
        try:
            out.rmdir()
        except OSError:
            pass


# ---------------------------------------------------------------------------
# commands
# ---------------------------------------------------------------------------
def check(start: bool = False, factory: Optional[Callable] = None, reg=None,
          processes: Optional[Callable] = None) -> dict:
    res = {"windows": sys.platform == "win32", "python": sys.version.split()[0], "pywin32": None,
           "registry": registry_info(reg) if (reg is not None or sys.platform == "win32") else {"checked": False},
           "start": {"tried": False}}
    try:
        import importlib.util
        if importlib.util.find_spec("win32com") is not None:
            try:
                from importlib.metadata import version
                res["pywin32"] = version("pywin32")
            except Exception:
                res["pywin32"] = "installed"
    except (ImportError, ValueError):
        pass
    if start:
        res["start"] = {"tried": True}
        t0 = time.monotonic()
        s = Session(factory, processes=processes)
        try:
            with s as asp:
                res["start"].update(ok=True, version=asp.version(), members=asp.members())
        except AutomationError as e:
            res["start"].update(ok=False, error=str(e))
        res["start"]["seconds"] = round(time.monotonic() - t0, 1)
        res["start"]["warnings"] = s.warnings
    return res


def get(src, paths: List[str], factory: Optional[Callable] = None, processes: Optional[Callable] = None) -> dict:
    p = check_source(src, editing=False)
    tmp = Path(tempfile.mkdtemp(prefix="psa-com-"))
    s = Session(factory, processes=processes)
    try:
        copy = copy_model(p, tmp)[0]
        with s as asp:
            asp.open(copy)
            vals = [asp.value(x) for x in paths]
            ver = asp.version()
    finally:
        shutil.rmtree(str(tmp), ignore_errors=True)
    return {"source": str(p), "aspen": ver, "values": vals, "warnings": s.warnings}


def tree(src, node: str = "\\Data", depth: int = 2, max_children: int = 60, factory: Optional[Callable] = None,
         processes: Optional[Callable] = None) -> dict:
    p = check_source(src, editing=False)
    tmp = Path(tempfile.mkdtemp(prefix="psa-com-"))
    s = Session(factory, processes=processes)
    try:
        copy = copy_model(p, tmp)[0]
        with s as asp:
            asp.open(copy)
            t = asp.tree(node, depth=depth, max_children=max_children)
    finally:
        shutil.rmtree(str(tmp), ignore_errors=True)
    return {"source": str(p), "tree": t, "warnings": s.warnings}


def _outputs(asp: Aspen, out: Path, stem: str, run: Optional[dict]) -> Dict[str, str]:
    """Save the .bkp and export the input with graphics, the report and the run messages."""
    files, results = {}, run is not None and run["status"] == "completed"
    plan = [("BACKUP", ".bkp"), ("INPUT_WITH_GRAPHICS", ".inp")]
    if run is not None:
        plan += [("RUNMSG", ".cpm")] + ([("REPORT", ".rep")] if results else [])
    for kind, ext in plan:
        err = asp.export(kind, out / (stem + ext))
        files[ext] = "written" if not err else "not written: " + err
    if run is not None and not results:
        files[".rep"] = "not written: the run did not complete (a report needs results of this session)"
    return files


def run(src, out, sets: List[str] = (), reinit: bool = False, timeout: float = 900, visible: bool = False,
        factory: Optional[Callable] = None, processes: Optional[Callable] = None) -> dict:
    p = check_source(src, editing=True)
    changes = [parse_set(x) for x in sets]
    o, created = prepare_out(out, p)
    log = _log("com-run", p, o)
    written = copy_model(p, o)
    s = Session(factory, visible=visible, processes=processes)
    ok = False
    try:
        with s as asp:
            log["aspen"] = {"version": asp.version(), "progid": PROGID}
            asp.open(written[0])
            for path, val in changes:
                log["changes"].append(asp.set(path, val))
            if reinit:
                asp.reinit()
                log["reinit"] = True
            log["run"] = asp.run(timeout=timeout)
            log["run"]["flags"] = asp.status_flags()
            log["run"]["verdict"] = verdict(log["run"]["flags"])
            log["files"] = _outputs(asp, o, p.stem, log["run"])
            ok = True
    finally:
        if not ok:
            _cleanup(created, o, written)
    return _finish(log, s, o)


def _vary(specs: List[str]) -> List[Tuple[str, list]]:
    out = []
    for spec in specs:
        path, vals = parse_set(spec)
        out.append((path, [_value(v) for v in str(vals).split(",") if v.strip()]))
    n = {len(v) for _, v in out}
    if not out or len(n) != 1 or 0 in n:
        raise Refused("--vary needs PATH=v1,v2,... with the same number of values on every --vary")
    return out


def sweep(src, out, vary: List[str], read: List[str], reinit: bool = False, timeout: float = 900,
          csv_name: str = "sweep.csv", factory: Optional[Callable] = None,
          processes: Optional[Callable] = None) -> dict:
    p = check_source(src, editing=True)
    plan = _vary(vary)
    reads = [r.strip() for x in read for r in x.split(",") if r.strip()]
    if not reads:
        raise Refused("--read needs at least one result path")
    o, created = prepare_out(out, p)
    log = _log("com-sweep", p, o)
    written = copy_model(p, o)
    s = Session(factory, processes=processes)
    rows: List[dict] = []
    ok = False
    try:
        with s as asp:
            log["aspen"] = {"version": asp.version(), "progid": PROGID}
            asp.open(written[0])
            for i in range(len(plan[0][1])):
                row = {"point": i + 1, "set": [], "read": []}
                try:
                    for path, vals in plan:
                        row["set"].append(asp.set(path, vals[i]))
                except Refused:
                    if i == 0:
                        raise
                    row["status"] = "failed: value not accepted"
                    rows.append(row)
                    continue
                if reinit:
                    asp.reinit()
                r = asp.run(timeout=timeout)
                flags = asp.status_flags()
                row.update(status=r["status"], seconds=r["seconds"], flags=flags, verdict=verdict(flags))
                row["read"] = [asp.value(x) for x in reads]
                rows.append(row)
            ok = True
    finally:
        if not ok:
            _cleanup(created, o, written)
    log["points"] = rows
    csv_path = o / csv_name
    _write_sweep_csv(csv_path, plan, reads, rows)
    log["csv"] = str(csv_path)
    return _finish(log, s, o)


def _write_sweep_csv(path: Path, plan, reads, rows) -> None:
    def head(path_, unit):
        return f"{path_} [{unit}]" if unit else path_
    units_set = {}
    units_read = {}
    for r in rows:
        for c in r["set"]:
            units_set.setdefault(c["path"], c.get("unit", ""))
        for v in r["read"]:
            units_read.setdefault(v["path"], v.get("unit", ""))
    cols = (["point"] + [head(pth, units_set.get(pth, "")) for pth, _ in plan] + ["status", "verdict"]
            + list(STATUS_FLAGS) + [head(x, units_read.get(x, "")) for x in reads])
    with open(str(path), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for r in rows:
            setv = {c["path"]: c["new"] for c in r["set"]}
            readv = {v["path"]: v.get("value") for v in r["read"]}
            w.writerow([r["point"]] + [setv.get(pth, "") for pth, _ in plan] + [r.get("status", ""),
                       r.get("verdict", "")] + [r.get("flags", {}).get(f, "") for f in STATUS_FLAGS]
                       + [readv.get(x, "") for x in reads])


def edit(src, out, add_blocks: List[str] = (), add_streams: List[str] = (), connect: List[str] = (),
         disconnect: List[str] = (), remove_blocks: List[str] = (), sets: List[str] = (), run_after: bool = False,
         timeout: float = 900, factory: Optional[Callable] = None, processes: Optional[Callable] = None) -> dict:
    p = check_source(src, editing=True)
    changes = [parse_set(x) for x in sets]
    if not (add_blocks or add_streams or connect or disconnect or remove_blocks or changes):
        raise Refused("nothing to do: give --add-block, --add-stream, --connect, --disconnect, --remove-block "
                      "or --set")
    o, created = prepare_out(out, p)
    log = _log("com-edit", p, o)
    written = copy_model(p, o)
    s = Session(factory, processes=processes)
    ok = False
    try:
        with s as asp:
            log["aspen"] = {"version": asp.version(), "progid": PROGID}
            asp.open(written[0])
            ops = log.setdefault("edits", [])
            for b in remove_blocks:
                ops.append(asp.remove_block(b))
            for st in add_streams:
                ops.append(asp.add_stream(st))
            for b in add_blocks:
                ops.append(asp.add_block(b))
            for c in disconnect:
                ops.append(asp.disconnect(c))
            for c in connect:
                ops.append(asp.connect(c))
            for path, val in changes:
                log["changes"].append(asp.set(path, val))
            if run_after:
                log["run"] = asp.run(timeout=timeout)
                log["run"]["flags"] = asp.status_flags()
                log["run"]["verdict"] = verdict(log["run"]["flags"])
            log["files"] = _outputs(asp, o, p.stem, log.get("run"))
            ok = True
    finally:
        if not ok:
            _cleanup(created, o, written)
    return _finish(log, s, o)


# ---------------------------------------------------------------------------
# text output
# ---------------------------------------------------------------------------
def _short(path: str) -> str:
    """'\\Data\\Streams\\FEED\\Input\\TEMP\\MIXED' -> 'FEED TEMP\\MIXED' (object and variable)."""
    parts = [x for x in path.split("\\") if x]
    if len(parts) >= 5 and parts[0].upper() == "DATA":
        return parts[2] + " " + "\\".join(parts[-2:])
    return "\\".join(parts[-3:])


def render_check(res: dict) -> str:
    reg = res["registry"]
    L = ["# Aspen Plus automation check", f"- Windows: {'yes' if res['windows'] else 'no (automation needs Windows)'}",
         f"- Python {res['python']}; pywin32: {res['pywin32'] or 'not installed (python -m pip install pywin32)'}"]
    if not reg.get("checked"):
        L.append("- Registry: not checked (Windows only)")
    elif not reg.get("registered"):
        L.append("- Apwn.Document: not registered (Aspen Plus missing, or its automation server not registered)")
    else:
        cur = reg.get("current") or "?"
        L.append(f"- Apwn.Document: registered; current {cur}"
                 + (f" ({reg['current_release']})" if reg.get("current_release") else ""))
        if reg["versions"]:
            L.append("- Versions: " + ", ".join(f"{v['progid']}" + (f" ({v['release']})" if v["release"] else "")
                                               for v in reg["versions"]))
    st = res["start"]
    if not st.get("tried"):
        L.append("- Server start: not tried (pass --start: it takes a licence for a few seconds)")
    elif st.get("ok"):
        L.append(f"- Server start: ok in {st['seconds']} s" + (f", version {st['version']}" if st.get("version") else "")
                 + "; quit, licence released")
        m = st.get("members", {})
        if m:
            yn = lambda b: "yes" if b else "no"
            L.append(f"- Members: Version {yn(m.get('Version'))}; Engine.IsRunning {yn(m.get('Engine.IsRunning'))} "
                     "(without it runs are synchronous, no timeout)")
            L.append(f"- Type library: {m.get('constants', 0)} constants; IAP_REINIT_SIMULATION "
                     f"{m.get('IAP_REINIT_SIMULATION')}; HAP_ENTERABLE {m.get('HAP_ENTERABLE')}; export codes "
                     + ("as documented" if not m.get("export_codes_differ") else
                        "differ from the help: " + ", ".join(f"{k} {v[0]}->{v[1]}"
                                                            for k, v in m["export_codes_differ"].items())
                        + " (the type library's are used)"))
    else:
        L.append(f"- Server start: failed: {st.get('error')}")
    L += [f"- {w}" for w in st.get("warnings", [])]
    return "\n".join(L)


def render_values(res: dict) -> str:
    L = [f"# Values in {Path(res['source']).name} (a copy; Aspen {res.get('aspen') or '?'})", "",
         "| Path | Value | Unit |", "|---|---|---|"]
    for v in res["values"]:
        if not v["found"]:
            L.append(f"| {v['path']} | not found (check the path with com-tree) | |")
        elif v.get("folder"):
            L.append(f"| {v['path']} | a folder of {v['children']} nodes | |")
        else:
            L.append(f"| {v['path']} | {v['value']} | {v['unit']} |")
    L += [f"\n{w}" for w in res.get("warnings", [])]
    return "\n".join(L)


def render_tree(res: dict) -> str:
    L = [f"# Tree of {Path(res['source']).name} (a copy)", "", "```text"]

    def walk(d, ind):
        if "value" in d:
            unit = f" {d['unit']}" if d.get("unit") else ""
            L.append(f"{ind}{d['name']} = {d['value']}{unit}")
            return
        more = "" if d.get("children") else f" ({d['count']} nodes)"
        L.append(f"{ind}{d['name']}{more}")
        for c in d.get("children", []):
            walk(c, ind + "  ")
        if d.get("omitted"):
            L.append(f"{ind}  ... {d['omitted']} more")
    t = res["tree"]
    L.append(t["path"] + ("" if t.get("children") or "value" in t else f" ({t.get('count', 0)} nodes)"))
    for c in t.get("children", []):
        walk(c, "  ")
    if "value" in t:
        L.append(f"  = {t['value']} {t.get('unit', '')}".rstrip())
    L.append("```")
    L += [w for w in res.get("warnings", [])]
    return "\n".join(L)


def render_log(log: dict) -> str:
    L = [f"# {log['command']}: {Path(log['source']).name} -> {log['out']}",
         f"- Aspen Plus {log.get('aspen', {}).get('version') or '?'}; started {log['started']}, ended {log.get('ended', '?')}"]
    for c in log.get("changes", []):
        unit = f" {c['unit']}" if c.get("unit") else ""
        L.append(f"- set {c['path']}: {c['old']}{unit} -> {c['new']}{unit}")
    for e in log.get("edits", []):
        L.append("- " + " ".join(f"{k}={v}" for k, v in e.items() if k != "op") + f" ({e['op']})")
    r = log.get("run")
    if r:
        L.append(f"- Run: {r['status']} in {r['seconds']} s; status flags: {r.get('verdict', '?')}"
                 + (f" ({r['note']})" if r.get("note") else ""))
        for f, v in r.get("flags", {}).items():
            if v not in (0, None):
                L.append(f"  - {f} ({FLAG_MEANING.get(f, '')}): {FLAG_TEXT.get(v, v)}")
    for ext, state in (log.get("files") or {}).items():
        L.append(f"- {ext}: {state}")
    if log.get("points") is not None:
        L.append("")
        L.append("| Point | Set | Status | Read |")
        L.append("|---|---|---|---|")
        for pt in log["points"]:
            sets = "; ".join(f"{_short(c['path'])}={c['new']}" for c in pt["set"])
            reads = "; ".join(f"{v.get('value')} {v.get('unit', '')}".strip() for v in pt["read"])
            L.append(f"| {pt['point']} | {sets} | {pt.get('status', '')} ({pt.get('verdict', '')}) | {reads} |")
        L.append(f"\nCSV: {log.get('csv')}")
    L += [f"- WARNING: {w}" for w in log.get("warnings", [])]
    L.append(f"- Log: {Path(log['out']) / 'automation-log.json'}")
    return "\n".join(L)
