"""Human-readable game log, used for the log review in verify-engine (a reviewer checks it against rules.md)."""
from __future__ import annotations


class TextLog(list):
    """A list of lines. `add` prefixes the seat as P<n>."""

    def add(self, seat, text: str) -> None:
        self.append(text if seat is None else f"P{seat}: {text}")

    def render(self, last: int = 0) -> str:
        return "\n".join(self[-last:] if last else self)
