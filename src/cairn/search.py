"""Lexical search over entries with BM25F (BM25 with per-field weights).

Each entry has three fields: title, tags and body. A term's frequency is
length-normalised per field, weighted, summed, then saturated once, so a query
word in the title counts more than the same word buried in a long body.
"""

from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from .model import Entry

FIELD_WEIGHTS = {"title": 3.0, "tags": 2.0, "body": 1.0}
K1 = 1.2
B = 0.75

_TOKEN_RE = re.compile(r"[a-z0-9]+")
STOPWORDS = frozenset(
    """
    a an and are as at be but by can do does for from has have how i if in into is it its
    not of on or so that the their then there these this to was we were what when where
    which while who why will with you your
    """.split()  # noqa: SIM905
)


def tokenize(text: str) -> list[str]:
    """Lowercase, split on non-alphanumerics, drop stopwords, fold simple plurals."""
    folded = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return [_stem(t) for t in _TOKEN_RE.findall(folded) if t not in STOPWORDS]


def _stem(token: str) -> str:
    if len(token) > 4 and token.endswith("ies"):
        return token[:-3] + "y"
    if len(token) > 3 and token.endswith("s") and not token.endswith(("ss", "us", "is")):
        return token[:-1]
    return token


@dataclass(frozen=True)
class Hit:
    entry: Entry
    score: float
    snippet: str


class Index:
    """An in-memory BM25F index. Build once per process; it is cheap for personal brains."""

    def __init__(self, entries: Iterable[Entry]) -> None:
        self.entries = list(entries)
        self._fields: list[dict[str, Counter[str]]] = []
        self._lengths: list[dict[str, int]] = []
        df: Counter[str] = Counter()
        for entry in self.entries:
            fields = {
                "title": Counter(tokenize(entry.title)),
                "tags": Counter(tokenize(" ".join(entry.tags))),
                "body": Counter(tokenize(entry.body)),
            }
            self._fields.append(fields)
            self._lengths.append({name: sum(c.values()) for name, c in fields.items()})
            df.update(set().union(*fields.values()))
        n = len(self.entries)
        self._idf = {t: math.log(1 + (n - d + 0.5) / (d + 0.5)) for t, d in df.items()}
        self._avg = {
            name: (sum(lengths[name] for lengths in self._lengths) / n if n else 0.0) or 1.0
            for name in FIELD_WEIGHTS
        }

    def score(self, i: int, terms: Sequence[str]) -> float:
        fields, lengths = self._fields[i], self._lengths[i]
        total = 0.0
        for term in terms:
            idf = self._idf.get(term)
            if idf is None:
                continue
            tf = sum(
                weight * fields[name][term] / (1 - B + B * lengths[name] / self._avg[name])
                for name, weight in FIELD_WEIGHTS.items()
            )
            total += idf * tf / (K1 + tf)
        return total

    def search(
        self,
        query: str,
        *,
        type: str | None = None,
        limit: int | None = 10,
        include_archived: bool = False,
    ) -> list[Hit]:
        terms = list(dict.fromkeys(tokenize(query)))
        hits = []
        for i, entry in enumerate(self.entries):
            if type and entry.type != type:
                continue
            if entry.status == "archived" and not include_archived:
                continue
            score = self.score(i, terms)
            if score > 0:
                hits.append(Hit(entry, score, snippet(entry, terms)))
        hits.sort(key=lambda h: (-h.score, h.entry.id))
        return hits if limit is None else hits[:limit]


def search(entries: Iterable[Entry], query: str, **kwargs) -> list[Hit]:
    """Convenience wrapper: build an :class:`Index` and query it once."""
    return Index(entries).search(query, **kwargs)


def snippet(entry: Entry, terms: Sequence[str], width: int = 160) -> str:
    """The body line sharing the most terms with the query, or the first body line."""
    lines = [line.strip().lstrip("#>-* ").strip() for line in entry.body.splitlines()]
    lines = [line for line in lines if line and not line.startswith("```")]
    if not lines:
        return ""
    wanted = set(terms)
    best = max(lines, key=lambda line: len(wanted.intersection(tokenize(line))))
    return best if len(best) <= width else best[: width - 3].rstrip() + "..."
