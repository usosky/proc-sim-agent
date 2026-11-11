"""SQLite full-text index over a MadCap help system: build (resumable), search, read, TOC."""
from __future__ import annotations

import re
import sqlite3
import time
from pathlib import Path
from typing import List, Optional

from . import madcap
from .common import data_home, fts5_available, now_iso, safe_name, truncate

SCHEMA_VERSION = "1"

STOPWORDS = set("""a an and are as at be by can could do does for from how i if in into is it its me my
no not of on or our should so than that the their then there these this to use used using want was
we what when where which who why will with would you your""".split())


def db_path_for(product: str, version: str) -> Path:
    v = safe_name(version) if version and version != "unknown" else "unversioned"
    return data_home() / "index" / f"help-{safe_name(product)}-{v}.sqlite"


def connect(path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(str(path))
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=NORMAL")
    return con


def _init(con: sqlite3.Connection, use_fts5: bool):
    con.executescript("""
    CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
    CREATE TABLE IF NOT EXISTS books(name TEXT PRIMARY KEY, ord INTEGER, rel TEXT, toc_path TEXT,
        title TEXT, signature TEXT, status TEXT, n_topics INTEGER DEFAULT 0, built_at TEXT);
    CREATE TABLE IF NOT EXISTS topics(id INTEGER PRIMARY KEY, book TEXT, rel TEXT UNIQUE, title TEXT,
        crumb TEXT, abstract TEXT, n_chars INTEGER, n_eq INTEGER);
    CREATE INDEX IF NOT EXISTS topics_book ON topics(book);
    CREATE TABLE IF NOT EXISTS links(src INTEGER, dst TEXT);
    CREATE INDEX IF NOT EXISTS links_src ON links(src);
    CREATE TABLE IF NOT EXISTS aliases(name TEXT, rel TEXT, rid TEXT, book TEXT);
    CREATE INDEX IF NOT EXISTS aliases_name ON aliases(name COLLATE NOCASE);
    """)
    if use_fts5:
        con.execute("CREATE VIRTUAL TABLE IF NOT EXISTS fts USING fts5(title, crumb, body, "
                    "tokenize='porter unicode61', prefix='2 3')")
    else:
        con.execute("CREATE TABLE IF NOT EXISTS fts(rowid INTEGER PRIMARY KEY, title TEXT, crumb TEXT, body TEXT)")
    con.commit()


def _meta(con, key, default=None):
    r = con.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return r[0] if r else default


def _set_meta(con, **kv):
    con.executemany("INSERT OR REPLACE INTO meta(key,value) VALUES(?,?)", [(k, str(v)) for k, v in kv.items()])


# ---------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------
def build(help_root: Path, db_path: Path, max_seconds: float = 0, rebuild: bool = False,
          only_books: Optional[List[str]] = None, progress=print) -> dict:
    """Index the help system. Returns a status dict; status['complete'] is False if the time budget ran out.

    Re-running continues where it stopped: finished books are skipped (unless their
    signature changed), half-finished books continue topic by topic.
    """
    t0 = time.time()
    help_root = Path(help_root)
    product, title = madcap.detect_product(help_root)
    version = madcap.detect_version(help_root)
    if rebuild:
        for p in (db_path, Path(str(db_path) + "-wal"), Path(str(db_path) + "-shm")):
            try:
                p.unlink()
            except FileNotFoundError:
                pass
    use_fts5 = fts5_available()
    con = connect(db_path)
    _init(con, use_fts5)
    stored_root = _meta(con, "help_root")
    if stored_root and Path(stored_root) != help_root:
        progress(f"note: index was built from {stored_root}; now indexing {help_root}")
    _set_meta(con, schema=SCHEMA_VERSION, product=product, product_title=title, version=version,
              help_root=str(help_root), fts5=int(use_fts5), started=_meta(con, "started", now_iso()))
    con.commit()

    all_books = madcap.list_books(help_root)
    books = all_books
    if only_books:
        wanted = {b.lower() for b in only_books}
        books = [b for b in books if b.name.lower() in wanted]
    total_books = len(books)
    done_books = 0
    new_topics = 0
    out_of_time = False

    for b in books:
        sig = madcap.book_signature(b)
        row = con.execute("SELECT signature,status FROM books WHERE name=?", (b.name,)).fetchone()
        if row and row["status"] == "done" and row["signature"] == sig:
            done_books += 1
            continue
        if row and row["signature"] != sig:
            _delete_book(con, b.name)
            row = None
        if max_seconds and time.time() - t0 > max_seconds:
            out_of_time = True
            break
        bt = time.time()
        btitle = madcap.book_title(b, help_root)
        con.execute("INSERT OR REPLACE INTO books(name,ord,rel,toc_path,title,signature,status,n_topics,built_at) "
                    "VALUES(?,?,?,?,?,?,?,COALESCE((SELECT n_topics FROM books WHERE name=?),0),?)",
                    (b.name, b.order, b.rel, b.toc_path, btitle, sig, "partial", b.name, now_iso()))
        # aliases (cheap; rewrite every time the book is touched)
        con.execute("DELETE FROM aliases WHERE book=?", (b.name,))
        con.executemany("INSERT INTO aliases(name,rel,rid,book) VALUES(?,?,?,?)",
                        [(n, r, i, b.name) for n, r, i in madcap.book_aliases(b, help_root)])
        catalog = madcap.book_search_catalog(b, help_root)
        files = madcap.book_topic_files(b, help_root)
        have = {r[0] for r in con.execute("SELECT rel FROM topics WHERE book=?", (b.name,))}
        crumb_prefix = [p for p in b.toc_path.split("|") if p]
        pending = [f for f in files if f not in have]
        batch = 0
        for rel in pending:
            if max_seconds and time.time() - t0 > max_seconds:
                out_of_time = True
                break
            try:
                doc = madcap.parse_topic(help_root, rel, links=False, equations=True)
            except Exception as e:  # unreadable topic: index the catalogue abstract instead
                doc = {"title": "", "toc_path": "", "text": "", "links": [], "equations": [], "error": str(e)}
            cat = catalog.get(rel, {})
            ttl = (doc.get("title") or cat.get("title") or Path(rel).stem).strip()
            crumb_parts = crumb_prefix + [p for p in (doc.get("toc_path") or "").split("|") if p]
            crumb = " > ".join(crumb_parts)
            body = doc.get("text") or cat.get("abstract", "")
            cur = con.execute("INSERT INTO topics(book,rel,title,crumb,abstract,n_chars,n_eq) VALUES(?,?,?,?,?,?,?)",
                              (b.name, rel, ttl, crumb, truncate(cat.get("abstract", ""), 400), len(body),
                               len(doc.get("equations") or [])))
            tid = cur.lastrowid
            con.execute("INSERT INTO fts(rowid,title,crumb,body) VALUES(?,?,?,?)", (tid, ttl, crumb, body))
            if doc.get("links"):
                con.executemany("INSERT INTO links(src,dst) VALUES(?,?)", [(tid, d) for d in doc["links"]])
            new_topics += 1
            batch += 1
            if batch >= 200:
                con.commit()
                batch = 0
        n = con.execute("SELECT COUNT(*) FROM topics WHERE book=?", (b.name,)).fetchone()[0]
        status = "partial" if out_of_time else "done"
        con.execute("UPDATE books SET status=?, n_topics=?, built_at=? WHERE name=?", (status, n, now_iso(), b.name))
        con.commit()
        if status == "done":
            done_books += 1
            progress(f"  [{done_books}/{total_books}] {b.name}: {n} topics ({time.time() - bt:.1f} s)")
        else:
            progress(f"  [{done_books}/{total_books}] {b.name}: {n}/{len(files)} topics so far (time budget reached)")
        if out_of_time:
            break

    complete = (done_books == total_books) and not out_of_time
    if complete and only_books:  # a subset run completes the index only if every other book is done too
        names = {b.name for b in all_books}
        done_all = {r[0] for r in con.execute("SELECT name FROM books WHERE status='done'")}
        complete = names <= done_all
    n_topics = con.execute("SELECT COUNT(*) FROM topics").fetchone()[0]
    if complete:
        if use_fts5:
            con.execute("INSERT INTO fts(fts) VALUES('optimize')")
        _set_meta(con, complete=1, finished=now_iso(), n_topics=n_topics, n_books=total_books)
    else:
        _set_meta(con, complete=0, n_topics=n_topics)
    con.commit()
    con.close()
    return {"product": product, "title": title, "version": version, "db": str(db_path),
            "books_done": done_books, "books_total": total_books, "topics": n_topics,
            "new_topics": new_topics, "complete": complete, "seconds": round(time.time() - t0, 1)}


def _delete_book(con, name):
    ids = [r[0] for r in con.execute("SELECT id FROM topics WHERE book=?", (name,))]
    for i in range(0, len(ids), 500):
        chunk = ids[i:i + 500]
        q = ",".join("?" * len(chunk))
        con.execute(f"DELETE FROM fts WHERE rowid IN ({q})", chunk)
        con.execute(f"DELETE FROM links WHERE src IN ({q})", chunk)
    con.execute("DELETE FROM topics WHERE book=?", (name,))
    con.execute("DELETE FROM aliases WHERE book=?", (name,))
    con.execute("DELETE FROM books WHERE name=?", (name,))


def status(db_path: Path) -> dict:
    if not db_path.exists():
        return {"exists": False, "db": str(db_path)}
    con = connect(db_path)
    try:
        meta = {r["key"]: r["value"] for r in con.execute("SELECT key,value FROM meta")}
        nb = con.execute("SELECT COUNT(*), SUM(status='done') FROM books").fetchone()
        nt = con.execute("SELECT COUNT(*) FROM topics").fetchone()[0]
    finally:
        con.close()
    return {"exists": True, "db": str(db_path), "meta": meta, "books_seen": nb[0], "books_done": nb[1] or 0,
            "topics": nt, "complete": meta.get("complete") == "1"}


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------
def _terms(query: str):
    """Split a natural-language query into FTS5 terms; hyphen/dot words become phrases."""
    phrases = re.findall(r'"([^"]+)"', query)
    rest = re.sub(r'"[^"]+"', " ", query)
    terms = []
    for p in phrases:
        words = re.findall(r"[A-Za-z0-9]+", p)
        if words:
            terms.append('"' + " ".join(words) + '"')
    for chunk in rest.split():
        words = re.findall(r"[A-Za-z0-9]+", chunk)
        if not words:
            continue
        if len(words) == 1:
            w = words[0]
            if w.lower() in STOPWORDS or (len(w) == 1 and not w.isdigit()):
                continue
            terms.append('"' + w + '"')
        else:
            terms.append('"' + " ".join(words) + '"')
    return list(dict.fromkeys(terms))


def search(db_path: Path, query: str, limit: int = 8, book: Optional[str] = None, raw: bool = False) -> List[dict]:
    con = connect(db_path)
    try:
        use_fts5 = _meta(con, "fts5", "1") == "1"
        if not use_fts5:
            return _search_plain(con, query, limit, book)
        results, seen = [], set()
        if raw:
            queries = [query]
        else:
            terms = _terms(query)
            if not terms:
                return []
            queries = [" AND ".join(terms)]
            if len(terms) > 1:
                queries.append(" OR ".join(terms))
        for q in queries:
            sql = ("SELECT t.id, t.book, t.rel, t.title, t.crumb, "
                   "snippet(fts, 2, '[', ']', ' ... ', 18) AS snip, bm25(fts, 8.0, 3.0, 1.0) AS score "
                   "FROM fts JOIN topics t ON t.id = fts.rowid WHERE fts MATCH ?")
            args = [q]
            if book:
                sql += " AND t.book = ? COLLATE NOCASE"
                args.append(book)
            sql += " ORDER BY score LIMIT ?"
            args.append(limit)
            try:
                rows = con.execute(sql, args).fetchall()
            except sqlite3.OperationalError as e:
                if raw:
                    raise
                continue
            for r in rows:
                if r["id"] in seen:
                    continue
                seen.add(r["id"])
                results.append({"id": r["id"], "title": r["title"], "book": r["book"], "crumb": r["crumb"],
                                "rel": r["rel"], "snippet": re.sub(r"\s+", " ", r["snip"] or ""),
                                "match": "all terms" if q is queries[0] else "some terms"})
            if len(results) >= limit:
                break
        return results[:limit]
    finally:
        con.close()


def _search_plain(con, query, limit, book):
    words = [w.lower() for w in re.findall(r"[A-Za-z0-9]+", query) if w.lower() not in STOPWORDS]
    if not words:
        return []
    sql = "SELECT t.id,t.book,t.rel,t.title,t.crumb,f.body FROM fts f JOIN topics t ON t.id=f.rowid"
    args = []
    if book:
        sql += " WHERE t.book=? COLLATE NOCASE"
        args.append(book)
    scored = []
    for r in con.execute(sql, args):
        title, body = (r["title"] or "").lower(), (r["body"] or "").lower()
        s = sum(8 * title.count(w) + body.count(w) for w in words)
        hit = sum(1 for w in words if w in title or w in body)
        if hit:
            scored.append((hit, s, r))
    scored.sort(key=lambda x: (-x[0], -x[1]))
    out = []
    for hit, s, r in scored[:limit]:
        body = r["body"] or ""
        k = body.lower().find(words[0])
        snip = body[max(0, k - 80): k + 160] if k >= 0 else body[:200]
        out.append({"id": r["id"], "title": r["title"], "book": r["book"], "crumb": r["crumb"], "rel": r["rel"],
                    "snippet": re.sub(r"\s+", " ", snip), "match": f"{hit}/{len(words)} terms"})
    return out


# ---------------------------------------------------------------------------
# read / resolve
# ---------------------------------------------------------------------------
def resolve(db_path: Path, ref: str) -> List[dict]:
    """Find topics by id, relative path, F1 alias, or title. Returns candidates (best first)."""
    con = connect(db_path)
    try:
        ref = ref.strip()
        rows = []
        if ref.isdigit():
            by_id = lambda: con.execute("SELECT * FROM topics WHERE id=?", (int(ref),)).fetchall()
            by_f1 = lambda: con.execute("SELECT t.* FROM aliases a JOIN topics t ON t.rel=a.rel WHERE a.rid=?",
                                        (ref,)).fetchall()
            # context-help (F1) ids are long numbers; topic ids are row numbers
            rows = (by_f1() or by_id()) if len(ref) >= 6 else (by_id() or by_f1())
        if not rows and ("/" in ref or "\\" in ref or ref.lower().endswith((".htm", ".html"))):
            r = ref.replace("\\", "/")
            rows = con.execute("SELECT * FROM topics WHERE rel=? OR rel LIKE ?", (r, "%" + r)).fetchall()
        if not rows:
            rows = con.execute("SELECT t.* FROM aliases a JOIN topics t ON t.rel=a.rel WHERE a.name=? COLLATE NOCASE",
                               (ref,)).fetchall()
        if not rows:
            rows = con.execute("SELECT * FROM topics WHERE title=? COLLATE NOCASE ORDER BY length(crumb)",
                               (ref,)).fetchall()
        if not rows:
            rows = con.execute("SELECT * FROM topics WHERE title LIKE ? ORDER BY length(title) LIMIT 15",
                               ("%" + ref + "%",)).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


def topic_aliases(db_path: Path, rel: str) -> List[str]:
    con = connect(db_path)
    try:
        return [r[0] for r in con.execute("SELECT name FROM aliases WHERE rel=?", (rel,))]
    finally:
        con.close()


def link_targets(db_path: Path, rels: List[str]) -> List[dict]:
    con = connect(db_path)
    try:
        out = []
        for rel in rels:
            r = con.execute("SELECT id,title,book FROM topics WHERE rel=?", (rel,)).fetchone()
            out.append({"rel": rel, "id": r["id"] if r else None, "title": r["title"] if r else "",
                        "book": r["book"] if r else ""})
        return out
    finally:
        con.close()


def books(db_path: Path) -> List[dict]:
    con = connect(db_path)
    try:
        return [dict(r) for r in con.execute("SELECT * FROM books ORDER BY ord")]
    finally:
        con.close()


def topic_ids_by_rel(db_path: Path) -> dict:
    con = connect(db_path)
    try:
        return {r[0]: r[1] for r in con.execute("SELECT rel,id FROM topics")}
    finally:
        con.close()
