"""Tolerant parser for the JavaScript object literals MadCap Flare writes.

Flare stores its table of contents and search catalogue as files like
``define({numchunks:1,prefix:'x_Chunk',tree:{n:[{i:0,c:0}]}})``: JavaScript,
not JSON (unquoted keys, single-quoted strings, \\uXXXX escapes). This module
turns them into Python dicts and lists without executing anything.
"""
from __future__ import annotations

import re

_KEY = re.compile(r"[A-Za-z0-9_$]+")
_ATOM = re.compile(r"[^,\]\}\s:]+")
_STR_RUN = {q: re.compile(r"[^\\" + q + r"]+") for q in ("'", '"')}
_ESC = {"n": "\n", "t": "\t", "r": "\r", "b": "\b", "f": "\f", "/": "/"}


class JSLiteralError(ValueError):
    pass


class _Parser:
    __slots__ = ("s", "i", "n")

    def __init__(self, s: str):
        self.s, self.i, self.n = s, 0, len(s)

    def _ws(self):
        s, i, n = self.s, self.i, self.n
        while i < n and s[i] in " \t\r\n":
            i += 1
        self.i = i

    def value(self):
        self._ws()
        if self.i >= self.n:
            raise JSLiteralError("unexpected end of input")
        c = self.s[self.i]
        if c == "{":
            return self._obj()
        if c == "[":
            return self._arr()
        if c in "'\"":
            return self._str()
        return self._atom()

    def _obj(self):
        self.i += 1
        out = {}
        while True:
            self._ws()
            c = self.s[self.i]
            if c == "}":
                self.i += 1
                return out
            if c == ",":
                self.i += 1
                continue
            key = self._str() if c in "'\"" else self._key()
            self._ws()
            if self.s[self.i] != ":":
                raise JSLiteralError(f"expected ':' at {self.i}")
            self.i += 1
            out[key] = self.value()

    def _arr(self):
        self.i += 1
        out = []
        while True:
            self._ws()
            c = self.s[self.i]
            if c == "]":
                self.i += 1
                return out
            if c == ",":
                self.i += 1
                continue
            out.append(self.value())

    def _key(self):
        m = _KEY.match(self.s, self.i)
        if not m:
            raise JSLiteralError(f"bad key at {self.i}")
        self.i = m.end()
        return m.group(0)

    def _str(self):
        q = self.s[self.i]
        self.i += 1
        run = _STR_RUN[q]
        parts = []
        s = self.s
        while True:
            m = run.match(s, self.i)
            if m:
                parts.append(m.group(0))
                self.i = m.end()
            c = s[self.i]
            if c == q:
                self.i += 1
                return "".join(parts)
            # backslash escape
            e = s[self.i + 1]
            if e == "u":
                parts.append(chr(int(s[self.i + 2:self.i + 6], 16)))
                self.i += 6
            else:
                parts.append(_ESC.get(e, e))
                self.i += 2

    def _atom(self):
        m = _ATOM.match(self.s, self.i)
        if not m:
            raise JSLiteralError(f"bad token at {self.i}")
        tok = m.group(0)
        self.i = m.end()
        if tok == "true":
            return True
        if tok == "false":
            return False
        if tok in ("null", "undefined"):
            return None
        try:
            return int(tok)
        except ValueError:
            try:
                return float(tok)
            except ValueError:
                return tok


def parse_define(text: str):
    """Parse ``define({...});`` (or a bare object literal) into Python data."""
    a = text.find("{")
    b = text.rfind("}")
    if a < 0 or b < a:
        raise JSLiteralError("no object literal found")
    return _Parser(text[a:b + 1]).value()
