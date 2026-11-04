"""Read the PHP literal arrays of Board Game Arena's material.inc.php (source A of the card database).

Only literals occur in that file: integers, quoted strings, true/false, nested `array(...)`, and wrappers such as
`clienttranslate("...")` / `self::_('...')` around a string. Nothing is executed.
"""
from __future__ import annotations

import re

_TOKEN = re.compile(r"""
    (?P<ws>\s+|//[^\n]*|/\*.*?\*/)
  | (?P<num>-?\d+(?:\.\d+)?)
  | (?P<str>'(?:[^'\\]|\\.)*'|"(?:[^"\\]|\\.)*")
  | (?P<arrow>=>)
  | (?P<punct>[(),;\[\]])
  | (?P<word>[A-Za-z_][A-Za-z_0-9]*(?:::[A-Za-z_][A-Za-z_0-9]*)?)
""", re.VERBOSE | re.DOTALL)


def _tokens(src: str):
    pos = 0
    while pos < len(src):
        m = _TOKEN.match(src, pos)
        if not m:
            raise ValueError(f"unexpected character at {pos}: {src[pos:pos + 30]!r}")
        pos = m.end()
        kind = m.lastgroup
        if kind == "ws":
            continue
        yield kind, m.group()


def _unquote(s: str) -> str:
    body = s[1:-1]
    return re.sub(r"\\(.)", r"\1", body)


class _Parser:
    def __init__(self, src: str):
        self.gen = _tokens(src)  # lazy: the source continues with other PHP after the value
        self.cur = next(self.gen, (None, None))

    def peek(self):
        return self.cur

    def take(self, value=None):
        tok = self.cur
        if value is not None and tok[1] != value:
            raise ValueError(f"expected {value!r}, got {tok!r}")
        self.cur = next(self.gen, (None, None))
        return tok

    def value(self):
        kind, text = self.take()
        if kind == "num":
            return float(text) if "." in text else int(text)
        if kind == "str":
            return _unquote(text)
        if kind == "word":
            low = text.lower()
            if low == "true":
                return True
            if low == "false":
                return False
            if low == "null":
                return None
            if low == "array":
                return self.array_body("(", ")")
            # a wrapper function around one literal, e.g. clienttranslate("...")
            self.take("(")
            v = self.value()
            self.take(")")
            return v
        if text == "[":
            return self.array_body(None, "]")
        raise ValueError(f"unexpected token {text!r}")

    def array_body(self, open_, close):
        if open_:
            self.take(open_)
        items, keyed, n = {}, False, 0
        while self.peek()[1] != close:
            v = self.value()
            if self.peek()[0] == "arrow":
                self.take()
                items[v] = self.value()
                keyed = True
            else:
                items[n] = v
                n += 1
            if self.peek()[1] == ",":
                self.take()
        self.take(close)
        return items if keyed else [items[k] for k in range(n)]


def read_assignment(src: str, name: str):
    """Value of `$this-><name> = array(...);` in a PHP source."""
    m = re.search(r"\$this->" + re.escape(name) + r"\s*=\s*", src)
    if not m:
        raise KeyError(name)
    p = _Parser(src[m.end():])
    return p.value()
