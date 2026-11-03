"""Shared helpers: number formatting, file reading, names and the config file."""
import json

from fwlib import common


def test_fmt_num():
    assert common.fmt_num(None) == ""
    assert common.fmt_num("n/a") == "n/a"
    assert common.fmt_num(0) == "0"
    assert common.fmt_num(0.000123) == "1.230e-04"
    assert common.fmt_num(-0.0005) == "-5.000e-04"
    assert common.fmt_num(1.23456) == "1.235"
    assert common.fmt_num(211.364) == "211.36"           # values compared with papers keep decimals
    assert common.fmt_num(9731.6) == "9731.6"
    assert common.fmt_num(123456.7) == "123457"
    assert common.fmt_num(2.5e6) == "2.500e+06"
    assert common.fmt_num("42.5") == "42.5"


def test_truncate_and_safe_name():
    assert common.truncate("abc", 3) == "abc"
    assert common.truncate("abcdef", 5) == "ab..."
    assert common.truncate(None, 5) == ""
    assert common.safe_name("Aspen Plus V15.0") == "Aspen-Plus-V15.0"
    assert common.safe_name("C:\\Sims\\run 1") == "C-Sims-run-1"
    assert common.safe_name("///") == "x"


def test_human_size_and_natural_sort():
    assert common.human_size(512) == "512 B"
    assert common.human_size(2048) == "2.0 KB"
    assert common.human_size(5 * 1024 ** 3) == "5.0 GB"
    assert common.human_size(2 * 1024 ** 4) == "2048.0 GB"
    names = ["v1.10_final", "v1.9_final", "2.3.3", "2.3", "V2"]
    assert sorted(names, key=common.natural_key) == ["2.3", "2.3.3", "v1.9_final", "v1.10_final", "V2"]


def test_read_text_any(tmp_path):
    """Aspen writes ANSI (cp1252) files with CRLF line ends; notes may be UTF-8 with a BOM."""
    ansi = tmp_path / "run.rep"
    ansi.write_bytes("T = 25 \u00b0C\r\nP = 1 bar\r".encode("cp1252"))
    assert common.read_text_any(ansi) == "T = 25 \u00b0C\nP = 1 bar\n"
    bom = tmp_path / "notes.txt"
    bom.write_bytes("\ufeffNRTL \u03b1 = 0.3\n".encode("utf-8"))
    assert common.read_text_any(bom) == "NRTL \u03b1 = 0.3\n"


def test_config_defaults_round_trip_and_corruption(mahome):
    assert common.data_home() == mahome and (mahome / "index").is_dir()
    cfg = common.load_config()
    assert cfg["version"] == common.CONFIG_VERSION
    assert cfg["library"] == {"folders": []} and cfg["simulations"] == {"folders": []}
    cfg["library"]["folders"].append("D:/Papers")
    path = common.save_config(cfg)
    assert path == mahome / "config.json" and not path.with_suffix(".tmp").exists()   # atomic write
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["library"]["folders"] == ["D:/Papers"] and "updated" in saved
    assert common.load_config()["library"]["folders"] == ["D:/Papers"]
    path.write_text("{not json", encoding="utf-8")                  # a damaged file: start again
    assert common.load_config()["library"] == {"folders": []}


def test_expand_globs_and_mtime(tmp_path):
    for name in ("b.his", "a.his", "c.rep"):
        (tmp_path / name).write_text("x", encoding="utf-8")
    found = common.expand_globs([str(tmp_path / "*.his"), str(tmp_path / "*.rep")])
    assert [p.split("/")[-1].split("\\")[-1] for p in found] == ["a.his", "b.his", "c.rep"]
    assert common.mtime_str(tmp_path / "missing.his") == "?"
    assert len(common.mtime_str(tmp_path / "a.his")) == len("2026-01-01 12:00")


def test_fts5_probe_is_boolean():
    assert common.fts5_available() in (True, False)
