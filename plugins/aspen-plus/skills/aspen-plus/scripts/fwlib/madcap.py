"""Read a MadCap Flare WebHelp tree (the format of Aspen Plus, HYSYS and Adsorption help).

Layout (per help system and per "book" = subsystem):
  <root>/<name>.mcwebhelp            root manifest; <Subsystems><Url Source=... TocPath=.../>
  <book>/Data/HelpSystem.xml          same manifest for the book (also lists nested subsystems)
  <book>/Data/Tocs/<name>.js (+ _ChunkN.js)  table of contents
  <book>/Data/SearchTopic_ChunkN.js   catalogue: url, title, abstract per topic
  <book>/Data/Alias.xml               context-sensitive help ids -> topic file
  <book>/Content/**.htm               the topics (data-mc-toc-path attribute = breadcrumb)
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from . import htmltext, jslit
from .common import PRODUCTS


@dataclass
class Book:
    name: str
    dir: Path
    rel: str                 # posix path of the book folder relative to the help root ('' for root)
    toc_path: str            # where the book is merged in the master TOC, 'A|B|C'
    order: int
    manifest: Optional[Path] = None
    attrs: Dict[str, str] = field(default_factory=dict)

    @property
    def build_time(self) -> str:
        return self.attrs.get("BuildTime", "")


# ---------------------------------------------------------------------------
# help root / product / version
# ---------------------------------------------------------------------------
def find_help_root(path) -> Optional[Path]:
    """Return the folder holding the root *.mcwebhelp file (searches up to 3 levels down)."""
    p = Path(path).expanduser()
    if p.is_file() and p.suffix.lower() == ".mcwebhelp":
        return p.parent
    if not p.is_dir():
        return None
    known = {f for spec in PRODUCTS.values() for f in spec["root_files"]}
    for depth in range(0, 4):
        pattern = "/".join(["*"] * depth + ["*.mcwebhelp"]) if depth else "*.mcwebhelp"
        hits = [h for h in p.glob(pattern) if "Subsystems" not in h.relative_to(p).parts]
        if hits:
            hits.sort(key=lambda h: (h.name.lower() not in known, len(h.parts)))
            return hits[0].parent
    return None


def root_manifest(root: Path) -> Optional[Path]:
    files = sorted(root.glob("*.mcwebhelp"))
    if not files:
        hs = root / "Data" / "HelpSystem.xml"
        return hs if hs.exists() else None
    known = {f for spec in PRODUCTS.values() for f in spec["root_files"]}
    files.sort(key=lambda h: h.name.lower() not in known)
    return files[0]


def detect_product(root: Path):
    man = root_manifest(root)
    name = man.name.lower() if man else ""
    for key, spec in PRODUCTS.items():
        if name in spec["root_files"]:
            return key, spec["title"]
    stem = man.stem if man else root.name
    return re.sub(r"[^a-z0-9]+", "-", stem.lower()).strip("-") or "help", stem


_VER_IN_PATH = re.compile(r"\bV(\d+(?:\.\d+)*)\b", re.I)
_VER_IN_TOC = re.compile(r"What.s New in .*?V(\d+(?:\.\d+)*)", re.I)


def detect_version(root: Path) -> str:
    for part in reversed(root.resolve().parts):
        m = _VER_IN_PATH.search(part)
        if m:
            return "V" + m.group(1)
    # fall back to the newest "What's New in ... Vxx" entry of the master TOC
    best = None
    for f in sorted((root / "Data" / "Tocs").glob("*.js")):
        try:
            txt = f.read_text(encoding="utf-8", errors="replace").replace("\\u0027", "'")
        except OSError:
            continue
        for m in _VER_IN_TOC.finditer(txt):
            v = tuple(int(x) for x in m.group(1).split("."))
            if best is None or v > best:
                best = v
    return "V" + ".".join(str(x) for x in best) if best else "unknown"


# ---------------------------------------------------------------------------
# books
# ---------------------------------------------------------------------------
def _read_manifest(path: Path):
    """Return (attrs, [(source, tocpath), ...]) from a .mcwebhelp / HelpSystem.xml file."""
    try:
        tree = ET.parse(str(path))
    except (ET.ParseError, OSError):
        txt = path.read_text(encoding="utf-8", errors="replace")
        subs = re.findall(r'<Url\s+Source="([^"]+)"\s+TocPath="([^"]*)"', txt)
        m = re.search(r"<WebHelpSystem([^>]*)>", txt)
        attrs = dict(re.findall(r'(\w+)="([^"]*)"', m.group(1))) if m else {}
        return attrs, subs
    root = tree.getroot()
    attrs = dict(root.attrib)
    subs = []
    for url in root.iter("Url"):
        src = url.attrib.get("Source")
        if src:
            subs.append((src, url.attrib.get("TocPath", "")))
    return attrs, subs


def list_books(root: Path) -> List[Book]:
    root = Path(root)
    man = root_manifest(root)
    attrs, subs = _read_manifest(man) if man else ({}, [])
    books = [Book(name=(man.stem if man and man.suffix == ".mcwebhelp" else root.name), dir=root, rel="",
                  toc_path="", order=0, manifest=man, attrs=attrs)]
    seen = {root.resolve()}
    queue = [(root, s, t) for s, t in subs]
    while queue:
        base, src, toc = queue.pop(0)
        mpath = (base / src).resolve()
        bdir = mpath.parent
        if bdir in seen or not bdir.exists():
            continue
        seen.add(bdir)
        battrs, bsubs = ({}, [])
        if mpath.exists():
            battrs, bsubs = _read_manifest(mpath)
        elif (bdir / "Data" / "HelpSystem.xml").exists():
            battrs, bsubs = _read_manifest(bdir / "Data" / "HelpSystem.xml")
        rel = bdir.relative_to(root.resolve()).as_posix()
        books.append(Book(name=mpath.stem, dir=bdir, rel=rel, toc_path=toc, order=len(books),
                          manifest=mpath if mpath.exists() else None, attrs=battrs))
        queue.extend((bdir, s, t) for s, t in bsubs)
    return books


def book_signature(book: Book) -> str:
    """Cheap change detector: build time + size of the search url table."""
    sizes = []
    for f in sorted((book.dir / "Data").glob("SearchUrl_Chunk*.js")):
        try:
            sizes.append(str(f.stat().st_size))
        except OSError:
            pass
    return f"{book.build_time}|{'/'.join(sizes)}"


def book_topic_files(book: Book, root: Path) -> List[str]:
    content = book.dir / "Content"
    if not content.is_dir():
        return []
    out = []
    for f in content.rglob("*"):
        if f.suffix.lower() in (".htm", ".html") and f.is_file():
            out.append(f.resolve().relative_to(Path(root).resolve()).as_posix())
    out.sort()
    return out


def book_search_catalog(book: Book, root: Path) -> Dict[str, dict]:
    """Map topic rel path -> {'title', 'abstract'} from SearchTopic_Chunk*.js."""
    out: Dict[str, dict] = {}
    data_dir = book.dir / "Data"
    for f in sorted(data_dir.glob("SearchTopic_Chunk*.js")):
        try:
            d = jslit.parse_define(f.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        for v in d.values():
            if not isinstance(v, dict) or "u" not in v:
                continue
            rel = _rel_from(book, root, data_dir, v["u"])
            if rel:
                out[rel] = {"title": v.get("t", ""), "abstract": v.get("a", "")}
    return out


def _rel_from(book: Book, root: Path, base_dir: Path, url: str) -> Optional[str]:
    url = url.split("#", 1)[0]
    try:
        p = (base_dir / url).resolve()
        return p.relative_to(Path(root).resolve()).as_posix()
    except (ValueError, OSError):
        return None


def book_aliases(book: Book, root: Path):
    """Context-sensitive help map: [(name, rel, resolved_id)]."""
    f = book.dir / "Data" / "Alias.xml"
    if not f.exists():
        return []
    out = []
    try:
        tree = ET.parse(str(f))
        maps = [(m.attrib.get("Name", ""), m.attrib.get("Link", ""), m.attrib.get("ResolvedId", ""))
                for m in tree.getroot().iter("Map")]
    except (ET.ParseError, OSError):
        txt = f.read_text(encoding="utf-8", errors="replace")
        maps = re.findall(r'<Map\s+Name="([^"]*)"\s+Link="([^"]*)"(?:\s+ResolvedId="([^"]*)")?', txt)
    for name, link, rid in maps:
        if not name or not link:
            continue
        rel = _rel_from(book, root, book.dir / "Content", link)
        if rel:
            out.append((name, rel, rid or ""))
    return out


# ---------------------------------------------------------------------------
# table of contents
# ---------------------------------------------------------------------------
def _load_toc(book: Book):
    """Return (tree, entries) where entries[i] = (title, url or None)."""
    toc_attr = book.attrs.get("Toc") or f"Data/Tocs/{book.name}.js"
    main = book.dir / toc_attr
    if not main.exists():
        cands = sorted((book.dir / "Data" / "Tocs").glob("*.js"))
        cands = [c for c in cands if "_Chunk" not in c.name]
        if not cands:
            return None, {}
        main = cands[0]
    try:
        d = jslit.parse_define(main.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None, {}
    entries: Dict[int, tuple] = {}
    prefix = d.get("prefix") or (main.stem + "_Chunk")
    for k in range(int(d.get("numchunks") or 0)):
        cf = main.parent / f"{prefix}{k}.js"
        if not cf.exists():
            continue
        try:
            chunk = jslit.parse_define(cf.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        for url, info in chunk.items():
            ids = info.get("i", []) if isinstance(info, dict) else []
            titles = info.get("t", []) if isinstance(info, dict) else []
            for j, idx in enumerate(ids):
                title = titles[j] if j < len(titles) else ""
                entries[int(idx)] = (title, None if url == "___" else url)
    return d.get("tree"), entries


def book_toc(book: Book, root: Path, subsystems: Optional[List[Book]] = None) -> List[dict]:
    """Nested [{'title','rel','book','children'}] for one book.

    In the master TOC, nodes with r:1/m:k are where subsystem k is merged in;
    they come back as {'book': <name>} placeholders.
    """
    tree, entries = _load_toc(book)
    if not tree:
        return []

    def walk(nodes):
        out = []
        for n in nodes or []:
            i = n.get("i")
            title, url = entries.get(i, ("", None))
            item = {"title": title, "rel": None, "book": None, "children": []}
            if n.get("r") and subsystems is not None and isinstance(n.get("m"), int):
                k = n["m"]
                if 0 <= k < len(subsystems):
                    item["book"] = subsystems[k].name
                    item["title"] = item["title"] if not title.endswith((".hhc", ".flprj")) and ".chm::" not in title else ""
            elif url and not url.endswith(".flprj"):
                item["rel"] = _rel_from(book, root, book.dir, url.lstrip("/"))
            item["children"] = walk(n.get("n"))
            out.append(item)
        return out

    return walk(tree.get("n"))


def book_title(book: Book, root: Path) -> str:
    try:
        toc = book_toc(book, root)
    except Exception:
        toc = []
    tops = [n["title"] for n in toc if n.get("title")]
    if not tops:
        return book.name
    if len(tops) <= 2:
        return " / ".join(tops)
    return f"{tops[0]} / {tops[1]} / ... ({len(tops)} sections)"


# ---------------------------------------------------------------------------
# topics
# ---------------------------------------------------------------------------
def parse_topic(root: Path, rel: str, links: bool = True, equations: bool = True) -> dict:
    path = Path(root) / rel
    raw = path.read_bytes()
    try:
        html = raw.decode("utf-8")
    except UnicodeDecodeError:
        html = raw.decode("cp1252", errors="replace")
    eq = (lambda r: htmltext.svg_equation_text(Path(root) / r)) if equations else None
    return htmltext.convert(html, topic_rel=rel, links=links, equation_text=eq)
