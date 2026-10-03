"""MadCap WebHelp reading, indexing, search and topic reading on a synthetic help tree."""
from fwlib import helpdb, htmltext, jslit, madcap


def test_jslit_parses_madcap_literals():
    d = jslit.parse_define("define({numchunks:1,prefix:'a_Chunk',tree:{n:[{i:0,c:0}]},"
                           "'/x.htm':{i:[3],t:['It\\u0027s'],b:['']}});")
    assert d["numchunks"] == 1
    assert d["tree"]["n"][0]["i"] == 0
    assert d["/x.htm"]["t"] == ["It's"]


def test_find_root_product_version_books(help_root):
    assert madcap.find_help_root(help_root.parent) == help_root
    assert madcap.detect_product(help_root) == ("aspen-plus", "Aspen Plus")
    assert madcap.detect_version(help_root) == "V15"  # from "What's New in ... V15" in the TOC
    books = madcap.list_books(help_root)
    assert [b.name for b in books] == ["apwn", "demoblock", "democonv"]
    assert books[1].toc_path == "Using the Simulation Environment|Blocks"


def test_master_toc_marks_merged_books(help_root):
    books = madcap.list_books(help_root)
    toc = madcap.book_toc(books[0], help_root, subsystems=books[1:])
    children = toc[0]["children"]
    assert [c["book"] for c in children if c["book"]] == ["demoblock", "democonv"]


def test_topic_conversion_keeps_structure(help_root):
    rel = "Subsystems/demoblock/Content/html/reactor_setup.htm"
    doc = madcap.parse_topic(help_root, rel, links=True)
    assert doc["title"] == "DemoReactor Setup Sheet"
    assert doc["toc_path"] == "DemoReactor|DemoReactor Setup Form"
    assert "- Pressure (zero or negative means a pressure drop)" in doc["text"]
    assert "| Conversion | fraction of the key component converted |" in doc["text"]
    assert "[equation: X=G(X) (approx.)]" in doc["text"]


def test_links_resolve_relative_to_help_root():
    assert htmltext.resolve_href("Subsystems/b/Content/html/a.htm", "c.htm#x") == "Subsystems/b/Content/html/c.htm"


def test_build_search_read(help_root, mahome):
    db = helpdb.db_path_for("aspen-plus", "V15")
    res = helpdb.build(help_root, db, progress=lambda *a: None)
    assert res["complete"] and res["books_done"] == 3 and res["topics"] == 7
    hits = helpdb.search(db, "secant bracket flat")
    assert hits and hits[0]["title"] == "Secant Method"
    assert hits[0]["book"] == "democonv"
    assert "Convergence" in hits[0]["crumb"]
    # AND first, then OR: an unmatched extra word still finds the topic
    assert helpdb.search(db, "bracketing zebra")[0]["title"] == "Secant Method"
    # restricted to a book
    assert all(h["book"] == "demoblock" for h in helpdb.search(db, "conversion", book="demoblock"))
    # F1 alias and title lookups
    assert helpdb.resolve(db, "830001")[0]["title"] == "DemoReactor Setup Sheet"
    assert helpdb.resolve(db, "secant_method")[0]["title"] == "Secant Method"
    assert helpdb.resolve(db, "DemoReactor Results Sheet")[0]["rel"].endswith("reactor_results.htm")


def test_build_is_resumable(help_root, mahome):
    db = helpdb.db_path_for("aspen-plus", "V15")
    first = helpdb.build(help_root, db, only_books=["demoblock"], progress=lambda *a: None)
    assert not first["complete"]  # other books are still missing
    assert helpdb.status(db)["exists"]
    second = helpdb.build(help_root, db, progress=lambda *a: None)
    assert second["complete"]
    assert second["topics"] == 7
    assert second["new_topics"] == 7 - first["topics"]


def test_version_from_copyright_variable(help_root):
    (help_root / "Content" / "html" / "copyright.htm").write_text(
        '<html><body><b>Version: <span class="notranslate mc-variable Date.ExternalVersion variable">V16'
        "</span></b></body></html>", encoding="utf-8")
    assert madcap.detect_version(help_root) == "V16"  # wins over the TOC's "What's New ... V15"
