"""Windows hardening: console encoding, unusual and long paths, files held open by Aspen Plus,
sync-conflict copies and engine working files. Runs on Linux too; the locked-file test needs
Windows."""
import os
import subprocess
import sys

import pytest

from conftest import SCRIPTS
from fwlib import common

import samples

FW = SCRIPTS / "fw.py"
sys.path.insert(0, str(SCRIPTS))
import fw  # noqa: E402


def run(args, home, ok=(0,), encoding=None):
    env = dict(os.environ, PROC_SIM_AGENT_HOME=str(home))
    env.pop("PYTHONUTF8", None)
    if encoding:                       # what a PowerShell or cmd console would give Python
        env["PYTHONIOENCODING"] = encoding
    else:
        env.pop("PYTHONIOENCODING", None)
    p = subprocess.run([sys.executable, str(FW)] + [str(a) for a in args], capture_output=True, env=env,
                       timeout=300)
    assert p.returncode in ok, f"exit {p.returncode}\n{p.stdout!r}\n{p.stderr!r}"
    return p.stdout.decode("utf-8"), p.stderr.decode("utf-8")


@pytest.mark.parametrize("cmd", fw.commands())
def test_every_command_has_help(cmd, tmp_path):
    out, _ = run([cmd, "-h"], tmp_path / "home", encoding="cp1252")
    assert "usage:" in out


def test_unusual_folder_names_and_a_cp1252_console(tmp_path):
    """Spaces, !, +, accents and a character outside cp1252 (Delta) in the folder name, with the
    console encoding a Windows console gives Python: no crash, UTF-8 output."""
    d = tmp_path / "Simulación v1.0+ final! ΔT"
    samples.write(d / "DEMO.his", samples.HIS)
    samples.write(d / "demo.rep", samples.REP)
    samples.write(d / "DEMO.cpm", samples.CPM)
    home = tmp_path / "home"
    out, _ = run(["his", d], home, encoding="cp1252")
    assert "DEMO.his" in out
    run(["rep", d / "demo.rep"], home, encoding="cp1252")
    run(["cpm", d], home, encoding="cp1252")
    out, _ = run(["sim-scan", tmp_path], home, encoding="cp1252")
    assert "Simulación v1.0+ final! ΔT" in out


def test_long_path(tmp_path):
    """Deeper than Windows' 260-character limit (os_path adds the \\\\?\\ prefix there)."""
    deep = tmp_path
    while len(str(deep)) < 300:
        deep = deep / ("version-folder-" + "x" * 30)
    os.makedirs(common.os_path(deep), exist_ok=True)
    target = deep / "DEMO.his"
    with open(common.os_path(target), "wb") as fh:
        fh.write(samples.HIS.replace("\n", "\r\n").encode("cp1252"))
    out, _ = run(["his", target], tmp_path / "home")
    assert "DEMO.his" in out or "Run" in out


def test_os_path_prefix_on_windows(monkeypatch):
    import ntpath
    monkeypatch.setattr(common.os, "name", "nt")
    monkeypatch.setattr(common.os, "path", ntpath)
    long = "C:\\Sims\\" + "a" * 260 + "\\m.his"
    assert common.os_path(long).startswith("\\\\?\\C:\\Sims\\")
    assert common.os_path("\\\\server\\share\\" + "b" * 260).startswith("\\\\?\\UNC\\server\\share\\")
    assert common.os_path("C:\\short.his") == "C:\\short.his"
    assert common.os_path("\\\\?\\C:\\" + "c" * 300) == "\\\\?\\C:\\" + "c" * 300


def test_busy_file_is_retried_once_then_explained(tmp_path, monkeypatch):
    f = tmp_path / "DEMO.his"
    f.write_bytes(b"x" * 10)
    real_open = open
    calls = {"n": 0}

    def flaky(path, mode="r", *a, **k):
        calls["n"] += 1
        if calls["n"] <= fails:
            raise PermissionError(13, "The process cannot access the file because it is being used")
        return real_open(path, mode, *a, **k)

    monkeypatch.setattr("builtins.open", flaky)
    fails = 1
    assert common.read_bytes(f, wait=0) == b"x" * 10          # retried once
    calls["n"], fails = 0, 2
    with pytest.raises(common.FileBusy, match="cannot read it now"):
        common.read_bytes(f, wait=0)


def test_file_changing_while_read_is_reread(tmp_path, monkeypatch):
    f = tmp_path / "demo.rep"
    f.write_bytes(b"0123456789")
    real_stat = os.stat
    sizes = iter([5, 10])                                     # first read looks truncated

    def stat(path, *a, **k):
        st = real_stat(path, *a, **k)
        if str(path) == common.os_path(f):
            return os.stat_result((st.st_mode, st.st_ino, st.st_dev, st.st_nlink, st.st_uid, st.st_gid,
                                   next(sizes), st.st_atime, st.st_mtime, st.st_ctime))
        return st

    monkeypatch.setattr(common.os, "stat", stat)
    assert common.read_bytes(f, wait=0) == b"0123456789"


@pytest.mark.skipif(sys.platform != "win32", reason="share modes exist only on Windows")
def test_file_locked_by_another_program(tmp_path):
    """Open the file the way a program that denies sharing does; fw must say so clearly."""
    import ctypes
    from ctypes import wintypes
    f = tmp_path / "DEMO.his"
    samples.write(f, samples.HIS)
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateFileW.restype = wintypes.HANDLE
    h = k32.CreateFileW(str(f), 0x80000000, 0, None, 3, 0x80, None)    # GENERIC_READ, no sharing
    assert h != wintypes.HANDLE(-1).value
    try:
        _, err = run(["his", f], tmp_path / "home", ok=(2,))
        assert "cannot read it now" in err and "Aspen Plus may hold it" in err
    finally:
        k32.CloseHandle(h)


def test_sync_conflicts_and_engine_files_are_never_the_model(tmp_path):
    d = tmp_path / "proj" / "v1.02"
    samples.write(d / "DEMO.his", samples.HIS)
    samples.write(d / "DEMO (Edit conflict 2026-11-03 13-04).his", samples.HIS_V2)
    samples.write(d / "demo.sync-conflict-20261103-130400-ABCDEFG.rep", samples.REP)
    samples.write(d / "_4421cba.his", samples.HIS)
    home = tmp_path / "home"
    out, _ = run(["sim-scan", tmp_path / "proj"], home)
    assert "sync-conflict copies, not read" in out and "Edit conflict" in out
    assert "engine working files" in out
    table = out.split("## Notes")[0]
    assert "Edit conflict" not in table and "_4421cba" not in table      # not listed as models
    assert "(using DEMO.his)" in run(["his", d], home)[0]


def test_only_working_copies_in_a_folder(tmp_path):
    d = tmp_path / "v2"
    samples.write(d / "_4421cba.his", samples.HIS)
    _, err = run(["his", d], tmp_path / "home", ok=(2,))
    assert "No .his file" in err and "_4421cba.his" in err


@pytest.mark.parametrize("name, kind", [
    ("_4421cba.his", "engine"), ("$model$backup.bk$", "recovery"),
    ("model (Edit conflict 2026-11-03 13-04).bkp", "conflict"),
    ("model (John's conflicted copy 2026-01-01).rep", "conflict"),
    ("model.sync-conflict-20260101-120000-ABCDEFG.his", "conflict"),
    ("model (Conflict 1).bkp", "conflict"), ("model-DESKTOP-ABC1234.bkp", "conflict"),
    ("Conflict-free model.bkp", ""), ("model - Copy.bkp", ""), ("model (2).bkp", ""), ("model.bkp", ""),
])
def test_side_files(name, kind):
    assert common.side_file(name) == kind
