"""Consistency checks for a brain. Errors fail ``cairn lint``; warnings do not (unless --strict)."""

from __future__ import annotations

from collections import defaultdict

from . import dedupe
from .brain import Brain, Problem
from .model import SKILL_FILE, TYPE_DIRS


def lint(brain: Brain, *, threshold: float = dedupe.THRESHOLD) -> list[Problem]:
    problems = list(brain.problems)
    entries = brain.entries

    by_id = defaultdict(list)
    for entry in entries:
        by_id[entry.id].append(entry)
    for entry_id, group in by_id.items():
        if len(group) > 1:
            others = ", ".join(brain.relpath(e.path) for e in group)
            for entry in group:
                problems.append(
                    Problem(
                        entry.path, "error", "duplicate-id", f"id '{entry_id}' used by {others}"
                    )
                )

    for entry in entries:
        if entry.path is None:
            continue
        folder = entry.path.parent.parent if entry.path.name == SKILL_FILE else entry.path.parent
        expected_dir = TYPE_DIRS[entry.type]
        if folder.name != expected_dir or folder.parent != brain.root:
            problems.append(
                Problem(
                    entry.path,
                    "error",
                    "wrong-folder",
                    f"type '{entry.type}' belongs in {expected_dir}/",
                )
            )
        stem = entry.path.parent.name if entry.path.name == SKILL_FILE else entry.path.stem
        if stem != entry.id:
            problems.append(
                Problem(
                    entry.path,
                    "warning",
                    "id-mismatch",
                    f"id '{entry.id}' does not match file name '{stem}'",
                )
            )
        for target in entry.outgoing_links():
            if target not in by_id:
                problems.append(
                    Problem(entry.path, "error", "broken-link", f"link to unknown id '{target}'")
                )

    live = [e for e in entries if e.status != "archived"]
    for a, b, sim in dedupe.near_duplicate_pairs(live, threshold):
        problems.append(
            Problem(
                a.path,
                "warning",
                "near-duplicate",
                f"'{a.id}' and '{b.id}' are {sim:.0%} similar ({brain.relpath(b.path)})",
            )
        )

    return sorted(problems, key=lambda p: (brain.relpath(p.path), p.severity, p.code, p.message))
