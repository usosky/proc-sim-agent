"""Stream checks (fw.py check): pasted result grids and .rep exports, balances, basis, metrics."""
import pytest

from fwlib import check

import samples


def test_pasted_table_balances_and_metrics():
    streams = check.from_text(samples.STREAM_TABLE)
    assert list(streams) == ["FEED", "GAS", "LIQ"]
    assert streams["FEED"]["TO"] == "FL1" and streams["GAS"]["FROM"] == "FL1"
    assert streams["LIQ"]["mole"]["CO2"] == pytest.approx(0.08)
    res = check.analyse(streams, elements=["C", "O"], metrics=[
        ("recovery", "flow(GAS, CO2) / elem(FEED, C)"),
        ("purity", "flow(GAS, CO2) / mole(GAS)"),
        ("loss", "massflow(LIQ, CO2) / mass(FEED)")])
    fl1 = res["blocks"]["FL1"]
    assert fl1["mass_rel"] == pytest.approx(0, abs=1e-5)
    assert fl1["elements"]["C"]["in"] == pytest.approx(0.1)
    m = {x["name"]: x["value"] for x in res["metrics"]}
    assert m["recovery"] == pytest.approx(0.2)
    assert m["purity"] == pytest.approx(0.02 / 0.06)
    assert m["loss"] == pytest.approx(3.5208 / 184.553)
    # all ions zero: apparent basis or inactive chemistry
    assert any("apparent basis" in f for f in res["flags"])
    md = check.render(res)
    assert "| FEED | (feed) -> FL1 |" in md and "recovery = 0.2" in md


def test_table_pasted_without_line_breaks():
    flat = samples.STREAM_TABLE.replace("\n", "\t")           # what a chat box does to a copied grid
    a = check.from_text(samples.STREAM_TABLE)
    b = check.from_text(flat)
    assert list(b) == list(a)
    for n in a:
        assert b[n]["mole"] == a[n]["mole"] and b[n]["mass_total"] == a[n]["mass_total"]


def test_imbalance_and_charge_are_flagged():
    table = samples.STREAM_TABLE.replace("\t1.6011\t", "\t1.7011\t")         # gas mass flow off by 0.1 kg/h
    table = table.replace("NA+\tkmol/hr\t0\t0\t0", "NA+\tkmol/hr\t0.01\t0\t0.01")
    res = check.analyse(check.from_text(table))
    flags = "\n".join(res["flags"])
    assert "Block FL1: mass out differs" in flags
    assert "Stream FEED is not electroneutral" in flags
    assert "apparent basis" not in flags


def test_metric_expressions_are_sandboxed():
    streams = check.from_text(samples.STREAM_TABLE)
    for bad in ("__import__('os').system('echo hi')", "open('x')", "flow(GAS, CO2).real"):
        with pytest.raises(Exception):
            check.evaluate(bad, streams, {})
    with pytest.raises(ValueError, match="no stream"):
        check.evaluate("flow(NOPE, CO2)", streams, {})
    with pytest.raises(ValueError, match="not in the table"):
        check.evaluate("flow(GAS, N2)", streams, {})
    assert check.evaluate("2 ** 3 - -1", streams, {}) == 9


def test_formulas_from_the_model_and_overrides(tmp_path):
    inp_file = samples.write(tmp_path / "m.inp", "COMPONENTS\n    MEOH CH4O /\n    WATER H2O /\n    X1 /\n"
                                                 "FORMULA X1 X1\n", crlf=False)
    aliases = check.aliases_from(inp_file)
    assert aliases == {"MEOH": "CH4O", "WATER": "H2O", "X1": "?"}
    fml, guessed = check.formulas(["MEOH", "WATER", "X1", "CO2"], aliases, {"X1": "C2H6"})
    assert fml["MEOH"] == {"C": 1, "H": 4, "O": 1} and fml["X1"] == {"C": 2, "H": 6}
    assert guessed == ["CO2"]                               # read from the ID itself
