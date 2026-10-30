"""Offline retrieval eval: labeled queries against ``evals/brain``, cairn vs two baselines.

Every retriever sees the same live (non-archived) entries and returns up to ``LIMIT`` ranked
``(id, score)`` pairs. Ties are broken by id, so every number here is deterministic.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from cairn import Brain, Entry, Index
from cairn.recall import DEFAULT_MIN_SCORE
from cairn.search import STOPWORDS

from .. import EVAL_BRAIN, EVALS_DIR, RESULTS_DIR

QUERIES_FILE = EVALS_DIR / "retrieval" / "queries.json"
BASELINE_FILE = EVALS_DIR / "retrieval" / "baseline.json"
RESULTS_FILE = RESULTS_DIR / "retrieval.json"

LIMIT = 10
KINDS = ("exact", "paraphrase", "error", "vague", "none")
# The no-answer threshold keeps this share of correct top-1 hits (see calibrate_threshold).
KEEP = 0.9
GATED = "cairn-bm25f"


@dataclass(frozen=True)
class Query:
    id: str
    kind: str
    query: str
    expected: tuple[str, ...]


class Retriever(Protocol):
    name: str

    def search(self, query: str) -> list[tuple[str, float]]: ...


class CairnBM25F:
    """cairn's own search, through the public ``Brain.search`` API."""

    name = "cairn-bm25f"

    def __init__(self, brain: Brain) -> None:
        self.brain = brain

    def search(self, query: str) -> list[tuple[str, float]]:
        return [(h.entry.id, h.score) for h in self.brain.search(query, limit=LIMIT)]


class FlatBM25:
    """Baseline: plain BM25 over one field (title, tags and body concatenated).

    Same tokenizer, ``k1`` and ``b`` as cairn, so the only difference is the field weighting.
    """

    name = "bm25-flat"

    def __init__(self, entries: Sequence[Entry]) -> None:
        flat = [
            Entry(id=e.id, type=e.type, title="", body=f"{e.title}\n{' '.join(e.tags)}\n{e.body}")
            for e in entries
        ]
        self.index = Index(flat)

    def search(self, query: str) -> list[tuple[str, float]]:
        return [(h.entry.id, h.score) for h in self.index.search(query, limit=LIMIT)]


class Substring:
    """Baseline: grep-style keyword match.

    Score is the share of distinct query words found as substrings of the lowercased entry
    text. Uses cairn's stopword list (otherwise "the" matches everything), but no stemming,
    no IDF and no field weights.
    """

    name = "substring"

    def __init__(self, entries: Sequence[Entry]) -> None:
        self.docs = [(e.id, f"{e.title}\n{' '.join(e.tags)}\n{e.body}".lower()) for e in entries]

    def search(self, query: str) -> list[tuple[str, float]]:
        words = list(dict.fromkeys(re.findall(r"[a-z0-9]+", query.lower())))
        words = [w for w in words if w not in STOPWORDS]
        if not words:
            return []
        scored = [
            (doc_id, sum(w in text for w in words) / len(words)) for doc_id, text in self.docs
        ]
        scored = [(doc_id, s) for doc_id, s in scored if s > 0]
        scored.sort(key=lambda pair: (-pair[1], pair[0]))
        return scored[:LIMIT]


def load_queries(path: Path = QUERIES_FILE) -> list[Query]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [Query(q["id"], q["kind"], q["query"], tuple(q["expected"])) for q in raw]


def retrievers(brain: Brain) -> list[Retriever]:
    live = [e for e in brain.entries if e.status != "archived"]
    return [CairnBM25F(brain), FlatBM25(live), Substring(live)]


def first_rank(ranked: Sequence[str], expected: Sequence[str]) -> int | None:
    """1-based rank of the first expected id, or None if none is in ``ranked``."""
    return next((i for i, doc_id in enumerate(ranked, 1) if doc_id in expected), None)


def calibrate_threshold(correct_top_scores: Sequence[float], keep: float = KEEP) -> float:
    """The lowest score that still keeps ``keep`` of the correct top-1 hits.

    Raw scores are not comparable across retrievers, so each one gets its own operating
    point, set only from answerable queries. The no-answer queries never influence it.
    """
    if not correct_top_scores:
        return math.inf
    ordered = sorted(correct_top_scores)
    return ordered[math.floor(round((1 - keep) * len(ordered), 9))]


def mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def evaluate(retriever: Retriever, queries: Sequence[Query]) -> dict:
    per_query = []
    for q in queries:
        results = retriever.search(q.query)
        ranked = [doc_id for doc_id, _ in results]
        per_query.append(
            {
                "id": q.id,
                "kind": q.kind,
                "rank": first_rank(ranked, q.expected) if q.expected else None,
                "top": [[doc_id, round(score, 4)] for doc_id, score in results[:3]],
            }
        )
    answerable = [p for p in per_query if p["kind"] != "none"]
    unanswerable = [p for p in per_query if p["kind"] == "none"]

    def hit(p: dict, k: int) -> float:
        return float(p["rank"] is not None and p["rank"] <= k)

    threshold = calibrate_threshold([p["top"][0][1] for p in answerable if p["rank"] == 1])
    metrics = {
        "hit@1": mean([hit(p, 1) for p in answerable]),
        "hit@3": mean([hit(p, 3) for p in answerable]),
        "mrr": mean([1 / p["rank"] if p["rank"] else 0.0 for p in answerable]),
        "none_any_result": mean([float(bool(p["top"])) for p in unanswerable]),
        "none_fp_at_threshold": mean(
            [float(bool(p["top"]) and p["top"][0][1] >= threshold) for p in unanswerable]
        ),
    }
    by_kind = {
        kind: mean([hit(p, 3) for p in answerable if p["kind"] == kind])
        for kind in KINDS
        if kind != "none"
    }
    return {
        "metrics": {k: round(v, 4) for k, v in metrics.items()},
        "hit@3_by_kind": {k: round(v, 4) for k, v in by_kind.items()},
        "threshold": round(threshold, 4) if math.isfinite(threshold) else None,
        "per_query": per_query,
    }


def run(brain_dir: Path = EVAL_BRAIN, queries_file: Path = QUERIES_FILE) -> dict:
    brain = Brain.open(brain_dir)
    queries = load_queries(queries_file)
    counts = {kind: sum(q.kind == kind for q in queries) for kind in KINDS}
    results = {
        "version": 1,
        "entries": sum(e.status != "archived" for e in brain.entries),
        "queries": counts,
        "limit": LIMIT,
        "keep": KEEP,
        "retrievers": {r.name: evaluate(r, queries) for r in retrievers(brain)},
    }
    results["recall_floor"] = recall_floor(results["retrievers"][GATED])
    return results


def recall_floor(cairn: dict, min_score: float = DEFAULT_MIN_SCORE) -> dict:
    """How cairn's shipped recall hook floor (``cairn.recall``) does on this set.

    ``kept`` is the share of answerable queries whose correct top-1 hit clears the floor;
    ``none_fp`` the share of no-answer queries whose top hit clears it.
    """
    answerable = [p for p in cairn["per_query"] if p["kind"] != "none"]
    unanswerable = [p for p in cairn["per_query"] if p["kind"] == "none"]
    return {
        "min_score": min_score,
        "kept": round(
            mean([float(p["rank"] == 1 and p["top"][0][1] >= min_score) for p in answerable]), 4
        ),
        "none_fp": round(
            mean([float(bool(p["top"]) and p["top"][0][1] >= min_score) for p in unanswerable]), 4
        ),
    }


def pct(value: float) -> str:
    return f"{100 * value:.0f}%"


def render_markdown(results: dict, queries: Sequence[Query]) -> str:
    rows = [
        "| Retriever | hit@1 | hit@3 | MRR | No-answer: any result | No-answer: FP at threshold |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, r in results["retrievers"].items():
        m = r["metrics"]
        rows.append(
            f"| {name} | {pct(m['hit@1'])} | {pct(m['hit@3'])} | {m['mrr']:.2f} "
            f"| {pct(m['none_any_result'])} | {pct(m['none_fp_at_threshold'])} |"
        )
    kinds = [k for k in KINDS if k != "none"]
    rows += [
        "",
        "hit@3 by query kind:",
        "",
        "| Retriever | " + " | ".join(f"{k} ({results['queries'][k]})" for k in kinds) + " |",
        "| --- |" + " ---: |" * len(kinds),
    ]
    for name, r in results["retrievers"].items():
        rows.append(f"| {name} | " + " | ".join(pct(r["hit@3_by_kind"][k]) for k in kinds) + " |")

    text = {q.id: q.query for q in queries}
    cairn = results["retrievers"].get(GATED)
    if cairn:
        misses = [
            p for p in cairn["per_query"] if p["kind"] != "none" and not (p["rank"] or 99) <= 3
        ]
        fps = [
            p
            for p in cairn["per_query"]
            if p["kind"] == "none" and p["top"] and p["top"][0][1] >= (cairn["threshold"] or 0)
        ]
        rows += ["", f"{GATED} misses (expected id not in top 3):", ""]
        rows += [f"- {p['id']} ({p['kind']}): `{text[p['id']]}`" for p in misses] or ["- none"]
        rows += ["", f"{GATED} no-answer queries above threshold:", ""]
        rows += [
            f"- {p['id']}: `{text[p['id']]}` -> {p['top'][0][0]} ({p['top'][0][1]:.2f})"
            for p in fps
        ] or ["- none"]
    floor = results.get("recall_floor")
    if floor:
        rows += [
            "",
            f"At the recall hook's floor (min_score {floor['min_score']}), {GATED} keeps "
            f"{pct(floor['kept'])} of answerable queries as a correct top-1 hit and lets "
            f"{pct(floor['none_fp'])} of no-answer queries through.",
        ]
    return "\n".join(rows) + "\n"
