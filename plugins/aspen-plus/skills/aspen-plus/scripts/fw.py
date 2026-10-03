#!/usr/bin/env python3
"""ModelAide command line: index and search local Aspen help, a personal library, and simulation folders.

Run `python fw.py <command> -h` for details. Commands:
  setup        register help folders, library folders and simulation folders
  status       show configuration and index state
  help-index   build/continue the help index (resumable; repeat until complete)
  help-search  full-text search of the help
  help-read    print a help topic as Markdown (by id, path, F1 id or title)
  help-toc     list books, or show one book's table of contents
  docs-index   build/continue the library index (PDF/DOCX/TXT/MD/HTML)
  docs-search  search the library;   docs-read: print pages;   docs-list: list documents
  sim-scan     summarise simulation folders (one folder per model version)
  his          digest of an Aspen Plus .his file (model, messages, convergence, block results, lint)
  his-diff     what changed in the input between two .his files
  bkp          structure summary of an Aspen Plus .bkp file
  rep          read a report export (.rep): status, convergence, blocks, stream tables
  cpm          read a Control Panel export (.cpm): progress, loops, messages, error summary

Only the Python standard library is required (PDF text needs pypdf or PyMuPDF).
Nothing is uploaded: indexes live in ~/.modelaide (override with MODELAIDE_HOME).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fwlib import bkp, cpm, docsdb, helpdb, his, madcap, rep, sims  # noqa: E402
from fwlib.common import (APP_TITLE, DEFAULT_HELP_GLOBS, PRODUCTS, config_path, data_home,  # noqa: E402
                          expand_globs, fts5_available, load_config, print_json, save_config, setup_io)

EXIT_INCOMPLETE = 3


def _die(msg: str, code: int = 2):
    print(msg, file=sys.stderr)
    sys.exit(code)


# ---------------------------------------------------------------------------
# config helpers
# ---------------------------------------------------------------------------
def _register_help(cfg: dict, path: str) -> dict:
    root = madcap.find_help_root(path)
    if not root:
        _die(f"No MadCap help (*.mcwebhelp) found in or under: {path}")
    root = root.resolve()  # absolute, so later runs work from any folder
    product, title = madcap.detect_product(root)
    version = madcap.detect_version(root)
    db = helpdb.db_path_for(product, version)
    cfg["help"][product] = {"root": str(root), "title": title, "version": version, "db": str(db)}
    return cfg["help"][product]


def _product(cfg: dict, wanted: str = None) -> dict:
    helps = cfg.get("help", {})
    if not helps:
        _die("No help folder registered. Run:\n  python fw.py setup --help-root \"<folder with the Aspen help>\"\n"
             "(default: C:\\ProgramData\\AspenTech\\Aspen Plus V15.0\\HtmlHelp), or: python fw.py setup --auto")
    if wanted:
        key = wanted.lower()
        for k in helps:
            if k == key or k.endswith(key) or key in k:
                return {"key": k, **helps[k]}
        _die(f"Product '{wanted}' not registered. Registered: {', '.join(helps)}")
    key = "aspen-plus" if "aspen-plus" in helps else next(iter(helps))
    return {"key": key, **helps[key]}


def _need_index(p: dict) -> Path:
    db = Path(p["db"])
    if not db.exists():
        _die(f"The {p['title']} help is registered but not indexed yet. Run:\n  python fw.py help-index"
             + (f" --product {p['key']}" if p["key"] != "aspen-plus" else "")
             + "\n(repeat until it reports 'complete'; each run continues where the last stopped)")
    return db


# ---------------------------------------------------------------------------
# commands
# ---------------------------------------------------------------------------
def cmd_setup(a):
    cfg = load_config()
    changed = False
    roots = list(a.help_root or [])
    if a.auto:
        found = expand_globs(DEFAULT_HELP_GLOBS)
        if not found:
            print("No help found in the default AspenTech locations; pass --help-root explicitly.")
        roots += found
    for r in roots:
        info = _register_help(cfg, r)
        print(f"help: {info['title']} {info['version']}  ->  {info['root']}")
        changed = True
    for f in a.library or []:
        p = str(Path(f).expanduser().resolve())
        if not Path(p).exists():
            print(f"warning: library folder not found: {p}")
        if p not in cfg["library"]["folders"]:
            cfg["library"]["folders"].append(p)
            changed = True
    for f in a.sims or []:
        p = str(Path(f).expanduser().resolve())
        if not Path(p).exists():
            print(f"warning: simulation folder not found: {p}")
        if p not in cfg["simulations"]["folders"]:
            cfg["simulations"]["folders"].append(p)
            changed = True
    for f in a.remove or []:
        forms = {f, str(Path(f).expanduser().resolve())}
        for sec in ("library", "simulations"):
            for x in forms & set(cfg[sec]["folders"]):
                cfg[sec]["folders"].remove(x)
                changed = True
        for k in list(cfg["help"]):
            if k == f or cfg["help"][k]["root"] in forms:
                del cfg["help"][k]
                changed = True
    if changed:
        print(f"saved {save_config(cfg)}")
    _print_config(cfg)
    if any(not Path(v["db"]).exists() for v in cfg["help"].values()):
        print("\nNext: python fw.py help-index   (repeat until it says 'complete')")
    if cfg["library"]["folders"] and not docsdb.db_path().exists():
        print("Next: python fw.py docs-index   (repeat until it says 'complete')")


def _print_config(cfg):
    print(f"\n{APP_TITLE} data folder: {data_home()}")
    print(f"config: {config_path()}")
    if cfg["help"]:
        for k, v in cfg["help"].items():
            st = helpdb.status(Path(v["db"]))
            state = ("complete" if st.get("complete") else f"partial ({st.get('books_done', 0)} books)") \
                if st["exists"] else "not indexed"
            print(f"  help  {k:18s} {v['version']:8s} {state:22s} {v['root']}")
    else:
        print("  help  (none registered)")
    for f in cfg["library"]["folders"]:
        print(f"  library      {f}")
    for f in cfg["simulations"]["folders"]:
        print(f"  simulations  {f}")


def cmd_status(a):
    cfg = load_config()
    print(f"{APP_TITLE} - Python {sys.version.split()[0]}, SQLite FTS5: {'yes' if fts5_available() else 'NO (slow fallback)'}"
          f", PDF text: {docsdb.pdf_backend() or 'none (pip install pypdf)'}")
    _print_config(cfg)
    for k, v in cfg["help"].items():
        st = helpdb.status(Path(v["db"]))
        if st["exists"]:
            print(f"  {k}: {st['topics']} topics, {st['books_done']}/{st['books_seen']} books indexed")
    lib = docsdb.list_docs()
    if lib:
        from collections import Counter
        c = Counter(d["status"] for d in lib)
        print(f"  library: {len(lib)} documents ({', '.join(f'{n} {s}' for s, n in c.items())})")
    if a.json:
        print_json({"config": cfg, "help": {k: helpdb.status(Path(v['db'])) for k, v in cfg['help'].items()}})


def cmd_help_index(a):
    cfg = load_config()
    p = _product(cfg, a.product)
    print(f"Indexing {p['title']} {p['version']} help from {p['root']}")
    res = helpdb.build(Path(p["root"]), Path(p["db"]), max_seconds=a.max_seconds, rebuild=a.rebuild,
                       only_books=a.books.split(",") if a.books else None)
    print(f"{res['books_done']}/{res['books_total']} books, {res['topics']} topics "
          f"(+{res['new_topics']} this run, {res['seconds']} s)")
    if res["complete"]:
        print("complete")
    else:
        print("INCOMPLETE - run the same command again to continue")
        sys.exit(EXIT_INCOMPLETE)


def cmd_help_search(a):
    cfg = load_config()
    p = _product(cfg, a.product)
    db = _need_index(p)
    res = helpdb.search(db, a.query, limit=a.limit, book=a.book, raw=a.raw)
    if a.json:
        print_json(res)
        return
    if not res:
        print("No matches. Try fewer or different words, a GUI term (e.g. 'Setup Specifications sheet'), "
              "or help-toc to browse.")
        return
    st = helpdb.status(db)
    if not st.get("complete"):
        print(f"(index incomplete: {st['books_done']} books so far - results may miss topics)\n")
    for i, r in enumerate(res, 1):
        print(f"[{i}] {r['title']}   (id {r['id']}, book {r['book']}, {r['match']})")
        if r["crumb"]:
            print(f"    {r['crumb']}")
        print(f"    {r['snippet']}")
    print(f"\nRead a topic: python fw.py help-read <id>")


def cmd_help_read(a):
    cfg = load_config()
    p = _product(cfg, a.product)
    db = _need_index(p)
    cands = helpdb.resolve(db, a.ref)
    if not cands:
        _die(f"No topic matches {a.ref!r}. Use help-search first.", 1)
    if len(cands) > 1 and not a.ref.isdigit():
        exact = [c for c in cands if c["title"].lower() == a.ref.lower()]
        if len(exact) != 1:
            print("Several topics match; pick an id:")
            for c in cands[:15]:
                print(f"  {c['id']:6d}  {c['title']}  [{c['book']}]  {c['crumb']}")
            return
        cands = exact
    t = cands[0]
    root = Path(p["root"])
    doc = madcap.parse_topic(root, t["rel"], links=True, equations=True) if (root / t["rel"]).exists() else None
    aliases = helpdb.topic_aliases(db, t["rel"])
    if a.json:
        print_json({"topic": t, "aliases": aliases, "markdown": doc["text"] if doc else None,
                    "links": doc["links"] if doc else []})
        return
    print(f"# {t['title']}")
    print(f"Path: {t['crumb']}" if t["crumb"] else "")
    print(f"Book: {t['book']} | topic id {t['id']}" + (f" | F1 help id: {', '.join(aliases)}" if aliases else ""))
    print(f"File: {root / t['rel']}")
    print()
    if not doc:
        print("(topic file not found - showing the indexed abstract)")
        print(t.get("abstract") or "")
        return
    text = doc["text"]
    if len(text) > a.max_chars:
        text = text[:a.max_chars] + f"\n\n... (truncated at {a.max_chars} characters; use --max-chars to see more)"
    print(text)
    if doc["equations"]:
        print(f"\n(Equations are images; the approximations above lose layout. Open the file to see them exactly.)")
    if a.links and doc["links"]:
        print("\nLinks from this topic:")
        for l in helpdb.link_targets(db, doc["links"]):
            print(f"  - {('id ' + str(l['id'])) if l['id'] else '(not indexed)'}: {l['title'] or l['rel']}"
                  + (f"  [{l['book']}]" if l["book"] else ""))


def cmd_help_toc(a):
    cfg = load_config()
    p = _product(cfg, a.product)
    root = Path(p["root"])
    db = Path(p["db"])
    ids = helpdb.topic_ids_by_rel(db) if db.exists() else {}
    if not a.book:
        rows = helpdb.books(db) if db.exists() else []
        if not rows:
            rows = [{"name": b.name, "title": madcap.book_title(b, root), "toc_path": b.toc_path, "n_topics": None}
                    for b in madcap.list_books(root)]
        if a.json:
            print_json(rows)
            return
        last = None
        for r in rows:
            tp = (r.get("toc_path") or "").replace("|", " > ") or "(main help)"
            if tp != last:
                print(f"\n{tp}")
                last = tp
            n = f"{r['n_topics']} topics" if r.get("n_topics") is not None else ""
            print(f"  {r['name']:18s} {r['title'][:70]:70s} {n}")
        print("\nShow a book's contents: python fw.py help-toc --book <name>")
        return
    books = {b.name.lower(): b for b in madcap.list_books(root)}
    b = books.get(a.book.lower())
    if not b:
        _die(f"No book named {a.book!r}. Run help-toc without --book to list them.")
    tree = madcap.book_toc(b, root)
    if a.json:
        print_json(tree)
        return
    print(f"{b.name}: {(b.toc_path or '(main help)').replace('|', ' > ')}")

    def walk(nodes, depth):
        for n in nodes:
            if a.depth and depth > a.depth:
                return
            tid = ids.get(n["rel"]) if n["rel"] else None
            label = n["title"] or (f"[book: {n['book']}]" if n["book"] else "")
            print("  " * depth + f"- {label}" + (f"  (id {tid})" if tid else ""))
            walk(n["children"], depth + 1)
    walk(tree, 1)


def cmd_docs_index(a):
    cfg = load_config()
    folders = cfg["library"]["folders"]
    if not folders:
        _die("No library folder registered. Run: python fw.py setup --library \"<folder with your PDFs>\"")
    if not docsdb.pdf_backend():
        print("note: no PDF text extractor found - PDFs will be listed but not searchable. "
              "Install one with: pip install pypdf")
    res = docsdb.build(folders, max_seconds=a.max_seconds, rebuild=a.rebuild)
    print(json.dumps({k: v for k, v in res.items() if k != "db"}, ensure_ascii=False))
    if res["complete"]:
        print("complete")
    else:
        print("INCOMPLETE - run the same command again to continue")
        sys.exit(EXIT_INCOMPLETE)


def cmd_docs_search(a):
    if not docsdb.db_path().exists():
        _die("Library not indexed yet. Run: python fw.py docs-index")
    res = docsdb.search(a.query, limit=a.limit, raw=a.raw)
    if a.json:
        print_json(res)
        return
    if not res:
        print("No matches in the library.")
        return
    for i, r in enumerate(res, 1):
        print(f"[{i}] {r['title']}, p. {r['page']}   (doc {r['doc']})")
        print(f"    {r['snippet']}")
        print(f"    {r['path']}")
    print("\nRead pages: python fw.py docs-read <doc> --pages 12-13")


def cmd_docs_read(a):
    if not docsdb.db_path().exists():
        _die("Library not indexed yet. Run: python fw.py docs-index")
    res = docsdb.read(a.ref, pages=a.pages, max_chars=a.max_chars)
    if "error" in res:
        _die(res["error"], 1)
    d = res["doc"]
    print(f"# {d['title']}  ({d['pages']} pages, {d['status']})\n{d['path']}\n")
    print(res["text"] or "(no text on these pages)")


def cmd_docs_list(a):
    docs = docsdb.list_docs()
    if a.json:
        print_json(docs)
        return
    for d in docs:
        print(f"{d['id']:5d}  {d['status']:9s} {d['pages'] or 0:5d} p  {d['title'][:80]}")


def cmd_sim_scan(a):
    cfg = load_config()
    roots = a.paths or cfg["simulations"]["folders"]
    if not roots:
        _die("Give a folder, or register one: python fw.py setup --sims \"<simulations folder>\"")
    res = sims.scan(roots, max_depth=a.depth)
    if a.json:
        print_json(res)
    else:
        print(sims.render_markdown(res))


def _pick_his(path: str) -> Path:
    p = Path(path).expanduser()
    if p.is_dir():
        cands = [f for f in p.glob("*.his") if not sims.TEMP_RX.match(f.name)] or list(p.glob("*.his"))
        if not cands:
            _die(f"No .his file in {p}")
        p = max(cands, key=lambda f: f.stat().st_mtime)
        print(f"(using {p.name})\n")
    if not p.exists():
        _die(f"File not found: {p}")
    return p


def cmd_his(a):
    p = _pick_his(a.file)
    d = his.parse(p)
    if a.echo:
        print(his.echo_text(d))
        return
    if a.json:
        slim = dict(d)
        slim["runs"] = [{k: v for k, v in r.items() if k != "echo"} for r in d["runs"]]
        print_json(slim)
        return
    print(his.render_markdown(d, fortran=a.fortran))


def cmd_his_diff(a):
    da, db_ = his.parse(_pick_his(a.a)), his.parse(_pick_his(a.b))
    out = his.diff(da, db_, context=a.context)
    print(out or "No differences in the input.")


def cmd_bkp(a):
    p = Path(a.file).expanduser()
    if not p.exists():
        _die(f"File not found: {p}")
    d = bkp.parse(p)
    if a.json:
        print_json(d)
    else:
        print(bkp.render_markdown(d))


def cmd_rep(a):
    p = Path(a.file).expanduser()
    if p.is_dir():
        cands = sorted(p.glob("*.rep"), key=lambda f: f.stat().st_mtime)
        if not cands:
            _die(f"No .rep file in {p}")
        p = cands[-1]
    if not p.exists():
        _die(f"File not found: {p}")
    d = rep.parse(p)
    if a.csv:
        rep.write_csv(d, a.csv)
        print(f"wrote {a.csv} ({len(d['streams'])} streams)")
        return
    if a.block:
        print(rep.block_text(d, a.block))
        return
    if a.section:
        print(rep.section_text(d, a.section))
        return
    if a.find:
        print(rep.find(d, a.find))
        return
    if a.streams:
        names = [x.strip() for x in a.streams.split(",") if x.strip()]
        print(rep.stream_table(d, names, components=not a.no_components))
        return
    if a.json:
        slim = {k: v for k, v in d.items() if k != "_sections"}
        for b in slim["blocks"].values():
            b.pop("lines", None)
        print_json(slim)
        return
    print(rep.render_markdown(d))


def cmd_cpm(a):
    p = Path(a.file).expanduser()
    if p.is_dir():
        cands = sorted(p.glob("*.cpm"), key=lambda f: f.stat().st_mtime)
        if not cands:
            _die(f"No .cpm file in {p}")
        p = cands[-1]
    if not p.exists():
        _die(f"File not found: {p}")
    d = cpm.parse(p)
    if a.json:
        print_json({k: v for k, v in d.items() if k != "messages"})
        return
    print(cpm.render_markdown(d))


def main(argv=None):
    setup_io()
    ap = argparse.ArgumentParser(prog="fw.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("setup", help="register folders")
    s.add_argument("--help-root", action="append", help="folder with the Aspen help (repeatable)")
    s.add_argument("--auto", action="store_true", help="look for installed help in the default AspenTech folders")
    s.add_argument("--library", action="append", help="folder with your PDFs/notes (repeatable)")
    s.add_argument("--sims", action="append", help="folder with simulation version folders (repeatable)")
    s.add_argument("--remove", action="append", help="unregister a folder or product")
    s.set_defaults(fn=cmd_setup)

    s = sub.add_parser("status", help="configuration and index state")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_status)

    s = sub.add_parser("help-index", help="build/continue the help index")
    s.add_argument("--product")
    s.add_argument("--max-seconds", type=float, default=100, help="stop after this many seconds (0 = no limit)")
    s.add_argument("--rebuild", action="store_true")
    s.add_argument("--books", help="comma-separated book names (for testing)")
    s.set_defaults(fn=cmd_help_index)

    s = sub.add_parser("help-search", help="search the help")
    s.add_argument("query")
    s.add_argument("--product")
    s.add_argument("-n", "--limit", type=int, default=8)
    s.add_argument("--book")
    s.add_argument("--raw", action="store_true", help="pass the query to SQLite FTS5 unchanged")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_help_search)

    s = sub.add_parser("help-read", help="print a help topic")
    s.add_argument("ref", help="topic id, file path, F1 help id, or title")
    s.add_argument("--product")
    s.add_argument("--max-chars", type=int, default=15000)
    s.add_argument("--links", action="store_true", help="list linked topics with their ids")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_help_read)

    s = sub.add_parser("help-toc", help="list books or one book's contents")
    s.add_argument("--product")
    s.add_argument("--book")
    s.add_argument("--depth", type=int, default=0)
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_help_toc)

    s = sub.add_parser("docs-index", help="build/continue the library index")
    s.add_argument("--max-seconds", type=float, default=100)
    s.add_argument("--rebuild", action="store_true")
    s.set_defaults(fn=cmd_docs_index)

    s = sub.add_parser("docs-search", help="search the library")
    s.add_argument("query")
    s.add_argument("-n", "--limit", type=int, default=8)
    s.add_argument("--raw", action="store_true")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_docs_search)

    s = sub.add_parser("docs-read", help="print pages of a library document")
    s.add_argument("ref", help="doc id, path or title fragment")
    s.add_argument("--pages", help="e.g. 12 or 12-14 or 3,7")
    s.add_argument("--max-chars", type=int, default=12000)
    s.set_defaults(fn=cmd_docs_read)

    s = sub.add_parser("docs-list", help="list indexed documents")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_docs_list)

    s = sub.add_parser("sim-scan", help="summarise simulation folders")
    s.add_argument("paths", nargs="*")
    s.add_argument("--depth", type=int, default=5)
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_sim_scan)

    s = sub.add_parser("his", help="digest of a .his file (or the newest .his in a folder)")
    s.add_argument("file")
    s.add_argument("--fortran", action="store_true", help="include calculator Fortran")
    s.add_argument("--echo", action="store_true", help="print the input echo (.inp text) only")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_his)

    s = sub.add_parser("his-diff", help="input differences between two .his files")
    s.add_argument("a")
    s.add_argument("b")
    s.add_argument("--context", type=int, default=2)
    s.set_defaults(fn=cmd_his_diff)

    s = sub.add_parser("bkp", help="structure summary of a .bkp file")
    s.add_argument("file")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_bkp)

    s = sub.add_parser("rep", help="read a report export (.rep)")
    s.add_argument("file", help=".rep file or a folder (newest .rep)")
    s.add_argument("--streams", help="comma-separated stream names, or 'all'")
    s.add_argument("--no-components", action="store_true", help="stream table without component rows")
    s.add_argument("--block", help="print one block's section")
    s.add_argument("--section", help="print a report section, e.g. 'FLOWSHEET' or 'PROBLEM STATUS'")
    s.add_argument("--find", help="search the report text")
    s.add_argument("--csv", help="write all stream properties to this CSV file")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_rep)

    s = sub.add_parser("cpm", help="read a Control Panel export (.cpm)")
    s.add_argument("file", help=".cpm file or a folder (newest .cpm)")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_cpm)

    a = ap.parse_args(argv)
    try:
        a.fn(a)
    except BrokenPipeError:  # output piped into head/less that closed early
        try:
            sys.stdout = open(os.devnull, "w")
        except OSError:
            pass
        sys.exit(0)


if __name__ == "__main__":
    main()
