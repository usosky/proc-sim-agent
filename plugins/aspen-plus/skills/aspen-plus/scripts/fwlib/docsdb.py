"""Full-text index of the user's own library (PDF, DOCX, TXT/MD, HTML): one row per page.

PDF text extraction uses the first available of: PyMuPDF (`pip install pymupdf`),
pypdf (`pip install pypdf`), or the `pdftotext` command (poppler). Scanned PDFs
without a text layer are listed as 'no-text' (OCR is out of scope).
The index stays on the user's machine; nothing is uploaded or shared.
"""
from __future__ import annotations

import html
import re
import shutil
import sqlite3
import subprocess
import time
import zipfile
from pathlib import Path
from typing import List, Optional, Tuple

from . import htmltext
from .common import data_home, fts5_available, now_iso, read_text_any, truncate

EXTS = {".pdf", ".docx", ".txt", ".md", ".html", ".htm"}


def db_path() -> Path:
    return data_home() / "index" / "library.sqlite"


def pdf_backend() -> str:
    try:
        import fitz  # noqa: F401  (PyMuPDF)
        return "pymupdf"
    except Exception:
        pass
    try:
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            import pypdf  # noqa: F401
        return "pypdf"
    except Exception:
        pass
    if shutil.which("pdftotext"):
        return "pdftotext"
    return ""


def connect(path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(str(path))
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    return con


def _init(con, use_fts5: bool):
    con.executescript("""
    CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
    CREATE TABLE IF NOT EXISTS docs(id INTEGER PRIMARY KEY, path TEXT UNIQUE, folder TEXT, title TEXT, kind TEXT,
        pages INTEGER, size INTEGER, mtime REAL, status TEXT, note TEXT, indexed_at TEXT, hash TEXT);
    CREATE TABLE IF NOT EXISTS pages(id INTEGER PRIMARY KEY, doc INTEGER, page INTEGER);
    CREATE INDEX IF NOT EXISTS pages_doc ON pages(doc);
    """)
    if use_fts5:
        con.execute("CREATE VIRTUAL TABLE IF NOT EXISTS pfts USING fts5(title, body, "
                    "tokenize='porter unicode61', prefix='2 3')")
    else:
        con.execute("CREATE TABLE IF NOT EXISTS pfts(rowid INTEGER PRIMARY KEY, title TEXT, body TEXT)")
    con.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('fts5',?)", (str(int(use_fts5)),))
    con.commit()


# ---------------------------------------------------------------------------
# extraction
# ---------------------------------------------------------------------------
def _pdf_pages(path: Path, backend: str) -> Tuple[List[str], str, str]:
    """Return (pages, title, status)."""
    if backend == "pymupdf":
        import fitz
        doc = fitz.open(str(path))
        if doc.needs_pass and not doc.authenticate(""):
            return [], "", "encrypted"
        title = (doc.metadata or {}).get("title") or ""
        pages = [p.get_text("text") for p in doc]
        doc.close()
        return pages, title, "ok"
    if backend == "pypdf":
        import pypdf
        r = pypdf.PdfReader(str(path))
        if r.is_encrypted:
            try:
                if not r.decrypt(""):
                    return [], "", "encrypted"
            except Exception:
                return [], "", "encrypted"
        title = ""
        try:
            title = (r.metadata.title or "") if r.metadata else ""
        except Exception:
            pass
        pages = []
        for p in r.pages:
            try:
                pages.append(p.extract_text() or "")
            except Exception:
                pages.append("")
        return pages, title, "ok"
    if backend == "pdftotext":
        res = subprocess.run(["pdftotext", "-layout", "-enc", "UTF-8", str(path), "-"], capture_output=True,
                             timeout=300)
        if res.returncode != 0:
            err = res.stderr.decode("utf-8", "replace").lower()
            return [], "", "encrypted" if "password" in err or "encrypt" in err else "error"
        return res.stdout.decode("utf-8", "replace").split("\f"), "", "ok"
    return [], "", "no-pdf-backend"


def _docx_text(path: Path) -> str:
    with zipfile.ZipFile(str(path)) as z:
        xml = z.read("word/document.xml").decode("utf-8", "replace")
    xml = re.sub(r"</w:p>", "\n", xml)
    xml = re.sub(r"<w:tab/>", "\t", xml)
    txt = html.unescape(re.sub(r"<[^>]+>", "", xml))
    return re.sub(r"\n{3,}", "\n\n", txt)


def _chunks(text: str, size: int = 3500) -> List[str]:
    """Split page-less documents into ~page-sized chunks on paragraph boundaries."""
    paras = text.split("\n\n")
    out, cur = [], ""
    for p in paras:
        if len(cur) + len(p) > size and cur:
            out.append(cur)
            cur = ""
        cur += p + "\n\n"
    if cur.strip():
        out.append(cur)
    return out or [""]


def extract(path: Path, backend: str):
    ext = path.suffix.lower()
    if ext == ".pdf":
        return _pdf_pages(path, backend)
    if ext == ".docx":
        return _chunks(_docx_text(path)), "", "ok"
    if ext in (".txt", ".md"):
        return _chunks(read_text_any(path)), "", "ok"
    if ext in (".html", ".htm"):
        d = htmltext.convert(read_text_any(path), links=False)
        return _chunks(d["text"]), d["title"], "ok"
    return [], "", "unsupported"


def _good_title(t: str, path: Path) -> str:
    t = (t or "").strip()
    if not t or len(t) < 4 or re.match(r"^(untitled|microsoft word|document\d*|title)\b", t, re.I) \
            or t.lower().endswith((".doc", ".docx", ".pdf", ".dvi", ".tex")):
        return path.stem
    return t


# ---------------------------------------------------------------------------
# build / search / read
# ---------------------------------------------------------------------------
def build(folders: List[str], max_seconds: float = 0, rebuild: bool = False, progress=print) -> dict:
    t0 = time.time()
    path = db_path()
    if rebuild:
        for p in (path, Path(str(path) + "-wal"), Path(str(path) + "-shm")):
            try:
                p.unlink()
            except FileNotFoundError:
                pass
    use_fts5 = fts5_available()
    con = connect(path)
    _init(con, use_fts5)
    backend = pdf_backend()
    files = []
    missing_roots = set()
    for f in folders:
        root = Path(f).expanduser().resolve()
        if root.is_file():
            files.append((root, root.parent))
        elif root.is_dir():
            files += [(p, root) for p in sorted(root.rglob("*")) if p.suffix.lower() in EXTS and p.is_file()
                      and not p.name.startswith("~$")]
        else:  # offline drive or moved folder: keep what was indexed from it
            missing_roots.add(str(root))
            progress(f"  folder not found, keeping its index entries: {root}")
    # a file that was being read when an earlier run was stopped (e.g. a huge PDF that outlasted the
    # caller's time limit) is recorded once instead of being retried forever
    stuck = (con.execute("SELECT value FROM meta WHERE key='in_progress'").fetchone() or [""])[0]
    seen = set()
    added = updated = skipped = 0
    out_of_time = False
    for p, root in files:
        sp = str(p)
        seen.add(sp)
        st = p.stat()
        row = con.execute("SELECT id,size,mtime,status,note FROM docs WHERE path=?", (sp,)).fetchone()
        orphan_dup = row is not None and row["status"] == "duplicate" and not _has_original(con, row["id"])
        if row and row["size"] == st.st_size and abs((row["mtime"] or 0) - st.st_mtime) < 1 and \
                not (row["status"] == "no-pdf-backend" and backend) and not orphan_dup:
            skipped += 1
            continue
        if max_seconds and time.time() - t0 > max_seconds:
            out_of_time = True
            break
        if row:
            _delete_doc(con, row["id"])
        if sp == stuck:
            con.execute("INSERT INTO docs(path,folder,title,kind,pages,size,mtime,status,note,indexed_at,hash) "
                        "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                        (sp, str(root), p.stem, p.suffix.lower().lstrip("."), 0, st.st_size, st.st_mtime,
                         "too-slow", "reading stopped in an earlier run; split or OCR-clean the file", now_iso(), ""))
            con.execute("DELETE FROM meta WHERE key='in_progress'")
            con.commit()
            progress(f"  too-slow          {truncate(p.name, 70)} (skipped)")
            continue
        digest = _quick_hash(p)
        dup = con.execute("SELECT id, path FROM docs WHERE hash=? AND path<>? AND status<>'duplicate'",
                          (digest, sp)).fetchone()
        if dup and Path(dup["path"]).exists():  # same file stored twice: list it, do not index it again
            con.execute("INSERT INTO docs(path,folder,title,kind,pages,size,mtime,status,note,indexed_at,hash) "
                        "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                        (sp, str(root), p.stem, p.suffix.lower().lstrip("."), 0, st.st_size, st.st_mtime,
                         "duplicate", f"same content as doc {dup['id']}", now_iso(), digest))
            con.commit()
            progress(f"  duplicate         {truncate(p.name, 70)} (= doc {dup['id']})")
            continue
        con.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('in_progress',?)", (sp,))
        con.commit()
        try:
            pages, title, status = extract(p, backend)
        except Exception as e:  # damaged file: record and move on
            pages, title, status = [], "", f"error: {type(e).__name__}"
        con.execute("DELETE FROM meta WHERE key='in_progress'")
        title = _good_title(title, p)
        nonempty = sum(1 for x in pages if x and x.strip())
        if status == "ok" and pages and nonempty == 0:
            status = "no-text"
        cur = con.execute("INSERT INTO docs(path,folder,title,kind,pages,size,mtime,status,note,indexed_at,hash) "
                          "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                          (sp, str(root), title, p.suffix.lower().lstrip("."), len(pages), st.st_size, st.st_mtime,
                           status, "" if status == "ok" else status, now_iso(), digest))
        did = cur.lastrowid
        if status == "ok":
            for i, txt in enumerate(pages, 1):
                if not txt or not txt.strip():
                    continue
                pc = con.execute("INSERT INTO pages(doc,page) VALUES(?,?)", (did, i))
                con.execute("INSERT INTO pfts(rowid,title,body) VALUES(?,?,?)", (pc.lastrowid, title, txt))
        con.commit()
        if row:
            updated += 1
        else:
            added += 1
        progress(f"  {status:9s} {len(pages):4d} p  {truncate(title, 70)}")
    removed = 0
    if not out_of_time:
        for r in con.execute("SELECT id,path,folder FROM docs").fetchall():
            if r["path"] not in seen and r["folder"] not in missing_roots:
                _delete_doc(con, r["id"])
                removed += 1
        con.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('complete','1')")
        con.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('folders',?)", ("|".join(folders),))
    else:
        con.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('complete','0')")
    con.commit()
    stats = {r["status"]: r["n"] for r in con.execute("SELECT status, COUNT(*) n FROM docs GROUP BY status")}
    con.close()
    return {"db": str(path), "pdf_backend": backend or "none", "added": added, "updated": updated,
            "unchanged": skipped, "removed": removed, "status_counts": stats, "complete": not out_of_time,
            "seconds": round(time.time() - t0, 1)}


def _has_original(con, doc_id) -> bool:
    """A 'duplicate' row still has its original indexed and on disk."""
    r = con.execute("SELECT hash FROM docs WHERE id=?", (doc_id,)).fetchone()
    if not r or not r["hash"]:
        return False
    o = con.execute("SELECT path FROM docs WHERE hash=? AND status<>'duplicate'", (r["hash"],)).fetchone()
    return bool(o) and Path(o["path"]).exists()


def _quick_hash(p: Path) -> str:
    import hashlib
    h = hashlib.sha1()
    try:
        size = p.stat().st_size
        with open(p, "rb") as fh:
            h.update(fh.read(1 << 20))
            if size > (2 << 20):
                fh.seek(size - (1 << 20))
                h.update(fh.read(1 << 20))
        h.update(str(size).encode())
    except OSError:
        return ""
    return h.hexdigest()


def _delete_doc(con, doc_id):
    ids = [r[0] for r in con.execute("SELECT id FROM pages WHERE doc=?", (doc_id,))]
    for i in range(0, len(ids), 500):
        chunk = ids[i:i + 500]
        q = ",".join("?" * len(chunk))
        con.execute(f"DELETE FROM pfts WHERE rowid IN ({q})", chunk)
    con.execute("DELETE FROM pages WHERE doc=?", (doc_id,))
    con.execute("DELETE FROM docs WHERE id=?", (doc_id,))


def search(query: str, limit: int = 8, raw: bool = False) -> List[dict]:
    from .helpdb import _terms  # same query handling as the help index
    path = db_path()
    if not path.exists():
        return []
    con = connect(path)
    try:
        fts5 = (con.execute("SELECT value FROM meta WHERE key='fts5'").fetchone() or ["1"])[0] == "1"
        if not fts5:
            words = [w.lower() for w in re.findall(r"[A-Za-z0-9]+", query)]
            rows = []
            for r in con.execute("SELECT p.id,p.page,d.id did,d.title,d.path,f.body FROM pfts f "
                                 "JOIN pages p ON p.id=f.rowid JOIN docs d ON d.id=p.doc"):
                b = (r["body"] or "").lower()
                hit = sum(1 for w in words if w in b)
                if hit:
                    rows.append((hit, sum(b.count(w) for w in words), r))
            rows.sort(key=lambda x: (-x[0], -x[1]))
            return [{"doc": r["did"], "title": r["title"], "page": r["page"], "path": r["path"],
                     "snippet": truncate(re.sub(r"\s+", " ", r["body"]), 220)} for _, _, r in rows[:limit]]
        terms = [query] if raw else _terms(query)
        if not terms:
            return []
        queries = [terms[0]] if raw else [" AND ".join(terms)] + ([" OR ".join(terms)] if len(terms) > 1 else [])
        out, seen = [], set()
        for q in queries:
            try:
                rows = con.execute(
                    "SELECT p.page, d.id did, d.title, d.path, snippet(pfts, 1, '[', ']', ' ... ', 20) snip, "
                    "bm25(pfts, 4.0, 1.0) score FROM pfts JOIN pages p ON p.id = pfts.rowid "
                    "JOIN docs d ON d.id = p.doc WHERE pfts MATCH ? ORDER BY score LIMIT ?", (q, limit * 3)).fetchall()
            except sqlite3.OperationalError:
                if raw:
                    raise
                continue
            for r in rows:
                key = (r["did"], r["page"])
                if key in seen:
                    continue
                seen.add(key)
                out.append({"doc": r["did"], "title": r["title"], "page": r["page"], "path": r["path"],
                            "snippet": re.sub(r"\s+", " ", r["snip"] or "")})
            if len(out) >= limit:
                break
        return out[:limit]
    finally:
        con.close()


def read(ref: str, pages: Optional[str] = None, max_chars: int = 12000) -> dict:
    path = db_path()
    con = connect(path)
    try:
        if ref.isdigit():
            d = con.execute("SELECT * FROM docs WHERE id=?", (int(ref),)).fetchone()
        else:
            d = con.execute("SELECT * FROM docs WHERE path=? OR path LIKE ? OR title LIKE ? ORDER BY length(path)",
                            (ref, "%" + ref, "%" + ref + "%")).fetchone()
        if not d:
            return {"error": f"no document matches {ref!r}"}
        doc = dict(d)
    finally:
        con.close()
    want = _page_range(pages, doc["pages"] or 1)
    p = Path(doc["path"])
    text_pages = []
    if p.exists():
        try:
            text_pages = _selected_pages(p, want)
        except Exception as e:
            return {"doc": doc, "pages": [], "text": f"(could not read {p.name}: {type(e).__name__}: {e})"}
    out_text, used = [], 0
    for i, t in text_pages:
        block = f"--- page {i} ---\n{t.strip()}"
        if used + len(block) > max_chars:
            out_text.append(f"--- (stopped at page {i}; use --pages to continue) ---")
            break
        out_text.append(block)
        used += len(block)
    return {"doc": doc, "pages": [i for i, _ in text_pages], "text": "\n\n".join(out_text)}


def _selected_pages(path: Path, want: List[int]) -> List[Tuple[int, str]]:
    """Extract only the requested pages (fast for large PDFs)."""
    if path.suffix.lower() != ".pdf":
        pages, _, _ = extract(path, "")
        return [(i, pages[i - 1]) for i in want if 1 <= i <= len(pages)]
    backend = pdf_backend()
    out = []
    if backend == "pymupdf":
        import fitz
        doc = fitz.open(str(path))
        if doc.needs_pass:
            doc.authenticate("")
        out = [(i, doc[i - 1].get_text("text")) for i in want if 1 <= i <= doc.page_count]
        doc.close()
    elif backend == "pypdf":
        import pypdf
        r = pypdf.PdfReader(str(path))
        if r.is_encrypted:
            r.decrypt("")
        out = [(i, r.pages[i - 1].extract_text() or "") for i in want if 1 <= i <= len(r.pages)]
    elif backend == "pdftotext":
        for i in want:
            res = subprocess.run(["pdftotext", "-layout", "-enc", "UTF-8", "-f", str(i), "-l", str(i), str(path), "-"],
                                 capture_output=True, timeout=120)
            if res.returncode == 0:
                out.append((i, res.stdout.decode("utf-8", "replace")))
    return out


def _page_range(spec: Optional[str], n: int) -> List[int]:
    if not spec:
        return list(range(1, min(n, 3) + 1))
    out = []
    for part in spec.split(","):
        part = part.strip()
        try:
            if "-" in part:  # '12-14', '12-' (to the end), '-3' (from the start)
                a, b = part.split("-", 1)
                lo = int(a) if a.strip() else 1
                hi = int(b) if b.strip() else max(n, lo)
                out += list(range(lo, hi + 1))
            elif part:
                out.append(int(part))
        except ValueError:
            continue
    return out


def list_docs() -> List[dict]:
    path = db_path()
    if not path.exists():
        return []
    con = connect(path)
    try:
        return [dict(r) for r in con.execute("SELECT id,title,kind,pages,status,path FROM docs ORDER BY title")]
    finally:
        con.close()
