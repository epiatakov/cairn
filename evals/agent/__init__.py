"""Agent A/B harness: the same scripted tasks, with and without brain recall.

For each task and repeat, the harness builds a throwaway git repository, runs the agent
twice (arm ``brain`` and arm ``none``), checks the result, and records pass/fail, whether
the known failure was repeated, turns, tokens, cost and wall time.

The ``brain`` arm gets the hits of ``cairn.recall.recall`` for the task prompt (the same
selection, limit and score floor as the recall hook), prepended to the prompt with their
bodies. A retrieval miss is a miss here too.
"""

from __future__ import annotations

import shutil
import tempfile
import time
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

from cairn import Brain
from cairn.recall import DEFAULT_LIMIT
from cairn.recall import recall as cairn_recall

from .. import EVAL_BRAIN
from .runners import Runner
from .tasks import TASKS, Task

ARMS = ("brain", "none")
RECALL_LIMIT = DEFAULT_LIMIT
SUFFIX = (
    "\n\nWork in the current directory, which is a git repository. Make the change directly; "
    "do not ask questions. Do not commit unless the task needs it."
)


@dataclass
class Record:
    task: str
    arm: str
    runner: str
    repeat: int
    passed: bool
    pitfall: bool
    detail: str
    turns: int | None
    input_tokens: int | None
    output_tokens: int | None
    cost_usd: float | None
    wall_s: float
    recalled: list[str]
    recall_hit: bool | None
    error: str | None


def recall(brain: Brain, query: str, limit: int = RECALL_LIMIT) -> list:
    return cairn_recall(brain, query, limit=limit)


def build_prompt(task: Task, hits: Sequence) -> str:
    if not hits:
        return task.prompt + SUFFIX
    notes = "\n\n".join(f"### {h.entry.title} ({h.entry.id})\n\n{h.entry.body}" for h in hits)
    return (
        "Notes from the team's knowledge base that matched this task. They may or may not "
        f"be relevant.\n\n{notes}\n\n---\n\nTask: {task.prompt}{SUFFIX}"
    )


def run_one(
    task: Task, arm: str, runner: Runner, brain: Brain, repeat: int = 0, keep: bool = False
) -> Record:
    hits = recall(brain, task.prompt) if arm == "brain" else []
    recalled = [h.entry.id for h in hits]
    repo = Path(tempfile.mkdtemp(prefix=f"cairn-eval-{task.id}-{arm}-")) / "repo"
    try:
        task.setup(repo)
        start = time.perf_counter()
        result = runner.run(task, repo, build_prompt(task, hits), recalled)
        wall = time.perf_counter() - start
        outcome = task.check(repo)
    finally:
        if not keep:
            shutil.rmtree(repo.parent, ignore_errors=True)
    return Record(
        task=task.id,
        arm=arm,
        runner=runner.name,
        repeat=repeat,
        passed=outcome.passed,
        pitfall=outcome.pitfall,
        detail=outcome.detail,
        turns=result.turns,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        cost_usd=result.cost_usd,
        wall_s=round(wall, 2),
        recalled=recalled,
        recall_hit=bool(set(recalled) & set(task.brain_ids)) if arm == "brain" else None,
        error=result.error,
    )


def run_all(
    runner: Runner,
    tasks: Sequence[Task] = TASKS,
    *,
    repeats: int = 1,
    brain_dir: Path = EVAL_BRAIN,
    keep: bool = False,
    progress=None,
) -> list[Record]:
    brain = Brain.open(brain_dir)
    records = []
    for repeat in range(repeats):
        for task in tasks:
            for arm in ARMS:
                record = run_one(task, arm, runner, brain, repeat, keep)
                records.append(record)
                if progress:
                    progress(record)
    return records


def _mean(values: Sequence[float | int | None]) -> float | None:
    present = [v for v in values if v is not None]
    return sum(present) / len(present) if present else None


def _sum(values: Sequence[float | None]) -> float | None:
    present = [v for v in values if v is not None]
    return sum(present) if present else None


def summarize(records: Sequence[Record]) -> dict:
    arms = {}
    for arm in ARMS:
        rs = [r for r in records if r.arm == arm]
        if not rs:
            continue
        tokens = [
            (r.input_tokens or 0) + (r.output_tokens or 0)
            if r.input_tokens is not None or r.output_tokens is not None
            else None
            for r in rs
        ]
        arms[arm] = {
            "runs": len(rs),
            "pass_rate": sum(r.passed for r in rs) / len(rs),
            "pitfall_rate": sum(r.pitfall for r in rs) / len(rs),
            "mean_turns": _mean([r.turns for r in rs]),
            "mean_tokens": _mean(tokens),
            "total_cost_usd": _sum([r.cost_usd for r in rs]),
            "mean_wall_s": _mean([r.wall_s for r in rs]),
            "errors": sum(r.error is not None for r in rs),
        }
    brain_runs = [r for r in records if r.arm == "brain"]
    recall_rate = (
        sum(bool(r.recall_hit) for r in brain_runs) / len(brain_runs) if brain_runs else None
    )
    return {"arms": arms, "recall_hit_rate": recall_rate}


def _fmt(value: float | None, spec: str = ".1f") -> str:
    return "n/a" if value is None else format(value, spec)


def render_markdown(records: Sequence[Record]) -> str:
    summary = summarize(records)
    rows = [
        "| Arm | Runs | Pass | Repeated known failure | Mean turns | Mean tokens "
        "| Mean wall time |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for arm, s in summary["arms"].items():
        rows.append(
            f"| {arm} | {s['runs']} | {s['pass_rate']:.0%} | {s['pitfall_rate']:.0%} "
            f"| {_fmt(s['mean_turns'])} | {_fmt(s['mean_tokens'], ',.0f')} "
            f"| {_fmt(s['mean_wall_s'])} s |"
        )
    if summary["recall_hit_rate"] is not None:
        rows += [
            "",
            f"Recall surfaced a relevant entry (top {RECALL_LIMIT}) in "
            f"{summary['recall_hit_rate']:.0%} of brain-arm runs.",
        ]
    rows += ["", "| Task | brain | none |", "| --- | --- | --- |"]
    for task in dict.fromkeys(r.task for r in records):
        cells = []
        for arm in ARMS:
            rs = [r for r in records if r.task == task and r.arm == arm]
            mark = f"{sum(r.passed for r in rs)}/{len(rs)}"
            if any(r.pitfall for r in rs):
                mark += " (repeated)"
            cells.append(mark)
        rows.append(f"| {task} | " + " | ".join(cells) + " |")
    return "\n".join(rows) + "\n"


def to_json(records: Sequence[Record]) -> dict:
    return {
        "version": 1,
        "summary": summarize(records),
        "records": [asdict(r) for r in records],
    }
