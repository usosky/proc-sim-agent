"""Search without SQLite FTS5, topic lookups, and PDFs in the library index."""
import io

import pytest

from fwlib import docsdb, helpdb

import samples

QUIET = dict(progress=lambda *a: None)


# ---------------------------------------------------------------- help index
@pytest.fixture
def help_db(help_root, mahome):
    db = helpdb.db_path_for("aspen-plus", "V15")
    assert helpdb.build(help_root, db, **QUIET)["complete"]
    return db


def test_help_search_without_fts5(help_root, mahome, monkeypatch):
    """Some Python builds ship SQLite without FTS5: the index then uses a plain table and
    a word-count ranking, and still finds topics."""
    monkeypatch.setattr(helpdb, "fts5_available", lambda: False)
    db = helpdb.db_path_for("aspen-plus", "V15")
    res = helpdb.build(help_root, db, **QUIET)
    assert res["complete"] and res["topics"] == 7
    assert helpdb.status(db)["meta"]["fts5"] == "0"
    hits = helpdb.search(db, "secant bracketing")
    assert hits[0]["title"] == "Secant Method" and hits[0]["match"] == "2/2 terms"
    assert "bracketing" in hits[0]["snippet"].lower()
    assert all(h["book"] == "demoblock" for h in helpdb.search(db, "conversion", book="demoblock"))
    assert helpdb.search(db, "the of and") == []                  # only stop words


def test_query_terms():
    assert helpdb._terms('"secant method" bracket the a 2') == ['"secant method"', '"bracket"', '"2"']
    assert helpdb._terms("heat-exchanger heat-exchanger") == ['"heat exchanger"']
    assert helpdb._terms("$OLVER02") == ['"OLVER02"']


def test_resolve_by_id_path_alias_and_title(help_db):
    by_path = helpdb.resolve(help_db, "Subsystems/demoblock/Content/html/reactor_setup.htm")
    assert by_path[0]["title"] == "DemoReactor Setup Sheet"
    assert helpdb.resolve(help_db, "html\\reactor_setup.htm")[0]["title"] == "DemoReactor Setup Sheet"
    assert helpdb.resolve(help_db, "910010")[0]["title"] == "Secant Method"     # F1 id
    topic = helpdb.resolve(help_db, "Tear Convergence Sheet")[0]
    assert helpdb.resolve(help_db, str(topic["id"]))[0]["title"] == "Tear Convergence Sheet"
    assert helpdb.resolve(help_db, "Results")[0]["title"] == "DemoReactor Results Sheet"   # partial title
    assert helpdb.resolve(help_db, "no such topic") == []


def test_aliases_links_and_books(help_db):
    rel = helpdb.resolve(help_db, "830001")[0]["rel"]
    assert "reactor_setup" in helpdb.topic_aliases(help_db, rel)
    targets = helpdb.link_targets(help_db, [rel, "Content/html/missing.htm"])
    assert targets[0]["title"] == "DemoReactor Setup Sheet" and targets[1]["id"] is None
    assert [b["name"] for b in helpdb.books(help_db)] == ["apwn", "demoblock", "democonv"]
    assert helpdb.topic_ids_by_rel(help_db)[rel] == helpdb.resolve(help_db, "830001")[0]["id"]


def test_status_of_a_missing_index(tmp_path):
    assert helpdb.status(tmp_path / "none.sqlite") == {"exists": False, "db": str(tmp_path / "none.sqlite")}


# ---------------------------------------------------------------- library: PDFs
@pytest.fixture
def pdf_library(tmp_path, mahome):
    pytest.importorskip("pypdf")
    lib = tmp_path / "papers"
    lib.mkdir()
    (lib / "doc12.pdf").write_bytes(samples.pdf_document(
        ["Introduction to reactive capture", "Formic acid leaves the column under vacuum distillation",
         "Conclusions and outlook"], title="Formic acid recovery"))
    return lib


def test_pdf_pages_title_search_and_read(pdf_library):
    res = docsdb.build([str(pdf_library)], **QUIET)
    assert res["complete"]
    doc = docsdb.list_docs()[0]
    assert doc["kind"] == "pdf" and doc["pages"] == 3 and doc["status"] == "ok"
    assert doc["title"] == "Formic acid recovery"            # metadata title for a short file name
    hit = docsdb.search("vacuum distillation")[0]
    assert hit["page"] == 2 and hit["title"] == "Formic acid recovery"
    page = docsdb.read("doc12.pdf", pages="2")                # path (or its end)
    assert page["pages"] == [2] and "under vacuum distillation" in page["text"]
    assert docsdb.read("acid recovery")["pages"] == [1, 2, 3]  # title fragment; first three pages
    assert docsdb.read(str(doc["id"]), pages="9")["pages"] == []   # doc id; no page 9
    assert "error" in docsdb.read("no such paper")


def test_encrypted_pdf_is_reported(tmp_path, mahome):
    pypdf = pytest.importorskip("pypdf")
    writer = pypdf.PdfWriter()
    for p in pypdf.PdfReader(io.BytesIO(samples.pdf_document(["confidential process data"]))).pages:
        writer.add_page(p)
    writer.encrypt("secret")
    lib = tmp_path / "locked"
    lib.mkdir()
    with open(lib / "locked.pdf", "wb") as fh:
        writer.write(fh)
    docsdb.build([str(lib)], **QUIET)
    assert docsdb.list_docs()[0]["status"] == "encrypted"
    assert docsdb.search("confidential") == []


def test_library_search_without_fts5(pdf_library, monkeypatch):
    monkeypatch.setattr(docsdb, "fts5_available", lambda: False)
    docsdb.build([str(pdf_library)], **QUIET)
    hits = docsdb.search("vacuum distillation")
    assert hits and hits[0]["page"] == 2


@pytest.mark.parametrize("spec, n, pages", [
    (None, 10, [1, 2, 3]), (None, 2, [1, 2]), ("2,4-5", 9, [2, 4, 5]),
    ("7-", 9, [7, 8, 9]), ("-2", 9, [1, 2]), ("x,3", 9, [3]),
])
def test_page_ranges(spec, n, pages):
    assert docsdb._page_range(spec, n) == pages
