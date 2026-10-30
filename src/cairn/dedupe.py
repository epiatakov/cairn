"""Near-duplicate detection with character-shingle Jaccard similarity.

Two entries are near-duplicates when either their titles or their full text
(title + body) share most of their character 5-grams. Comparing titles on their
own catches a new title-only entry that restates an existing, longer one.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from itertools import combinations

from .model import Entry

SHINGLE_SIZE = 5
THRESHOLD = 0.6


def normalize(text: str) -> str:
    folded = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return " ".join(re.findall(r"[a-z0-9]+", folded))


def shingles(text: str, k: int = SHINGLE_SIZE) -> frozenset[str]:
    norm = normalize(text)
    if len(norm) <= k:
        return frozenset([norm]) if norm else frozenset()
    return frozenset(norm[i : i + k] for i in range(len(norm) - k + 1))


def jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


@dataclass(frozen=True)
class Fingerprint:
    title: frozenset[str]
    content: frozenset[str]

    @classmethod
    def of(cls, title: str, body: str = "") -> Fingerprint:
        return cls(shingles(title), shingles(f"{title}\n{body}"))

    def similarity(self, other: Fingerprint) -> float:
        return max(jaccard(self.title, other.title), jaccard(self.content, other.content))


@dataclass(frozen=True)
class Match:
    entry: Entry
    similarity: float


def find_similar(
    title: str,
    body: str,
    entries: Iterable[Entry],
    threshold: float = THRESHOLD,
) -> list[Match]:
    """Entries at or above ``threshold`` similarity to a candidate, most similar first."""
    candidate = Fingerprint.of(title, body)
    matches = []
    for entry in entries:
        sim = candidate.similarity(Fingerprint.of(entry.title, entry.body))
        if sim >= threshold:
            matches.append(Match(entry, sim))
    return sorted(matches, key=lambda m: (-m.similarity, m.entry.id))


def near_duplicate_pairs(
    entries: Iterable[Entry], threshold: float = THRESHOLD
) -> list[tuple[Entry, Entry, float]]:
    """All pairs at or above ``threshold``. Quadratic, fine for thousands of entries."""
    prints = [(e, Fingerprint.of(e.title, e.body)) for e in entries]
    pairs = []
    for (a, fa), (b, fb) in combinations(prints, 2):
        sim = fa.similarity(fb)
        if sim >= threshold:
            pairs.append((a, b, sim))
    return pairs
