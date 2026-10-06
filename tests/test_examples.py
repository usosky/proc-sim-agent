"""Example-library index (examples-index / -search / -show) on a synthetic model library."""
import os
import time

import pytest

from fwlib import bkp, examples, inp

import samples


@pytest.fixture
def library(tmp_path, mahome):
    root = samples.make_example_library(tmp_path / "Examples")
    res = examples.build([str(root)])
    assert res["complete"] and res["models"] == 3 and res["failed"] == 0
    return root


def _names(res):
    return [r["name"] for r in res]


def test_bkp_hidden_objects_hierarchy_and_privacy():
    d = bkp.parse_text(samples.BKP_DEMO, "demo.bkp")
    assert d["hidden"] == ["SENSITIVITY", "CONVERGENCE"]          # both buffer endings are cut out
    assert d["user_sequence"] is False                             # a hidden sequence would not count
    assert "SENSITIVITY S-OLD" not in d["sections"] and d["sensitivities"] == []
    assert d["blocks"]["HB.P1"]["hierarchy"] == "HB" and d["blocks"]["HB.P1"]["model"] == "Pump"
    assert d["property_methods"] == ["ELECNRTL", "ENRTL-RK"]      # global first, then the hierarchy's
    assert d["chemistry"]["C-1"] == {"equilibria": 1, "dissociations": 1, "salts": 0}
    assert d["ions"] == ["H3O+", "HCO3-", "NA+", "CL-"]
    md = bkp.render_markdown(d)
    assert "Hidden objects" in md and "JDOE" not in md and "PC-123" not in md
    assert bkp.parse_text(samples.BKP_COLUMN, "col.bkp")["user_sequence"] is True


def test_index_rows_features_and_guides(library):
    rows = {r["name"]: r for r in examples.search(limit=10)}
    assert set(rows) == {"brine_absorber", "methanol_column", "packed_column"}
    brine = rows["brine_absorber"]
    assert brine["folder"] == "Carbon Capture/Brine absorber" and brine["release"] == "V15"
    for f in ("electrolyte", "chemistry", "henry", "hierarchy", "calculator", "design-spec", "tear", "fortran",
              "user-fortran", "results"):
        assert f in brine["features"], f
    assert brine["guides"] == ["brine_absorber.pdf"]
    col = rows["methanol_column"]
    assert "user-sequence" in col["features"] and "results" not in col["features"]
    assert "user-fortran" in rows["packed_column"]["features"]       # .f inside the .apwz
    assert rows["packed_column"]["path"].endswith("packed_column.apwz")


def test_search_ranking_and_filters(library):
    assert _names(examples.search("brine bicarbonate"))[0] == "brine_absorber"
    assert set(_names(examples.search(block=["RADFRAC"]))) == {"methanol_column", "packed_column"}
    assert _names(examples.search(has=["hierarchy"])) == ["brine_absorber"]
    assert _names(examples.search(method=["ENRTL-RK"])) == ["brine_absorber"]   # hierarchy property method
    assert _names(examples.search(component=["NA+"])) == ["brine_absorber"]
    assert set(_names(examples.search(folder="Getting Started"))) == {"methanol_column", "packed_column"}
    assert _names(examples.search("column", block=["HEATER"], has=["user-sequence"], limit=5))
    assert examples.search("zzzunknownzzz") == []


def test_search_reads_the_pdf_guide(library):
    pytest.importorskip("pypdf")
    res = examples.search("hydraulics")                # only in the guide's first page
    assert _names(res) == ["brine_absorber"]


def test_show_section_and_chemistry_translation(library):
    d = examples.resolve("brine")
    md = examples.render_show(d)
    assert "Hidden objects (Hide/Reveal, not calculated): SENSITIVITY, CONVERGENCE" in md
    assert "| HB.P1 | Pump | LIQ -> PROD |" in md
    assert "Chemistry C-1: 1 equilibria, 1 dissociations, 0 salts" in md
    assert "JDOE" not in md
    sec = examples.section_text(d, "BLOCK FLASH2")
    assert "PARAM TEMP=25. PRES=0.1" in sec
    chem = examples.chemistry_as_inp(d)
    assert "STOIC 1 CO2 -1. / H2O -2. / HCO3- 1. / H3O+ 1." in chem
    assert "K-STOIC 1 A=231.465 B=-12092.1 C=-36.7816" in chem
    assert "DISS NACL NA+ 1. / CL- 1." in chem
    # the translation drops into an input file that passes the checker
    text = (samples.INP_FLASH.split("COMPONENTS")[0]
            + "COMPONENTS\n    H2O H2O /\n    CO2 CO2 /\n    NACL NACL /\n    H3O+ H3O+ /\n"
              "    HCO3- HCO3- /\n    NA+ NA+ /\n    CL- CL-\n"
            + "HENRY-COMPS GLOBAL CO2\n"
            + "\n".join(l for l in chem.splitlines() if not l.startswith(";")) + "\n"
            + "PROPERTIES ELECNRTL HENRY-COMPS=GLOBAL CHEMISTRY=C-1 TRUE-COMPS=YES\n")
    res = inp.check(text)
    assert res["counts"]["error"] == 0, res["findings"]
    assert not [f for f in res["findings"] if "balance" in f["message"]]
    # .apwz: sections are read from the .bkp inside
    assert "SEQUENCE" in examples.section_text(examples.resolve("packed"), "SEQUENCE")
    assert examples.chemistry_as_inp(examples.resolve("methanol")) == "No CHEMISTRY section in this model."


def test_index_is_incremental(library):
    again = examples.build([str(library)])
    assert again["added"] == again["updated"] == again["removed"] == 0
    f = library / "Getting Started" / "Distillation" / "methanol_column.bkp"
    samples.write(f, samples.BKP_COLUMN.replace("METHANOL", "ETHANOL"))
    later = time.time() + 5
    os.utime(f, (later, later))
    (library / "Getting Started" / "Packed" / "packed_column.apwz").unlink()
    res = examples.build([str(library)])
    assert res["updated"] == 1 and res["removed"] == 1 and res["models"] == 2
    assert _names(examples.search(component=["ETHANOL"])) == ["methanol_column"]


def test_index_resumes_after_time_limit(tmp_path, mahome):
    root = samples.make_example_library(tmp_path / "Examples")
    first = examples.build([str(root)], max_seconds=1e-9)
    assert first["complete"] is False and first["models"] < 3
    assert examples.status()["complete"] is False
    second = examples.build([str(root)])
    assert second["complete"] and second["models"] == 3
    assert examples.status() == {"exists": True, "models": 3, "complete": True,
                                 "updated": examples.status()["updated"]}


def test_folders_summary(library):
    rows = {r["folder"]: r for r in examples.folders()}
    assert rows["Carbon Capture/Brine absorber"]["models"] == 1
    assert "electrolyte" in rows["Carbon Capture/Brine absorber"]["features"]


def test_component_aliases_for_input_files(library):
    rows = examples.find_components("SODIUM-CHLORIDE")
    assert rows[0]["alias"] == "NACL" and rows[0]["ids"] == ["NACL"] and rows[0]["exact"]
    rows = examples.find_components("CH4O")                      # by formula
    assert rows[0]["databank_name"] == "METHANOL" and rows[0]["models"] == 2
    assert examples.find_components("ZZZ") == []
    md = examples.render_components(examples.find_components("water"), "water")
    assert "`WATER H2O` (also as H2O) | conv | WATER | 3 model(s)" in md     # same alias, different IDs
