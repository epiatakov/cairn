"""``python -m evals.agent``: run the A/B tasks with a runner and report brain vs none."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .. import EVAL_BRAIN, RESULTS_DIR
from . import Record, render_markdown, run_all, to_json
from .runners import ClaudeRunner, MockRunner, Runner
from .tasks import TASKS, get


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m evals.agent", description=__doc__)
    parser.add_argument("--runner", choices=["mock", "claude"], default="mock")
    parser.add_argument("--tasks", help="comma-separated task ids (default: all)")
    parser.add_argument("--repeats", type=int, default=1, help="runs per task and arm")
    parser.add_argument("--brain", type=Path, default=EVAL_BRAIN)
    parser.add_argument(
        "--out", type=Path, help="JSON output (default: results/agent-<runner>.json)"
    )
    parser.add_argument("--model", help="claude runner: model alias or id")
    parser.add_argument("--max-turns", type=int, default=25, help="claude runner: turn cap")
    parser.add_argument(
        "--max-budget-usd", type=float, default=1.0, help="claude runner: spend cap per run"
    )
    parser.add_argument("--keep", action="store_true", help="keep the throwaway repositories")
    parser.add_argument("--list", action="store_true", help="list the tasks and exit")
    args = parser.parse_args(argv)

    if args.list:
        for task in TASKS:
            print(f"{task.id:16} {', '.join(task.brain_ids)}")
        return 0
    try:
        tasks = [get(t.strip()) for t in args.tasks.split(",")] if args.tasks else TASKS
    except KeyError as exc:
        print(f"unknown task {exc}; see --list", file=sys.stderr)
        return 2

    runner: Runner = (
        ClaudeRunner(model=args.model, max_turns=args.max_turns, max_budget_usd=args.max_budget_usd)
        if args.runner == "claude"
        else MockRunner()
    )
    reason = runner.unavailable_reason()
    if reason:
        print(f"skipped: {runner.name} runner unavailable ({reason})")
        return 0

    def progress(r: Record) -> None:
        status = "pass" if r.passed else "FAIL"
        extra = " repeated-known-failure" if r.pitfall else ""
        print(f"  {r.task:16} {r.arm:5} #{r.repeat} {status}{extra} ({r.detail})", file=sys.stderr)

    records = run_all(
        runner, tasks, repeats=args.repeats, brain_dir=args.brain, keep=args.keep, progress=progress
    )
    print(render_markdown(records), end="")
    out = args.out or RESULTS_DIR / f"agent-{runner.name}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="\n") as fh:
        json.dump(to_json(records), fh, indent=2)
        fh.write("\n")
    print(f"\nwrote {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
