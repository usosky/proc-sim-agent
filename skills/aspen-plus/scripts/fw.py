#!/usr/bin/env python3
"""proc-sim-agent command line: index and search local Aspen help, a personal library, and simulation folders.

Run `python fw.py <command> -h` for details. Commands:
  setup        register help folders, library folders and simulation folders
  status       show configuration and index state
  help-index   build/continue the help index (resumable; repeat until complete)
  help-search  full-text search of the help
  help-read    print a help topic as Markdown (by id, path, F1 id or title)
  help-toc     list books, or show one book's table of contents
  docs-index   build/continue the library index (PDF/DOCX/TXT/MD/HTML)
  docs-search  search the library;   docs-read: print pages;   docs-list: list documents
  examples-index   build/continue the index of a model library (the Aspen Plus examples)
  examples-search  find example models by topic, block type, method, component or feature
  examples-show    one example's structure, files and raw input sections; examples-list: folders
  sim-scan     summarise simulation folders (one folder per model version)
  his          digest of an Aspen Plus .his file (model, messages, convergence, block results, lint);
               --inp writes the run's input as an .inp file
  his-diff     what changed in the input between two .his files
  bkp          structure summary of an Aspen Plus .bkp file
  rep          read a report export (.rep): status, convergence, blocks, stream tables
  cpm          read a Control Panel export (.cpm): progress, loops, messages, error summary
  inp-check    check an input file (.inp) before opening it in Aspen Plus
  inp-find     how a block or paragraph is written, taken from your own runs (.his/.inp)
  comp-find    databank alias of a component (the COMPONENTS line), from the example models
  check        balances, charge, apparent/true basis and metrics from a .rep or a pasted stream table

Only the Python standard library is required (PDF text needs pypdf or PyMuPDF).
Nothing is uploaded: indexes live in ~/.proc-sim-agent (override with PROC_SIM_AGENT_HOME).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fwlib import bkp, check, cpm, docsdb, examples, helpdb, his, inp, madcap, rep, sims  # noqa: E402
from fwlib.common import (APP_TITLE, DEFAULT_EXAMPLES_GLOBS, DEFAULT_HELP_GLOBS, PRODUCTS,  # noqa: E402
                          config_path, data_home,
                          FileBusy, expand_globs, fts5_available, load_config, natural_key, os_path, print_json,
                          save_config, setup_io, side_file)

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
        ex = [p for p in expand_globs(DEFAULT_EXAMPLES_GLOBS) if Path(p).is_dir()]
        if ex and not a.examples:
            a.examples = [max(ex, key=natural_key)]  # newest release
            print(f"examples found: {a.examples[0]}")
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
    for f in a.examples or []:
        p = str(Path(f).expanduser().resolve())
        if not Path(p).exists():
            print(f"warning: examples folder not found: {p}")
        if p not in cfg["examples"]["folders"]:
            cfg["examples"]["folders"].append(p)
            changed = True
    for f in a.remove or []:
        forms = {f, str(Path(f).expanduser().resolve())}
        for sec in ("library", "simulations", "examples"):
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
    if (cfg["library"]["folders"] or cfg["examples"]["folders"]) and not docsdb.db_path().exists():
        print("Next: python fw.py docs-index   (repeat until it says 'complete')")
    if cfg["examples"]["folders"] and not examples.db_path().exists():
        print("Next: python fw.py examples-index   (repeat until it says 'complete')")


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
    for f in cfg["examples"]["folders"]:
        print(f"  examples     {f}")


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
    ex = examples.status()
    if ex["exists"]:
        print(f"  examples: {ex['models']} models ({'complete' if ex['complete'] else 'partial'})")
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
    # example folders are indexed too, so their PDF guides are searchable with docs-search
    folders = list(dict.fromkeys(cfg["library"]["folders"] + cfg["examples"]["folders"]))
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


def _pick(path: str, ext: str) -> Path:
    """A file, or the newest `ext` file of a folder. Engine working files (_xxxxxxx.*), recovery
    copies and sync-conflict copies are never picked."""
    p = Path(path).expanduser()
    if os.path.isdir(os_path(p)):
        every = sorted(p.glob("*" + ext))
        cands = [f for f in every if not side_file(f.name)]
        if not cands:
            others = f" (only {', '.join(f.name for f in every)}: working or conflict copies)" if every else ""
            _die(f"No {ext} file in {p}{others}")
        p = max(cands, key=lambda f: f.stat().st_mtime)
        print(f"(using {p.name})\n")
    if not os.path.exists(os_path(p)):
        _die(f"File not found: {p}")
    return p


def _pick_his(path: str) -> Path:
    return _pick(path, ".his")


def cmd_examples_index(a):
    cfg = load_config()
    roots = cfg["examples"]["folders"]
    if not roots:
        _die("No examples folder registered. Run:\n  python fw.py setup --examples \"<folder with example models>\"\n"
             "(the Aspen Plus examples are in the installation, e.g. ...\\Aspen Plus V15.0\\GUI\\Examples, or any "
             "copy of them)")
    res = examples.build(roots, max_seconds=a.max_seconds, rebuild=a.rebuild)
    print(json.dumps(res, ensure_ascii=False))
    if res["complete"]:
        print("complete")
        if not docsdb.db_path().exists():
            print("Tip: python fw.py docs-index also makes the PDF guides of the examples searchable.")
    else:
        print("INCOMPLETE - run the same command again to continue")
        sys.exit(EXIT_INCOMPLETE)


def _need_examples():
    if not examples.db_path().exists():
        _die("Examples not indexed yet. Run: python fw.py setup --examples \"<folder>\" then python fw.py examples-index")


def _csv_list(vals):
    out = []
    for v in vals or []:
        out += [x.strip() for x in v.split(",") if x.strip()]
    return out


def cmd_examples_search(a):
    _need_examples()
    res = examples.search(a.query or "", limit=a.limit, block=_csv_list(a.block), method=_csv_list(a.method),
                          component=_csv_list(a.component), has=_csv_list(a.has), folder=a.folder)
    if a.json:
        print_json(res)
        return
    print(examples.render_search(res))


def cmd_examples_show(a):
    _need_examples()
    d = examples.resolve(a.ref)
    if not d:
        _die(f"No example matches {a.ref!r}. Use examples-search first.", 1)
    if a.chemistry_inp:
        print(examples.chemistry_as_inp(d))
        return
    if a.section:
        print(examples.section_text(d, a.section, max_chars=a.max_chars))
        return
    if a.json:
        print_json(d)
        return
    print(examples.render_show(d))


def cmd_examples_list(a):
    _need_examples()
    rows = examples.folders()
    if a.json:
        print_json(rows)
        return
    for r in rows:
        print(f"{r['models']:4d}  {r['folder']}" + (f"   [{', '.join(r['features'])}]" if r["features"] else ""))


def cmd_comp_find(a):
    _need_examples()
    rows = examples.find_components(a.text, limit=a.limit)
    if a.json:
        print_json(rows)
        return
    print(examples.render_components(rows, a.text))


def cmd_inp_check(a):
    p = Path(a.file).expanduser()
    if not os.path.exists(os_path(p)):
        _die(f"File not found: {p}")
    if p.suffix.lower() == ".his":
        text = inp.from_his(his.parse(p), source=p.name)
    else:
        text = inp.read(p)
    res = inp.check(text)
    if a.json:
        print_json(res)
    else:
        print(inp.render(res, str(p)))
    if res["counts"]["error"]:
        sys.exit(1)


def _input_files(paths, max_files=400):
    """.his/.inp files under the given paths (newest first); default: the registered simulation folders."""
    roots = [Path(x).expanduser() for x in paths] if paths else [Path(f) for f in load_config()["simulations"]["folders"]]
    files = []
    for r in roots:
        if r.is_file():
            files.append(r)
        elif r.is_dir():
            files += [f for f in r.rglob("*") if f.suffix.lower() in (".his", ".inp") and f.is_file()]
    files = sorted(set(files), key=lambda f: f.stat().st_mtime, reverse=True)
    return files[:max_files], roots


def cmd_inp_find(a):
    files, roots = _input_files(a.paths)
    if not files:
        _die("No .his or .inp files to look in. Pass a folder or file, or register your simulation folders:\n"
             "  python fw.py setup --sims \"<folder with your model versions>\"")
    res = inp.find_examples(files, a.keyword, limit=a.limit)
    if a.json:
        print_json(res)
        return
    if not res:
        print(f"No {a.keyword.upper()} in {len(files)} input files. Find the syntax in the help "
              f"(help-search \"{a.keyword} input language\"), in an example (examples-search --block ...; "
              "examples-show <id> --section ...), or export a model that has it (File > Export > Input file).")
        return
    print(f"# {a.keyword.upper()} as written in your runs ({len(files)} input files searched)")
    for r in res:
        print(f"\n## {r['file']} (input line {r['line']})\n```\n{r['text']}\n```")


def cmd_check(a):
    p = _pick(a.file, ".rep")
    try:
        streams = check.load(p)
    except ValueError as e:
        _die(str(e), 1)
    if a.streams:
        want = {s.strip().upper() for s in a.streams.split(",")}
        streams = type(streams)((k, v) for k, v in streams.items() if k.upper() in want)
    aliases = {}
    src = a.model
    if not src and p.suffix.lower() == ".rep":  # a .his next to the report gives the component formulas
        his_files = sorted((f for f in p.parent.glob("*.his") if not side_file(f.name)),
                           key=lambda f: f.stat().st_mtime)
        src = str(his_files[-1]) if his_files else None
    if src:
        try:
            aliases = check.aliases_from(src)
            if not a.json:
                print(f"(component formulas from {Path(src).name})")
        except Exception as e:  # pragma: no cover - unreadable model file
            print(f"(could not read component formulas from {src}: {e})")
    overrides = {}
    for f in a.formula or []:
        if "=" in f:
            k, v = f.split("=", 1)
            overrides[k.strip()] = v.strip()
    metrics = []
    for m in a.metric or []:
        if "=" not in m:
            _die(f"--metric needs NAME=EXPRESSION, got {m!r}")
        k, v = m.split("=", 1)
        metrics.append((k.strip(), v.strip()))
    res = check.analyse(streams, elements=_csv_list(a.elements), aliases=aliases, overrides=overrides,
                        metrics=metrics)
    if a.json:
        print_json(res)
    else:
        print(check.render(res))


def cmd_his(a):
    p = _pick_his(a.file)
    d = his.parse(p)
    if a.inp:
        out = Path(a.inp).expanduser()
        if out.exists() and not a.force:
            _die(f"{out} exists; pass --force to overwrite")
        out.write_text(inp.from_his(d, source=p.name), encoding="utf-8")
        print(f"wrote {out} ({len(d['runs'][-1]['echo'])} lines; open it in Aspen Plus with File > Open > Input Files)")
        return
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
    if not os.path.exists(os_path(p)):
        _die(f"File not found: {p}")
    d = bkp.parse(p)
    if a.json:
        print_json(d)
    else:
        print(bkp.render_markdown(d))


def cmd_rep(a):
    p = _pick(a.file, ".rep")
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
    p = _pick(a.file, ".cpm")
    d = cpm.parse(p)
    if a.json:
        print_json({k: v for k, v in d.items() if k != "messages"})
        return
    print(cpm.render_markdown(d))


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="fw.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("setup", help="register folders")
    s.add_argument("--help-root", action="append", help="folder with the Aspen help (repeatable)")
    s.add_argument("--auto", action="store_true", help="look for installed help in the default AspenTech folders")
    s.add_argument("--library", action="append", help="folder with your PDFs/notes (repeatable)")
    s.add_argument("--sims", action="append", help="folder with simulation version folders (repeatable)")
    s.add_argument("--examples", action="append", help="folder with example models, e.g. the Aspen Plus examples "
                                                     "(repeatable)")
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

    s = sub.add_parser("examples-index", help="build/continue the example-model index")
    s.add_argument("--max-seconds", type=float, default=100)
    s.add_argument("--rebuild", action="store_true")
    s.set_defaults(fn=cmd_examples_index)

    s = sub.add_parser("examples-search", help="find example models")
    s.add_argument("query", nargs="?", default="", help="words (topic, process, component, method ...)")
    s.add_argument("--block", action="append", help="block type, e.g. RADFRAC (repeatable or comma-separated)")
    s.add_argument("--method", action="append", help="property method, e.g. ENRTL-RK")
    s.add_argument("--component", action="append", help="component ID or databank name, e.g. CO2")
    s.add_argument("--has", action="append", help="feature: " + ", ".join(examples.FEATURE_WORDS))
    s.add_argument("--folder", help="folder name fragment, e.g. 'Carbon Capture'")
    s.add_argument("-n", "--limit", type=int, default=10)
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_examples_search)

    s = sub.add_parser("examples-show", help="details of one example model")
    s.add_argument("ref", help="id from examples-search, or a name/path fragment")
    s.add_argument("--section", help="print the raw input sections whose name contains this, e.g. CHEMISTRY, "
                                     "'BLOCK RADFRAC', 'CALCULATOR', 'PROPERTIES MAIN'")
    s.add_argument("--chemistry-inp", action="store_true", help="print the example's CHEMISTRY as input language")
    s.add_argument("--max-chars", type=int, default=8000)
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_examples_show)

    s = sub.add_parser("examples-list", help="example folders and what they contain")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_examples_list)

    s = sub.add_parser("comp-find", help="databank aliases of a component, as used in the example models")
    s.add_argument("text", help="component ID, formula/alias or databank name, e.g. MEA, C2H7NO, MONOETHANOLAMINE")
    s.add_argument("-n", "--limit", type=int, default=15)
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_comp_find)

    s = sub.add_parser("inp-check", help="check an input file (.inp, or the input of a .his)")
    s.add_argument("file")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_inp_check)

    s = sub.add_parser("inp-find", help="examples of a block model, paragraph or statement from your own runs")
    s.add_argument("keyword", help="e.g. RADFRAC, HEATX, DESIGN-SPEC, CHEMISTRY, COL-SPECS")
    s.add_argument("paths", nargs="*", help="files or folders (default: the registered simulation folders)")
    s.add_argument("-n", "--limit", type=int, default=3)
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_inp_find)

    s = sub.add_parser("check", help="balances and metrics from a .rep or a pasted stream table")
    s.add_argument("file", help=".rep file, a folder (newest .rep), or a text file with a copied stream table")
    s.add_argument("--elements", action="append", help="element balances, e.g. C,NA,CL")
    s.add_argument("--model", help=".his, .inp or .bkp to read component formulas from (default: newest .his "
                                   "next to a .rep)")
    s.add_argument("--formula", action="append", help="override a formula, e.g. MEA=C2H7NO (repeatable)")
    s.add_argument("--metric", action="append", help="NAME=EXPRESSION, e.g. "
                                                     "\"recovery=flow(CO2-GAS, CO2)/elem(FEED, C)\" (repeatable)")
    s.add_argument("--streams", help="only these streams (comma-separated)")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_check)

    s = sub.add_parser("sim-scan", help="summarise simulation folders")
    s.add_argument("paths", nargs="*")
    s.add_argument("--depth", type=int, default=5)
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_sim_scan)

    s = sub.add_parser("his", help="digest of a .his file (or the newest .his in a folder)")
    s.add_argument("file")
    s.add_argument("--fortran", action="store_true", help="include calculator Fortran")
    s.add_argument("--echo", action="store_true", help="print the input echo (.inp text) only")
    s.add_argument("--inp", help="write the input of the last run to this .inp file")
    s.add_argument("--force", action="store_true", help="overwrite the --inp file if it exists")
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

    return ap


def commands() -> list:
    """Names of every subcommand (for the -h smoke tests)."""
    ap = build_parser()
    action = next(x for x in ap._actions if isinstance(x, argparse._SubParsersAction))
    return list(action.choices)


def main(argv=None):
    setup_io()
    a = build_parser().parse_args(argv)
    try:
        a.fn(a)
    except FileBusy as e:
        _die(str(e), 2)
    except BrokenPipeError:  # output piped into head/less that closed early
        try:
            sys.stdout = open(os.devnull, "w")
        except OSError:
            pass
        sys.exit(0)


if __name__ == "__main__":
    main()
