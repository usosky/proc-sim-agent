"""Index of a model library on the user's computer: the Aspen Plus example library, or any folder
of .bkp / .apwz models.

One row per model (a .bkp, or the .bkp inside an .apwz): topic folder, description, components,
property method and electrolyte setup, block types, flowsheet tools (calculators, design specs,
sensitivity, optimization, tears, hierarchy), Fortran, and the files next to it (PDF guide, Fortran
subroutines, Excel, custom-model files). Search ranks with SQLite FTS5 and can filter on block type,
property method, component or feature.

The example library is licensed AspenTech content: the index stays on the user's computer and
nothing from it is copied into answers beyond names, paths and short structural facts.
"""
from __future__ import annotations

import json
import re
import sqlite3
import time
import zipfile
from collections import Counter, OrderedDict
from pathlib import Path
from typing import Dict, List, Optional

from . import bkp, docsdb
from .common import data_home, fts5_available, now_iso, read_text_any, truncate
from .helpdb import _terms

MODEL_EXTS = {".bkp", ".apwz"}
COMPANION = {
    ".pdf": "guide", ".f": "fortran", ".for": "fortran", ".xlsx": "excel", ".xlsm": "excel", ".xls": "excel",
    ".acmf": "acm", ".atmlz": "acm", ".apm": "custom", ".aprbkp": "properties", ".appdf": "properties",
    ".txt": "notes", ".dll": "binary", ".lib": "binary", ".opt": "binary", ".dlopt": "binary", ".cst": "data",
    ".rep": "report", ".his": "history",
}
FEATURE_WORDS = ["calculator", "design-spec", "sensitivity", "optimization", "tear", "convergence", "hierarchy",
                 "electrolyte", "chemistry", "henry", "solids", "reactions", "fortran", "user-fortran", "excel",
                 "acm", "properties-only", "results", "user-sequence"]


def db_path() -> Path:
    return data_home() / "index" / "examples.sqlite"


def connect(path: Path = None) -> sqlite3.Connection:
    con = sqlite3.connect(str(path or db_path()))
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    return con


def _init(con, use_fts5: bool):
    con.executescript("""
    CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
    CREATE TABLE IF NOT EXISTS models(id INTEGER PRIMARY KEY, root TEXT, rel TEXT UNIQUE, folder TEXT, name TEXT,
        kind TEXT, release TEXT, run_class TEXT, description TEXT, methods TEXT, components TEXT, ions TEXT,
        block_types TEXT, n_blocks INTEGER, features TEXT, files TEXT, guides TEXT, size INTEGER, mtime REAL,
        status TEXT, summary TEXT, indexed_at TEXT);
    """)
    if use_fts5:
        con.execute("CREATE VIRTUAL TABLE IF NOT EXISTS mfts USING fts5(name, folder, description, methods, "
                    "components, blocks, features, guide, tokenize='porter unicode61', prefix='2 3')")
    else:
        con.execute("CREATE TABLE IF NOT EXISTS mfts(rowid INTEGER PRIMARY KEY, name TEXT, folder TEXT, "
                    "description TEXT, methods TEXT, components TEXT, blocks TEXT, features TEXT, guide TEXT)")
    con.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('fts5',?)", (str(int(use_fts5)),))
    con.commit()


def _meta(con, key, default=None):
    r = con.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return r["value"] if r else default


# ---------------------------------------------------------------------------
# reading one model
# ---------------------------------------------------------------------------
def read_model(path: Path) -> dict:
    """Parse a .bkp, or the first .bkp inside an .apwz. Returns the bkp summary plus 'inner_files'."""
    if path.suffix.lower() == ".apwz":
        with zipfile.ZipFile(str(path)) as z:
            names = z.namelist()
            inner = [n for n in names if n.lower().endswith(".bkp")]
            if not inner:
                return {"status": "no-bkp-inside", "inner_files": names, "blocks": {}, "components": []}
            d = bkp.parse_text(bkp.decode(z.read(inner[0])), str(path))
            d["inner_files"] = names
            d["inner_bkp"] = inner[0]
    else:
        d = bkp.parse(path)
        d["inner_files"] = []
    d["status"] = "ok"
    return d


def features_of(d: dict, companions: Dict[str, List[str]]) -> List[str]:
    f = []
    if d.get("calculators"):
        f.append("calculator")
    if d.get("design_specs"):
        f.append("design-spec")
    if d.get("sensitivities"):
        f.append("sensitivity")
    if d.get("optimizations"):
        f.append("optimization")
    if d.get("tears"):
        f.append("tear")
    if d.get("convergence_blocks"):
        f.append("convergence")
    if any(b.get("hierarchy") or b.get("type") == "HIERARCHY" for b in d.get("blocks", {}).values()):
        f.append("hierarchy")
    # ions, or complete dissociations: electrolyte chemistry (salt precipitation alone, e.g. an organic
    # acid crystallising, is 'chemistry' + 'solids', not an electrolyte system)
    if d.get("ions") or any(c.get("dissociations") for c in (d.get("chemistry") or {}).values()):
        f.append("electrolyte")
    if d.get("chemistry"):
        f.append("chemistry")
    if d.get("henry"):
        f.append("henry")
    if (set(d.get("substreams") or []) - {"MIXED"}) or any("(S)" in c["id"] for c in d.get("components", [])):
        f.append("solids")
    if d.get("reactions"):
        f.append("reactions")
    if any(x.get("lines") for x in (d.get("fortran") or {}).values()):
        f.append("fortran")
    inner_f = any(n.lower().endswith((".f", ".for", ".dll")) for n in d.get("inner_files", []))
    if companions.get("fortran") or inner_f:
        f.append("user-fortran")
    if companions.get("excel"):
        f.append("excel")
    if companions.get("acm") or any(b.get("type") == "ACM" for b in d.get("blocks", {}).values()):
        f.append("acm")
    rc = (d.get("run_class") or "").upper()
    if rc and rc != "FLOWSHEET":
        f.append("properties-only")
    if (d.get("run") or {}).get("has_results"):
        f.append("results")
    if d.get("user_sequence"):
        f.append("user-sequence")
    return f


def _words(s: str) -> set:
    return {w for w in re.findall(r"[a-z0-9]+", s.lower()) if len(w) >= 3 or w.isdigit()} - {"model", "the", "and",
                                                                                             "with", "aspen", "plus"}


def match_guides(model_stem: str, pdfs: List[Path], n_models: int = 1) -> List[Path]:
    """PDF guides that belong to a model: same name, else best word overlap, else all PDFs when the
    model is alone in its folder."""
    if not pdfs:
        return []
    exact = [p for p in pdfs if p.stem.lower() == model_stem.lower()]
    if exact:
        return exact
    mw = _words(model_stem)
    scored = []
    for p in pdfs:
        pw = _words(p.stem)
        if mw and pw:
            j = len(mw & pw) / len(mw | pw)
            if j >= 0.25:
                scored.append((j, p))
    if scored:
        best = max(s for s, _ in scored)
        return [p for s, p in scored if s >= best - 1e-9]
    return pdfs if n_models == 1 and len(pdfs) <= 3 else []


# ---------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------
def build(roots: List[str], max_seconds: float = 0, rebuild: bool = False, progress=print,
          guide_pages: int = 2) -> dict:
    t0 = time.time()
    path = db_path()
    if rebuild:
        for p in (path, Path(str(path) + "-wal"), Path(str(path) + "-shm")):
            if p.exists():
                p.unlink()
    con = connect(path)
    use_fts5 = fts5_available() if _meta_safe(con) is None else _meta(con, "fts5", "1") == "1"
    _init(con, use_fts5)
    backend = docsdb.pdf_backend()
    seen, added, updated, failed, n_total = set(), 0, 0, 0, 0
    guide_cache: Dict[str, str] = {}
    complete = True
    missing_roots = []
    for root in roots:
        rp = Path(root)
        if not rp.exists():
            missing_roots.append(str(rp))
            continue
        files = sorted(p for p in rp.rglob("*") if p.is_file() and p.suffix.lower() in MODEL_EXTS)
        per_dir = Counter(p.parent for p in files)
        for f in files:
            rel = f.relative_to(rp).as_posix()
            key = f"{rp.as_posix()}::{rel}"
            seen.add(key)
            n_total += 1
            st = f.stat()
            row = con.execute("SELECT id, size, mtime, status FROM models WHERE rel=?", (key,)).fetchone()
            if row and row["size"] == st.st_size and abs(row["mtime"] - st.st_mtime) < 1 and row["status"] == "ok":
                continue
            if max_seconds and time.time() - t0 > max_seconds:
                complete = False
                break
            folder_files = [p for p in f.parent.iterdir() if p.is_file()]
            comp: Dict[str, List[str]] = {}
            for p in folder_files:
                kind = COMPANION.get(p.suffix.lower())
                if kind and p != f:
                    comp.setdefault(kind, []).append(p.name)
            pdfs = [p for p in folder_files if p.suffix.lower() == ".pdf"]
            guides = match_guides(f.stem, pdfs, per_dir[f.parent])
            gtext = []
            for g in guides:
                gk = str(g)
                if gk not in guide_cache:
                    pages, title = docsdb.pdf_first_pages(g, guide_pages, backend) if backend else ([], "")
                    guide_cache[gk] = re.sub(r"\s+", " ", (title + " " + " ".join(pages)))[:6000]
                gtext.append(guide_cache[gk])
            try:
                d = read_model(f)
                status = d.get("status", "ok")
            except Exception as e:  # pragma: no cover - damaged file
                d, status = {"blocks": {}, "components": []}, f"error: {type(e).__name__}"
                failed += 1
            types = Counter(b.get("type") or (b.get("model") or "").upper() for b in d.get("blocks", {}).values())
            feats = features_of(d, comp) if status == "ok" else []
            comps = d.get("components", [])
            folder = str(Path(rel).parent.as_posix()) if "/" in rel else ""
            summary = {k: d.get(k) for k in ("engine", "release", "saved", "run_class", "description",
                                              "property_methods", "property_options", "chemistry", "henry",
                                              "reactions", "substreams", "calculators", "design_specs",
                                              "sensitivities", "optimizations", "convergence_blocks", "tears",
                                              "disabled", "hidden", "user_sequence", "inner_bkp")}
            summary["components"] = comps
            summary["blocks"] = {k: {"model": v.get("model"), "type": v.get("type"), "in": v.get("in"),
                                     "out": v.get("out"), "hierarchy": v.get("hierarchy")}
                                 for k, v in d.get("blocks", {}).items()}
            summary["has_results"] = bool((d.get("run") or {}).get("has_results"))
            summary["fortran_objects"] = [k for k, v in (d.get("fortran") or {}).items() if v.get("lines")]
            summary["inner_files"] = d.get("inner_files", [])
            vals = dict(root=str(rp), rel=key, folder=folder, name=f.stem, kind=f.suffix.lower()[1:],
                        release=d.get("release") or d.get("engine") or "", run_class=d.get("run_class", ""),
                        description=d.get("description", ""),
                        methods=" ".join(d.get("property_methods", [])),
                        components=" ".join(c["id"] + (" " + c["databank_name"] if c.get("databank_name") else "")
                                            for c in comps),
                        ions=" ".join(d.get("ions", [])), block_types=json.dumps(dict(types.most_common())),
                        n_blocks=len(d.get("blocks", {})), features=" ".join(feats),
                        files=json.dumps(comp), guides=json.dumps([g.name for g in guides]), size=st.st_size,
                        mtime=st.st_mtime, status=status, summary=json.dumps(summary, default=str),
                        indexed_at=now_iso())
            if row:
                con.execute("UPDATE models SET " + ", ".join(f"{k}=?" for k in vals) + " WHERE id=?",
                            list(vals.values()) + [row["id"]])
                mid = row["id"]
                con.execute("DELETE FROM mfts WHERE rowid=?", (mid,))
                updated += 1
            else:
                cur = con.execute("INSERT INTO models(" + ",".join(vals) + ") VALUES(" + ",".join("?" * len(vals))
                                  + ")", list(vals.values()))
                mid = cur.lastrowid
                added += 1
            blocks_txt = " ".join(f"{t} {t.title()}" for t in types) + " " + " ".join(
                (v.get("model") or "") for v in d.get("blocks", {}).values())
            con.execute("INSERT INTO mfts(rowid, name, folder, description, methods, components, blocks, features, "
                        "guide) VALUES(?,?,?,?,?,?,?,?,?)",
                        (mid, f.stem.replace("_", " "), folder.replace("/", " "), vals["description"],
                         vals["methods"], vals["components"] + " " + vals["ions"], blocks_txt,
                         " ".join(feats).replace("-", " ") + " " + " ".join(feats), " ".join(gtext)))
            con.commit()
        if not complete:
            break
    removed = 0
    if complete:
        for r in con.execute("SELECT id, rel, root FROM models").fetchall():
            if r["rel"] not in seen and r["root"] not in missing_roots:
                con.execute("DELETE FROM models WHERE id=?", (r["id"],))
                con.execute("DELETE FROM mfts WHERE rowid=?", (r["id"],))
                removed += 1
        con.commit()
    n = con.execute("SELECT COUNT(*) AS n FROM models").fetchone()["n"]
    con.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('complete',?)", (str(int(complete)),))
    con.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('updated',?)", (now_iso(),))
    con.commit()
    con.close()
    return {"complete": complete, "models": n, "files_seen": n_total, "added": added, "updated": updated,
            "removed": removed, "failed": failed, "missing_roots": missing_roots, "pdf_backend": backend or "none",
            "seconds": round(time.time() - t0, 1)}


def _meta_safe(con):
    try:
        return _meta(con, "fts5")
    except sqlite3.Error:
        return None


def status() -> dict:
    p = db_path()
    if not p.exists():
        return {"exists": False}
    con = connect(p)
    try:
        n = con.execute("SELECT COUNT(*) AS n FROM models").fetchone()["n"]
        return {"exists": True, "models": n, "complete": _meta(con, "complete", "0") == "1",
                "updated": _meta(con, "updated", "")}
    finally:
        con.close()


# ---------------------------------------------------------------------------
# search / show
# ---------------------------------------------------------------------------
def _filters_sql(block=None, method=None, component=None, has=None, folder=None):
    sql, args = [], []
    for b in (block or []):
        sql.append("m.block_types LIKE ?")
        args.append(f'%"{b.upper()}"%')
    for mth in (method or []):
        sql.append("(' ' || m.methods || ' ') LIKE ?")
        args.append(f"% {mth.upper()} %")
    for c in (component or []):
        sql.append("(' ' || UPPER(m.components) || ' ' || UPPER(m.ions) || ' ') LIKE ?")
        args.append(f"% {c.upper()} %")
    for h in (has or []):
        sql.append("(' ' || m.features || ' ') LIKE ?")
        args.append(f"% {h.lower()} %")
    if folder:
        sql.append("m.rel LIKE ?")
        args.append(f"%{folder}%")
    return sql, args


def search(query: str = "", limit: int = 10, block=None, method=None, component=None, has=None,
           folder=None) -> List[dict]:
    con = connect()
    try:
        use_fts5 = _meta(con, "fts5", "1") == "1"
        fsql, fargs = _filters_sql(block, method, component, has, folder)
        results, seen = [], set()
        terms = _terms(query) if query else []
        if terms and use_fts5:
            queries = [" AND ".join(terms)] + ([" OR ".join(terms)] if len(terms) > 1 else [])
            for q in queries:
                sql = ("SELECT m.*, snippet(mfts, -1, '[', ']', ' ... ', 14) AS snip, "
                       "bm25(mfts, 6.0, 3.0, 3.0, 4.0, 2.0, 3.0, 2.0, 1.0) AS score "
                       "FROM mfts JOIN models m ON m.id = mfts.rowid WHERE mfts MATCH ?")
                args = [q]
                for s in fsql:
                    sql += " AND " + s
                args += fargs
                sql += " ORDER BY score LIMIT ?"
                args.append(limit)
                try:
                    rows = con.execute(sql, args).fetchall()
                except sqlite3.OperationalError:
                    rows = []
                for r in rows:
                    if r["id"] not in seen:
                        seen.add(r["id"])
                        results.append(_row(r, "all terms" if q == queries[0] else "some terms"))
                if len(results) >= limit:
                    break
        elif terms:  # no FTS5: plain LIKE over the text columns
            like = " AND ".join(["(m.name || ' ' || m.folder || ' ' || m.description || ' ' || m.methods || ' ' || "
                                 "m.components || ' ' || m.block_types || ' ' || m.features) LIKE ?"] * len(terms))
            sql = "SELECT m.*, '' AS snip FROM models m WHERE " + like
            args = [f"%{t.strip(chr(34))}%" for t in terms]
            for s in fsql:
                sql += " AND " + s
            args += fargs
            sql += " LIMIT ?"
            args.append(limit)
            results = [_row(r, "all terms") for r in con.execute(sql, args).fetchall()]
        else:  # filters only
            sql = "SELECT m.*, '' AS snip FROM models m" + (" WHERE " + " AND ".join(fsql) if fsql else "")
            sql += " ORDER BY m.folder, m.name LIMIT ?"
            results = [_row(r, "filters") for r in con.execute(sql, fargs + [limit]).fetchall()]
        return results[:limit]
    finally:
        con.close()


def _row(r, match: str) -> dict:
    root, rel = r["rel"].split("::", 1) if "::" in r["rel"] else ("", r["rel"])
    bt = json.loads(r["block_types"] or "{}")
    return {"id": r["id"], "name": r["name"], "folder": r["folder"], "path": str(Path(root) / rel),
            "release": r["release"], "methods": r["methods"], "run_class": r["run_class"],
            "blocks": bt, "n_blocks": r["n_blocks"], "features": (r["features"] or "").split(),
            "guides": json.loads(r["guides"] or "[]"), "snippet": (r["snip"] if "snip" in r.keys() else ""),
            "match": match}


def resolve(ref: str) -> Optional[dict]:
    con = connect()
    try:
        r = None
        if str(ref).isdigit():
            r = con.execute("SELECT * FROM models WHERE id=?", (int(ref),)).fetchone()
        if r is None:
            rows = con.execute("SELECT * FROM models WHERE rel LIKE ? OR name LIKE ? ORDER BY length(rel)",
                               (f"%{ref}%", f"%{ref}%")).fetchall()
            r = rows[0] if rows else None
        if r is None:
            return None
        d = dict(r)
        d["summary"] = json.loads(d["summary"] or "{}")
        d["files"] = json.loads(d["files"] or "{}")
        d["guides"] = json.loads(d["guides"] or "[]")
        d["block_types"] = json.loads(d["block_types"] or "{}")
        root, rel = d["rel"].split("::", 1)
        d["path"] = str(Path(root) / rel)
        return d
    finally:
        con.close()


def find_components(query: str, limit: int = 15) -> List[dict]:
    """Component IDs, databank aliases and databank names used in the indexed models that match
    `query` (an ID, alias/formula or databank name; 3+ characters also match inside names).
    The alias is what an input file needs: 'COMPONENTS <id> <alias>'."""
    q = query.upper().strip()
    agg: Dict[tuple, dict] = {}
    con = connect()
    try:
        for r in con.execute("SELECT name, summary FROM models ORDER BY name"):
            for c in (json.loads(r["summary"] or "{}").get("components") or []):
                cid, alias, db = (str(c.get(k) or "").upper() for k in ("id", "alias", "databank_name"))
                ctype = str(c.get("type") or "CONV").upper()
                exact = q in (cid, alias, db)
                if not (exact or (len(q) >= 3 and any(q in x for x in (cid, alias, db)))):
                    continue
                e = agg.setdefault((alias, db, ctype), {"alias": c.get("alias") or "", "type": ctype,
                                                        "databank_name": c.get("databank_name") or "",
                                                        "ids": Counter(), "models": set(), "exact": False})
                e["ids"][c.get("id")] += 1
                e["models"].add(r["name"])
                e["exact"] = e["exact"] or exact
    finally:
        con.close()
    rows = sorted(agg.values(), key=lambda e: (not e["exact"], -len(e["models"]), e["alias"]))
    return [{"alias": e["alias"], "databank_name": e["databank_name"], "type": e["type"],
             "ids": [i for i, _ in e["ids"].most_common(4)], "models": len(e["models"]),
             "example": sorted(e["models"])[0], "exact": e["exact"]} for e in rows[:limit]]


def render_components(rows: List[dict], query: str) -> str:
    if not rows:
        return (f"No component matching {query!r} in the indexed models. Search the databank in Aspen Plus: "
                "Components > Specifications > Find.")
    L = [f"# Components matching {query!r} in the indexed models", "",
         "| COMPONENTS line | Type | Databank name | Used in |", "|---|---|---|---|"]
    for r in rows:
        line = f"{r['ids'][0]} {r['alias']}".strip() if r["alias"] else f"{r['ids'][0]}  (no alias: user component)"
        others = f" (also as {', '.join(r['ids'][1:])})" if len(r["ids"]) > 1 else ""
        L.append(f"| `{line}`{others} | {r['type'].lower()} | {r['databank_name'] or '-'} | {r['models']} model(s), "
                 f"e.g. {r['example']} |")
    L.append("")
    L.append("The second word is the databank alias the input file needs; the ID (first word) is yours to choose. "
             "Type 'solid' is Type = Solid on the Components form: in an input file list the ID in CISOLID-COMPS "
             "too (required when the solid is in the MIXED substream, e.g. a precipitating salt). IDs with "
             "parentheses are written in double quotes: \"NACL(S)\" NACL. Aliases are those of the release the "
             "examples come from.")
    return "\n".join(L)


def folders() -> List[dict]:
    con = connect()
    try:
        rows = con.execute("SELECT folder, COUNT(*) AS n, GROUP_CONCAT(features, ' ') AS f FROM models "
                           "GROUP BY folder ORDER BY folder").fetchall()
        out = []
        for r in rows:
            c = Counter((r["f"] or "").split())
            out.append({"folder": r["folder"] or "(top)", "models": r["n"],
                        "features": [k for k, _ in c.most_common(6) if k not in ("results",)]})
        return out
    finally:
        con.close()


_FEATURE_TOKENS = set(FEATURE_WORDS) | {p for w in FEATURE_WORDS for p in w.split("-")} | {"results"}


def _only_feature_words(snippet: str) -> bool:
    """A snippet taken from the feature list repeats the 'has:' line; it says nothing new."""
    words = re.findall(r"[a-z]+", snippet.lower())
    return bool(words) and all(w in _FEATURE_TOKENS for w in words)


def render_search(res: List[dict]) -> str:
    if not res:
        return "No matching models."
    L = []
    for i, r in enumerate(res, 1):
        bt = ", ".join(f"{k} x{v}" if v > 1 else k for k, v in list(r["blocks"].items())[:8])
        feats = ", ".join(x for x in r["features"] if x != "results")
        L.append(f"[{i}] {r['name']}   (id {r['id']}, {r['release'] or '?'}, {r['match']})")
        L.append(f"    {r['folder']}")
        L.append(f"    method: {r['methods'] or '-'} | blocks: {bt or ('none: ' + (r['run_class'] or '?'))}")
        if feats:
            L.append(f"    has: {feats}")
        if r["guides"]:
            L.append(f"    guide: {', '.join(r['guides'])}")
        if r.get("snippet") and not _only_feature_words(r["snippet"]):
            snip = truncate(re.sub(r"\s+", " ", r["snippet"]), 220)
            L.append(f"    ... {snip}")
    L.append("\nDetails: python fw.py examples-show <id>   |   raw input sections: examples-show <id> --section <name>")
    return "\n".join(L)


def render_show(d: dict) -> str:
    s = d["summary"]
    L = [f"# {d['name']}", f"File: {d['path']}" + (f" (inside: {s.get('inner_bkp')})" if s.get("inner_bkp") else "")]
    L.append(f"- Folder: {d['folder'] or '(top)'} | Aspen Plus {d['release'] or '?'}"
             + (" | saved with results" if s.get("has_results") else " | no results stored"))
    if s.get("run_class") and s["run_class"].upper() != "FLOWSHEET":
        L.append(f"- Run type: {s['run_class']}")
    if s.get("description"):
        L.append(f"- Description: {truncate(s['description'], 600)}")
    po = s.get("property_options") or {}
    L.append(f"- Property method: {', '.join(s.get('property_methods') or []) or '-'}"
             + (f" | chemistry {po['chemistry']}" if po.get("chemistry") else "")
             + (f" | Henry {po['henry']}" if po.get("henry") else "")
             + ((" | true components" if str(po.get("true_comps", "")).upper() == "YES" else " | apparent components")
                if po.get("true_comps") else ""))
    comps = s.get("components") or []
    L.append(f"- Components ({len(comps)}): " + ", ".join(
        c["id"] + (f" ({c['databank_name']})" if c.get("databank_name") and c["databank_name"] != c["id"] else "")
        for c in comps[:60]) + (" ..." if len(comps) > 60 else ""))
    for cid, c in (s.get("chemistry") or {}).items():
        L.append(f"- Chemistry {cid}: {c['equilibria']} equilibria, {c['dissociations']} dissociations, "
                 f"{c['salts']} salts")
    for hid, hc in (s.get("henry") or {}).items():
        L.append(f"- Henry components {hid}: {' '.join(hc)}")
    if s.get("reactions"):
        L.append(f"- Reaction sets: {', '.join(s['reactions'])}")
    for label, key in (("Calculators", "calculators"), ("Design specs", "design_specs"),
                       ("Sensitivity", "sensitivities"), ("Optimization", "optimizations"),
                       ("Convergence blocks", "convergence_blocks"), ("Tear streams", "tears"),
                       ("Disabled", "disabled")):
        if s.get(key):
            L.append(f"- {label}: {', '.join(s[key])}")
    if s.get("fortran_objects"):
        L.append(f"- Inline Fortran in: {', '.join(s['fortran_objects'])}")
    if s.get("user_sequence"):
        L.append("- User-defined calculation sequence")
    if s.get("hidden"):
        L.append(f"- Hidden objects (Hide/Reveal, not calculated): {', '.join(s['hidden'])}")
    blocks = s.get("blocks") or {}
    if blocks:
        L.append("")
        L.append(f"## Blocks ({len(blocks)})")
        L.append("| Block | Model | In -> Out |")
        L.append("|---|---|---|")
        for name, b in list(blocks.items())[:80]:
            L.append(f"| {name} | {b.get('model')} | {' '.join(b.get('in') or [])} -> {' '.join(b.get('out') or [])} |")
        if len(blocks) > 80:
            L.append(f"| ... | {len(blocks) - 80} more | |")
    files = d.get("files") or {}
    if files or s.get("inner_files"):
        L.append("")
        L.append("## Files next to the model")
        for kind, names in files.items():
            if kind == "guide":
                others = [n for n in names if n not in (d.get("guides") or [])]
                if others:
                    L.append(f"- other PDFs in the folder: {len(others)}")
                continue
            L.append(f"- {kind}: {', '.join(names[:12])}" + (f" (+{len(names) - 12})" if len(names) > 12 else ""))
        if s.get("inner_files"):
            L.append(f"- inside the .apwz: {', '.join(s['inner_files'])}")
    if d.get("guides"):
        L.append("")
        L.append(f"Guide: {', '.join(d['guides'])} (search it with docs-search once the folder is in the library "
                 f"index; `setup --examples` adds it)")
    L.append("")
    L.append("How the vendor set something up: `python fw.py examples-show <id> --section \"CHEMISTRY\"` "
             "(or a block name). Full structure: `python fw.py bkp <file>`.")
    return "\n".join(L)


def _sections(d: dict):
    path = Path(d["path"])
    if path.suffix.lower() == ".apwz":
        with zipfile.ZipFile(str(path)) as z:
            inner = [n for n in z.namelist() if n.lower().endswith(".bkp")]
            text = bkp.decode(z.read(inner[0])) if inner else ""
    else:
        text = read_text_any(path)
    input_part = text.split(" GRAPHICS_BACKUP", 1)[0]
    k = input_part.find("\n? ")
    serial = bkp._HIDE_RX.sub(" ", input_part[k:].replace("\n", "") if k >= 0 else "")
    return bkp.parse_sections(serial)


def _n(v) -> str:
    """'-2.0' -> '-2.', '1' -> '1.' (input-language style)."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)
    return f"{f:.10g}" + ("." if f == int(f) and "e" not in f"{f:.10g}" else "")


def chemistry_as_inp(d: dict) -> str:
    """The CHEMISTRY sections of a model translated to input language (STOIC, K-STOIC, DISS, SALT, K-SALT)."""
    out = []
    for sname, recs in _sections(d).items():
        if not sname.startswith("CHEMISTRY "):
            continue
        cid = sname[len("CHEMISTRY "):].strip()
        reac: "OrderedDict[str, list]" = OrderedDict()
        kst, diss, salt, ksalt = [], OrderedDict(), OrderedDict(), []
        for r in recs:
            kw = r["_kw"]
            if kw == "STOIC" and r.get("REACNO"):
                reac.setdefault(r["REACNO"], []).append((r.get("STOIC-CID"), r.get("COEF")))
            elif kw == "STOIC1" and r.get("REACNO1"):
                reac.setdefault(r["REACNO1"], []).append((r.get("STOIC-CID1"), r.get("COEF1")))
            elif kw == "K-STOIC" and any(k in r for k in ("A", "B", "C", "D")):
                kst.append((r.get("K-S-REACNO"), [(k, r[k]) for k in ("A", "B", "C", "D") if k in r]))
            elif kw == "DISS" and r.get("ELECID"):
                diss.setdefault(r["ELECID"], []).append((r.get("DISS-CID"), r.get("DISS-COEF")))
            elif kw == "SALT" and r.get("SALTID"):
                salt.setdefault(r["SALTID"], []).append((r.get("SALT-CID"), r.get("SALT-COEF")))
            elif kw == "K-SALT" and r.get("K-SALTID"):
                ksalt.append((r["K-SALTID"], [(k[2:], r[k]) for k in ("K-A", "K-B", "K-C", "K-D") if k in r]))
        L = [f"CHEMISTRY {cid}"]
        for n, ents in reac.items():
            L.append(f"    STOIC {n} " + " / ".join(f"{c} {_n(v)}" for c, v in ents))
        for n, ks in kst:
            L.append(f"    K-STOIC {n} " + " ".join(f"{k}={v}" for k, v in ks))
        for e, ents in diss.items():
            L.append(f"    DISS {e} " + " / ".join(f"{c} {_n(v)}" for c, v in ents))
        for s, ents in salt.items():
            L.append(f"    SALT {s} " + " / ".join(f"{c} {_n(v)}" for c, v in ents))
        for s, ks in ksalt:
            L.append(f"    K-SALT {s} " + " ".join(f"{k}={v}" for k, v in ks))
        out.append(_wrap("\n".join(L)))
    if not out:
        return "No CHEMISTRY section in this model."
    return ("; Translated from the example's input tree by proc-sim-agent. Reactions without K-STOIC take K\n"
            "; from reference-state Gibbs energies (unsymmetric ion reference state). Component IDs are the\n"
            "; example's: map them to yours. Run inp-check on the file you paste this into.\n"
            + "\n\n".join(out))


def _wrap(text: str, width: int = 78) -> str:
    """Wrap long input-language lines with ' &' continuations, breaking at ' / ' or spaces."""
    lines = []
    for line in text.split("\n"):
        while len(line) > width:
            cut = line.rfind(" / ", 0, width - 2)
            cut = cut + 2 if cut > 10 else line.rfind(" ", 0, width - 2)
            if cut <= 10:
                break
            lines.append(line[:cut].rstrip() + " &")
            line = "        " + line[cut:].lstrip()
        lines.append(line)
    return "\n".join(lines)


def section_text(d: dict, name: str, max_chars: int = 8000) -> str:
    """Raw input-tree records of the sections whose name contains `name` (case-insensitive)."""
    secs = _sections(d)
    want = name.upper()
    out = []
    for sname, recs in secs.items():
        if want in sname.upper():
            out.append(f"## {sname}")
            for rec in recs:
                kv = " ".join(f"{k}={'(' + ' '.join(v) + ')' if isinstance(v, list) else v}"
                              for k, v in rec.items() if k not in ("_kw", "_words"))
                words = " ".join(rec.get("_words", []))
                out.append(f"  {rec['_kw']} {kv} {words}".rstrip())
    txt = "\n".join(out) if out else f"No section matching {name!r}. Sections: " + ", ".join(
        s for s in secs if not s.startswith(("PROPERTIES PARAMETERS", '"PROP-SET"', "SETUP")))[:3000]
    return txt if len(txt) <= max_chars else txt[:max_chars] + "\n... (truncated)"
