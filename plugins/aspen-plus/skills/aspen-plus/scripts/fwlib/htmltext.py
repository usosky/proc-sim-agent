"""Convert MadCap Flare topic HTML into compact Markdown (for reading) or plain text (for indexing).

Keeps what matters to an engineer reading help: headings, paragraphs, bullet and
numbered lists, tables (as Markdown tables), notes, link targets, and a marker
where an equation image sits (with an approximate text rendering of the MathJax
SVG when the file is available).
"""
from __future__ import annotations

import posixpath
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Callable, List, Optional

_WS = re.compile(r"[ \t\r\n\f\v    ]+")
_SKIP = {"head", "script", "style", "noscript", "object", "iframe", "svg", "button"}
_PARA = {"p", "div", "dt", "dd", "blockquote", "section", "article", "caption", "figure",
         "figcaption", "header", "footer", "nav", "aside", "main", "form", "fieldset"}
_HEAD = {"h1": 1, "h2": 2, "h3": 3, "h4": 4, "h5": 5, "h6": 6}
_DECOR_IMG = re.compile(r"(bullet|plus\.png|minus\.png|transparent\.gif|spacer|arrow)", re.I)


def resolve_href(topic_rel: str, href: str) -> str:
    """Resolve a link relative to the topic file; returns a help-root-relative posix path or URL."""
    href = href.strip()
    if re.match(r"^[a-z]+:", href, re.I):  # http:, mailto:, javascript:
        return href
    href = href.split("#", 1)[0].split("?", 1)[0]
    if not href:
        return ""
    base = posixpath.dirname(topic_rel)
    return posixpath.normpath(posixpath.join(base, href.replace("\\", "/")))


class _Table:
    def __init__(self):
        self.rows: List[List[str]] = []
        self.header_rows = 0
        self.row: Optional[List[str]] = None
        self.cell: Optional[List[str]] = None
        self.in_thead = False
        self.row_has_th = False


class TopicHTML(HTMLParser):
    def __init__(self, topic_rel: str = "", links: bool = True,
                 equation_text: Optional[Callable[[str], str]] = None):
        super().__init__(convert_charrefs=True)
        self.topic_rel = topic_rel
        self.want_links = links
        self.equation_text = equation_text
        self.title = ""
        self.toc_path = ""
        self.blocks: List[str] = []
        self.inline: List[str] = []
        self.skip = 0
        self.in_title = False
        self.lists: List[list] = []          # stack of [kind, counter]
        self.li_prefix: Optional[str] = None
        self.heading = 0
        self.pre = 0
        self.tables: List[_Table] = []
        self.nested_table = 0
        self.a_href: Optional[str] = None
        self.a_buf: List[str] = []
        self.links: List[str] = []
        self.equations: List[str] = []
        self.headings: List[str] = []

    # ---- sinks -------------------------------------------------------------
    def _sink(self) -> List[str]:
        if self.a_href is not None:
            return self.a_buf
        if self.tables and self.tables[-1].cell is not None:
            return self.tables[-1].cell
        return self.inline

    def _emit(self, text: str):
        if text:
            self._sink().append(text)

    def _flush(self):
        """Close the current paragraph / list item / heading."""
        if self.tables and self.tables[-1].cell is not None:
            self._emit(" ")
            return
        text = "".join(self.inline)
        self.inline = []
        text = text if self.pre else _WS.sub(" ", text).strip()
        if not text:
            return
        if self.heading:
            self.headings.append(text)
            text = "#" * min(self.heading + 1, 6) + " " + text
        elif self.li_prefix is not None:
            text = self.li_prefix + text
            self.li_prefix = "  " * len(self.lists) + "  "  # continuation lines of the same item
        self.blocks.append(text)

    # ---- parser callbacks --------------------------------------------------
    def handle_starttag(self, tag, attrs):
        a = {k: (v or "") for k, v in attrs}
        if tag == "html":
            self.toc_path = a.get("data-mc-toc-path", "")
            return
        if tag == "title":
            self.in_title = True
            return
        if tag in _SKIP:
            self.skip += 1
            return
        if self.skip:
            return
        if tag == "table":
            if self.tables and self.tables[-1].cell is not None:
                self.nested_table += 1
                return
            self._flush()
            self.tables.append(_Table())
            return
        if self.tables and self.nested_table:
            if tag in ("td", "th", "tr", "p", "li", "br", "div"):
                self._emit(" ")
            return
        if self.tables:
            t = self.tables[-1]
            if t.cell is not None and tag not in ("td", "th", "tr", "a", "img"):
                # inside a cell: keep text flowing, mark list items, ignore layout state
                if tag == "li":
                    self._emit(" - ")
                elif tag in _PARA or tag in _HEAD or tag in ("br", "ul", "ol", "pre", "hr"):
                    self._emit(" ")
                return
            if tag == "thead":
                t.in_thead = True
                return
            if tag == "tr":
                t.row = []
                t.row_has_th = False
                return
            if tag in ("td", "th"):
                if t.row is None:
                    t.row = []
                t.cell = []
                if tag == "th":
                    t.row_has_th = True
                return
        if tag in _HEAD:
            self._flush()
            self.heading = _HEAD[tag]
            return
        if tag in ("ul", "ol"):
            self._flush()
            self.lists.append([tag, 0])
            return
        if tag == "li":
            self._flush()
            depth = max(len(self.lists), 1)
            if self.lists and self.lists[-1][0] == "ol":
                self.lists[-1][1] += 1
                mark = f"{self.lists[-1][1]}. "
            else:
                mark = "- "
            self.li_prefix = "  " * (depth - 1) + mark
            return
        if tag == "pre":
            self._flush()
            self.pre += 1
            return
        if tag in _PARA:
            self._flush()
            return
        if tag == "br":
            if self.tables and self.tables[-1].cell is not None:
                self._emit(" ")
            elif self.pre:
                self._emit("\n")
            else:
                self._flush()
            return
        if tag == "hr":
            self._flush()
            return
        if tag == "a":
            href = a.get("href", "")
            if href and not href.startswith("#") and not href.lower().startswith("javascript"):
                self.a_href = resolve_href(self.topic_rel, href)
                self.a_buf = []
            return
        if tag == "img":
            self._img(a)
            return

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False
            return
        if tag in _SKIP:
            self.skip = max(0, self.skip - 1)
            return
        if self.skip:
            return
        if tag == "table":
            if self.nested_table:
                self.nested_table -= 1
                return
            if self.tables:
                t = self.tables.pop()
                self._close_row(t)
                rendered = _render_table(t)
                if rendered:
                    if self.tables and self.tables[-1].cell is not None:
                        self._emit(" " + rendered.replace("\n", " "))
                    else:
                        self.blocks.append(rendered)
            return
        if self.tables and self.nested_table:
            return
        if self.tables:
            t = self.tables[-1]
            if t.cell is not None and tag not in ("td", "th", "tr", "a"):
                if tag in _PARA or tag in _HEAD or tag in ("li", "ul", "ol", "pre"):
                    self._emit(" ")
                return
            if tag == "thead":
                t.in_thead = False
                return
            if tag in ("td", "th"):
                if t.cell is not None and t.row is not None:
                    t.row.append(_WS.sub(" ", "".join(t.cell)).strip())
                t.cell = None
                return
            if tag == "tr":
                self._close_row(t)
                return
        if tag in _HEAD:
            self._flush()
            self.heading = 0
            return
        if tag in ("ul", "ol"):
            self._flush()
            if self.lists:
                self.lists.pop()
            self.li_prefix = None
            return
        if tag == "li":
            self._flush()
            self.li_prefix = None
            return
        if tag == "pre":
            self._flush()
            self.pre = max(0, self.pre - 1)
            return
        if tag in _PARA:
            self._flush()
            return
        if tag == "a" and self.a_href is not None:
            target = self.a_href
            text = _WS.sub(" ", "".join(self.a_buf)).strip()
            self.a_href = None
            self.a_buf = []
            if target and not target.startswith(("http:", "https:", "mailto:")):
                self.links.append(target)
            if text:
                if self.want_links and target:
                    self._emit(f"[{text}]({target})")
                else:
                    self._emit(text)
            return

    def handle_data(self, data):
        if self.in_title:
            self.title += data
            return
        if self.skip:
            return
        if self.pre:
            self._emit(data)
        else:
            self._emit(_WS.sub(" ", data))

    # ---- helpers -----------------------------------------------------------
    def _img(self, a):
        src = a.get("src", "")
        alt = (a.get("alt") or "").strip()
        cls = a.get("class", "")
        rel = resolve_href(self.topic_rel, src) if src else ""
        if "Equation" in src or "_MCEquation" in cls or src.lower().endswith(".svg") and "GeneratedImages" in src:
            self.equations.append(rel)
            approx = ""
            if self.equation_text and rel:
                try:
                    approx = self.equation_text(rel)
                except Exception:
                    approx = ""
            self._emit(f" [equation: {approx} (approx.)] " if approx else " [equation image] ")
            return
        if alt and not _DECOR_IMG.search(src):
            self._emit(f" [image: {alt}] ")

    @staticmethod
    def _close_row(t: _Table):
        if t.row is not None:
            if t.cell is not None:
                t.row.append(_WS.sub(" ", "".join(t.cell)).strip())
                t.cell = None
            if any(c for c in t.row):
                t.rows.append(t.row)
                if (t.in_thead or t.row_has_th) and len(t.rows) == t.header_rows + 1:
                    t.header_rows += 1
            t.row = None

    def finish(self) -> str:
        self._flush()
        while self.tables:  # unclosed tables
            t = self.tables.pop()
            self._close_row(t)
            r = _render_table(t)
            if r:
                self.blocks.append(r)
        out = []
        for b in self.blocks:
            if out and (b.startswith("#") or out[-1].startswith("#") or b.startswith("|") != out[-1].startswith("|")):
                out.append("")
            out.append(b)
        text = "\n".join(out)
        return re.sub(r"\n{3,}", "\n\n", text).strip()


def _render_table(t: _Table) -> str:
    rows = [r for r in t.rows if any(c.strip() for c in r)]
    if not rows:
        return ""
    width = max(len(r) for r in rows)
    if width == 1:  # single-column layout tables read better as plain lines
        return "\n".join(r[0] for r in rows if r[0])
    norm = [[c.replace("|", "/") for c in r] + [""] * (width - len(r)) for r in rows]
    head = norm[0]
    body = norm[1:]
    lines = ["| " + " | ".join(head) + " |", "|" + "---|" * width]
    lines += ["| " + " | ".join(r) + " |" for r in body]
    return "\n".join(lines)


def convert(html: str, topic_rel: str = "", links: bool = True,
            equation_text: Optional[Callable[[str], str]] = None) -> dict:
    """Return dict(title, toc_path, text, links, equations, headings)."""
    p = TopicHTML(topic_rel=topic_rel, links=links, equation_text=equation_text)
    try:
        p.feed(html)
        p.close()
    except Exception:  # malformed HTML: keep what we have
        pass
    text = p.finish()
    return {
        "title": _WS.sub(" ", p.title).strip(),
        "toc_path": p.toc_path,
        "text": text,
        "links": list(dict.fromkeys(p.links)),
        "equations": p.equations,
        "headings": p.headings,
    }


# ---- MathJax SVG -> approximate text ----------------------------------------
_GLYPH = re.compile(r'href="#MJ[A-Z0-9]*-([0-9A-F]+)"')


def svg_equation_text(svg_path: Path, max_len: int = 160) -> str:
    """Approximate the symbols of a MathJax SVG equation, in drawing order.

    Fractions, sub/superscripts and radicals lose their layout, so the result is
    only a hint (e.g. 'X=G(X)'); the exact form is in the help topic itself.
    """
    try:
        s = Path(svg_path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    body = s.split("</defs>", 1)[-1]
    chars = []
    for hx in _GLYPH.findall(body):
        try:
            ch = chr(int(hx, 16))
        except ValueError:
            continue
        chars.append(ch)
    text = "".join(chars)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_len]
