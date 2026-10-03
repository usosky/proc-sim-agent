#!/usr/bin/env python3
"""Make shareable copies of Aspen Plus files by removing what identifies the author's setup.

Removes:
  - licence holder:   "THIS COPY OF ASPEN PLUS LICENSED TO <org>"        (.his .rep)
  - install / run folders: "LOCATED IN: <path>", ";Directory <path> ...",
    "Filename <path>", "INSTALLATION: <site>"                           (.his .rep .inp .bkp)
  - Windows user and computer name in the backup's run status:
    DSET RUN-STATUS VERS ( "39.0" "WIN-X64" "" "<user>" "<computer>" )  (.bkp)
Then lists any other line that still looks like a local path or an e-mail address, for you to
check by hand (it does not change those lines).

The files are read and written byte for byte (latin-1), keeping line endings; in .bkp files each
changed line keeps its length (padded with spaces), so Aspen reads the copy like the original.
Open the scrubbed .bkp in Aspen Plus once before publishing it.

Usage:
  python tools/scrub_aspen_files.py <files or folders> --out <folder>   write scrubbed copies
  python tools/scrub_aspen_files.py <files or folders> --check          exit 1 if anything is left
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import List, Tuple

EXTS = {".bkp", ".his", ".rep", ".cpm", ".inp", ".sum"}
REMOVED = "[removed]"

LICENSE_RX = re.compile(r"(THIS COPY OF ASPEN PLUS LICENSED TO)([^\r\n]*)")
LOCATED_RX = re.compile(r"(LOCATED IN:)([ \t]*)([^\r\n]*\S)")
# the value sits right after the label; a blank value is followed by the right-hand column (the time)
INSTALL_RX = re.compile(r"(INSTALLATION:)([ \t]{1,10})(\S(?:[^\r\n]*?\S)?)(?=[ \t]{3,}\S|[ \t]*$)")
DIR_RX = re.compile(r";Directory\b")
# a Windows path inside ;Directory / Filename lines: runs to two spaces, a quote, or the end
PATH_IN_DIR_RX = re.compile(r"((?:;Directory|Filename)[ \t]+)(?=\S)(?!Runid\b|Filename\b)([^\r\n\"]*?)(?=[ \t]{2,}|\"|[ \t]*$)")
VERS_RX = re.compile(r'(DSET RUN-STATUS VERS\s+@VERS\s*\(\s*"[^"]*"\s*"[^"]*"\s*"[^"]*"\s*)"[^"]*"(\s*)"[^"]*"')
# the same record wrapped over several 80-column lines (long user or computer names)
VERS_ML_RX = re.compile(r'DSET\s+RUN-STATUS\s+VERS\s+@VERS\s*\(\s*"[^"]*"\s*"[^"]*"\s*"[^"]*"\s*"([^"]*)"\s*"([^"]*)"')
SUSPECT_RX = re.compile(r"(?<![A-Za-z0-9])[A-Za-z]:\\[A-Za-z0-9 _.$-]{2,}|\\\\[A-Za-z0-9_.-]{2,}\\|"
                        r"\\Users\\|/home/|/Users/|[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
ENCODED_LINE_RX = re.compile(r'^"[!-~]{60,}"\s*$')  # graphics/structure data blocks in .bkp


def _split_eol(line: str) -> Tuple[str, str]:
    body = line.rstrip("\r\n")
    return body, line[len(body):]


def _scrub_line(body: str, ext: str, token: str) -> str:
    new = LICENSE_RX.sub(lambda m: m.group(1) + (" " + token if m.group(2).strip() else m.group(2)), body)
    new = LOCATED_RX.sub(lambda m: m.group(1) + " " + token, new)
    new = INSTALL_RX.sub(lambda m: m.group(1) + m.group(2) + token, new)
    if DIR_RX.search(new) or "Filename" in new:
        new = PATH_IN_DIR_RX.sub(lambda m: m.group(1) + (token if m.group(2).strip() else m.group(2)), new)
    if ext == ".bkp" and "RUN-STATUS VERS" in new:
        new = VERS_RX.sub(lambda m: m.group(1) + '""' + m.group(2) + '""', new)
    return new


def scrub_text(text: str, ext: str) -> Tuple[str, List[str]]:
    """Return (scrubbed text, list of 'line N: what changed')."""
    out, changes = [], []
    keep_len = ext == ".bkp"   # backup files are card images: never make a line longer
    for n, line in enumerate(text.splitlines(keepends=True), 1):
        body, eol = _split_eol(line)
        new = _scrub_line(body, ext, REMOVED)
        if new != body:
            if keep_len and len(new) > len(body):
                new = _scrub_line(body, ext, "")
            if keep_len:
                new = new.ljust(len(body))
            changes.append(f"line {n}: {body.strip()[:60]!r} -> {new.strip()[:60]!r}")
        out.append(new + eol)
    text_out = "".join(out)
    if ext == ".bkp":
        text_out = _scrub_wrapped_vers(text_out, changes)
    return text_out, changes


def _scrub_wrapped_vers(text: str, changes: List[str]) -> str:
    """Blank user and computer name in a VERS record that wraps over lines, keeping every line length."""
    for m in reversed(list(VERS_ML_RX.finditer(text))):
        if not (m.group(1) or m.group(2)):
            continue
        ls = text.rfind("\n", 0, m.start()) + 1
        le = text.find("\n", m.end())
        le = len(text) if le == -1 else le + 1
        old = text[ls:le]
        a1, b1, a2, b2 = m.start(1) - ls, m.end(1) - ls, m.start(2) - ls, m.end(2) - ls
        new = old[:a1] + old[b1:a2] + old[b2:]
        fixed = []
        for o, n in zip(old.splitlines(keepends=True), new.splitlines(keepends=True)):
            ob, _ = _split_eol(o)
            nb, ne = _split_eol(n)
            fixed.append(nb.ljust(len(ob)) + ne)
        text = text[:ls] + "".join(fixed) + text[le:]
        line_no = text.count("\n", 0, ls) + 1
        changes.append(f"lines {line_no}-{line_no + max(old.count(chr(10)) - 1, 0)}: user/computer name in a wrapped "
                       "RUN-STATUS VERS record -> blank")
    return text


def suspects(text: str) -> List[str]:
    found = []
    for n, line in enumerate(text.splitlines(), 1):
        if ENCODED_LINE_RX.match(line):
            continue
        if REMOVED in line and not SUSPECT_RX.search(line.replace(REMOVED, "")):
            continue
        m = SUSPECT_RX.search(line)
        if m:
            found.append(f"line {n}: ...{line.strip()[:100]}")
    return found


def iter_files(paths) -> List[Tuple[Path, Path]]:
    """(file, base) pairs; copies keep their path relative to base."""
    files = []
    for p in map(Path, paths):
        if p.is_dir():
            files += [(f, p) for f in sorted(p.rglob("*")) if f.is_file() and f.suffix.lower() in EXTS]
        elif p.is_file():
            files.append((p, p.parent))
        else:
            print(f"not found: {p}", file=sys.stderr)
    return files


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="+")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--out", help="folder for the scrubbed copies (created if needed)")
    g.add_argument("--check", action="store_true", help="only report; exit 1 if something would change or looks private")
    a = ap.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):  # Windows consoles (cp1252) must not crash on odd bytes
        try:
            stream.reconfigure(errors="backslashreplace")
        except (AttributeError, ValueError):
            pass

    files = iter_files(a.paths)
    if not files:
        print("no Aspen files found", file=sys.stderr)
        return 2
    problems = 0
    for f, base in files:
        raw = f.read_bytes()
        text = raw.decode("latin-1")
        new, changes = scrub_text(text, f.suffix.lower())
        left = suspects(new)
        print(f"{f}: {len(changes)} change(s), {len(left)} line(s) to check by hand")
        for c in changes:
            print("   " + c)
        for s in left:
            print("   CHECK " + s)
        if a.check:
            problems += len(changes) + len(left)
            continue
        target = Path(a.out) / f.relative_to(base)
        if target.resolve() == f.resolve():
            print(f"refusing to overwrite the original: {f}", file=sys.stderr)
            return 2
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(new.encode("latin-1"))
    if a.check:
        return 1 if problems else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
