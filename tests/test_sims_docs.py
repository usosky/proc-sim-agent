"""Simulation-folder scan and the personal library index."""
import os
import time

from fwlib import docsdb, sims

import samples


def test_sim_scan_versions_temp_and_private_files(tmp_path):
    root = tmp_path / "sims" / "Plant"
    v1, v2 = root / "1.0 base", root / "1.1 new split"
    samples.write(v1 / "Plant.his", samples.HIS)
    (v1 / "Plant.bkp").write_text('MM "41.0" VERSION "41.0" DATETIME "x"\n', encoding="latin-1")
    samples.write(v2 / "Plant.his", samples.HIS_V2)
    (v2 / "Plant.bkp").write_text('MM "41.0" VERSION "41.0" DATETIME "x"\n', encoding="latin-1")
    samples.write(v2 / "plant.rep", samples.REP)
    (v2 / "notes.md").write_text("# split fraction 0.3 -> 0.4\n", encoding="utf-8")
    (v2 / "_0001abc.inm").write_text("x", encoding="latin-1")
    samples.write(v2 / "_0001abc.his", samples.HIS)
    (v2 / "$Plant$backup.bk$").write_text("x", encoding="latin-1")
    (v2 / "aspen.def").write_text("USERNAME=SECRETUSER\n", encoding="latin-1")
    # make the .bkp of 1.0 newer than its .his -> stale-results note
    old = time.time() - 3600
    os.utime(v1 / "Plant.his", (old, old))

    folders = sims.scan([str(tmp_path / "sims")])
    by_rel = {f["rel"]: f for f in folders}
    assert set(by_rel) == {"Plant/1.0 base", "Plant/1.1 new split"}
    new = by_rel["Plant/1.1 new split"]
    assert list(new["models"]) == ["plant"]                     # Plant.bkp + plant.rep grouped
    assert new["models"]["plant"]["status"] == "completed: 2 warnings"
    assert new["version_note"] == "split fraction 0.3 -> 0.4"
    assert new["temp_runs"][0]["runid"] == "DEMO"
    assert new["recovery"] == ["$Plant$backup.bk$"]
    md = sims.render_markdown(folders)
    assert "SECRETUSER" not in md
    assert any("may be stale" in n for n in by_rel["Plant/1.0 base"]["notes"])
    assert any("no .rep export" in n for n in by_rel["Plant/1.0 base"]["notes"])


def test_library_index_search_read_duplicates(tmp_path, mahome):
    lib = tmp_path / "library"
    lib.mkdir()
    (lib / "formic.md").write_text("# Formic acid purification\n\nThe purification column runs under vacuum "
                                   "to limit formic acid decomposition.\n", encoding="utf-8")
    (lib / "copy of formic.md").write_text((lib / "formic.md").read_text(encoding="utf-8"), encoding="utf-8")
    (lib / "nrtl.html").write_text("<html><body><h1>NRTL binaries</h1><p>Regress binary interaction parameters "
                                   "from VLE data.</p></body></html>", encoding="utf-8")
    res = docsdb.build([str(lib)], progress=lambda *a: None)
    assert res["complete"]
    statuses = sorted(d["status"] for d in docsdb.list_docs())
    assert statuses == ["duplicate", "ok", "ok"]
    hits = docsdb.search("purification vacuum")
    assert hits and "formic" in hits[0]["title"].lower()
    assert docsdb.search("binary interaction")[0]["title"].lower().startswith("nrtl")
    page = docsdb.read("nrtl")
    assert "Regress binary interaction parameters" in page["text"]


def test_library_keeps_offline_folders_and_reindexes_orphan_copies(tmp_path, mahome):
    lib, other = tmp_path / "lib", tmp_path / "usb"
    lib.mkdir()
    other.mkdir()
    (lib / "a.md").write_text("# Reflux ratio\n\nMinimum reflux by Underwood.\n", encoding="utf-8")
    (lib / "b.md").write_text("# Reflux ratio\n\nMinimum reflux by Underwood.\n", encoding="utf-8")  # copy
    (other / "c.md").write_text("# Pump curves\n\nNPSH available versus required.\n", encoding="utf-8")
    docsdb.build([str(lib), str(other)], progress=lambda *a: None)
    assert sorted(d["status"] for d in docsdb.list_docs()) == ["duplicate", "ok", "ok"]
    # the drive with c.md goes offline: its entries stay
    import shutil
    shutil.rmtree(other)
    res = docsdb.build([str(lib), str(other)], progress=lambda *a: None)
    assert res["removed"] == 0 and docsdb.search("NPSH")
    # the original of the duplicate is deleted: the copy is indexed instead
    (lib / "a.md").unlink()
    docsdb.build([str(lib), str(other)], progress=lambda *a: None)
    assert docsdb.search("Underwood") and docsdb.search("Underwood")[0]["path"].endswith("b.md")


def test_docx_entities_and_open_page_ranges(tmp_path, mahome):
    import zipfile
    lib = tmp_path / "lib"
    lib.mkdir()
    with zipfile.ZipFile(lib / "note.docx", "w") as z:
        z.writestr("word/document.xml", "<w:document><w:body><w:p><w:r><w:t>Heat &amp; mass balance "
                   "&lt;check&gt;</w:t></w:r></w:p></w:body></w:document>")
    docsdb.build([str(lib)], progress=lambda *a: None)
    page = docsdb.read("note", pages="1-")
    assert "Heat & mass balance <check>" in page["text"]
    assert docsdb._page_range("2-", 4) == [2, 3, 4] and docsdb._page_range("-2", 4) == [1, 2]
    assert docsdb._page_range("x,3", 4) == [3]


def test_document_titles_prefer_descriptive_file_names():
    from pathlib import Path
    stale = docsdb._good_title("CO2 Capture from Syngas for IGCC Using MEA",
                               Path("CO2 capture from flue gas using CESAR1 solvent.pdf"))
    assert stale == "CO2 capture from flue gas using CESAR1 solvent"
    assert docsdb._good_title("Accelerating the net-zero economy", Path("1-s2.0-S2542435124000035-main.pdf")) \
        == "Accelerating the net-zero economy"
    assert docsdb._good_title("", Path("notes.md")) == "notes"
    assert docsdb._good_title("Untitled", Path("Kim2024.pdf")) == "Kim2024"
    assert docsdb._good_title("x", Path("ENRTL-RK_Rate_Based_MEA_Model.pdf")) == "ENRTL-RK Rate Based MEA Model"
