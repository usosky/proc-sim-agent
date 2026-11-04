"""Read SKILL.md frontmatter without PyYAML.

Accepts the subset that Agent Skills use (top-level `key: value` lines and one-level maps such
as `metadata`) and rejects plain values that YAML would read differently: a value with ": " or
" #" in it, or starting with a YAML indicator character, must be quoted.
"""
import re

_INDICATORS = tuple("[]{}&*!|>%@`'\",#?:-")


def read(path):
    """Return (frontmatter dict, body text, frontmatter line count)."""
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n", text, re.S)
    if not m:
        raise ValueError(f"{path}: no YAML frontmatter")
    fm, parent = {}, None
    for line in m.group(1).splitlines():
        if not line.strip():
            continue
        if line[0] in " \t":
            if parent is None:
                raise ValueError(f"indented line without a parent key: {line!r}")
            k, v = _key_value(line.strip())
            fm[parent][k] = v
            continue
        k, v = _key_value(line)
        if k in fm:
            raise ValueError(f"duplicate key {k!r}")
        if v == "":
            fm[k], parent = {}, k
        else:
            fm[k], parent = v, None
    return fm, text[m.end():], m.group(1).count("\n") + 1


def _key_value(line):
    k, sep, v = line.partition(":")
    if not sep or not k.strip() or " " in k.strip():
        raise ValueError(f"not a 'key: value' line: {line!r}")
    v = v.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        return k.strip(), v[1:-1]
    if v and (v.startswith(_INDICATORS) or ": " in v or " #" in v):
        raise ValueError(f"quote the value of {k.strip()!r}: {v[:40]!r}")
    return k.strip(), v
