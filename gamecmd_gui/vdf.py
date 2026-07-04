"""
vdf.py

A small, dependency-free parser for Valve's text KeyValues format (VDF),
as used in steamapps/libraryfolders.vdf and appmanifest_*.acf files.

Only handles the simple nested-dict-of-strings subset those two file
types actually use -- no arrays, no conditional blocks (#base/#include),
no macros. That's all Steam writes for these particular files.
"""

import re

_TOKEN_RE = re.compile(r'"((?:[^"\\]|\\.)*)"|(\{)|(\})')


def parse_vdf(text: str) -> dict:
    """Parse VDF/KeyValues text into a nested dict of str -> (str | dict)."""
    tokens = []
    for m in _TOKEN_RE.finditer(text):
        if m.group(2):
            tokens.append("{")
        elif m.group(3):
            tokens.append("}")
        else:
            tokens.append(m.group(1).replace('\\"', '"').replace("\\\\", "\\"))

    pos = 0

    def parse_block() -> dict:
        nonlocal pos
        result: dict = {}
        while pos < len(tokens):
            tok = tokens[pos]
            if tok == "}":
                pos += 1
                return result
            key = tok
            pos += 1
            if pos >= len(tokens):
                break
            nxt = tokens[pos]
            if nxt == "{":
                pos += 1
                value = parse_block()
            elif nxt == "}":
                # malformed / dangling key with no value -- skip
                continue
            else:
                value = nxt
                pos += 1
            result[key] = value
        return result

    return parse_block()
