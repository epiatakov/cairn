"""``python -m evals.retrieval``: print the Markdown table, write JSON, gate on hit@3."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .. import EVAL_BRAIN
from . import BASELINE_FILE, GATED, QUERIES_FILE, RESULTS_FILE, load_queries, render_markdown, run


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m evals.retrieval", description=__doc__)
    parser.add_argument("--brain", type=Path, default=EVAL_BRAIN)
    parser.add_argument("--queries", type=Path, default=QUERIES_FILE)
    parser.add_argument("--out", type=Path, default=RESULTS_FILE)
    parser.add_argument("--baseline", type=Path, default=BASELINE_FILE)
    parser.add_argument(
        "--update-baseline",
        action="store_true",
        help=f"record the current {GATED} hit@3 as the new floor",
    )
    args = parser.parse_args(argv)

    results = run(args.brain, args.queries)
    print(render_markdown(results, load_queries(args.queries)), end="")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    _write_json(args.out, results)

    current = results["retrievers"][GATED]["metrics"]["hit@3"]
    if args.update_baseline:
        _write_json(args.baseline, {"retriever": GATED, "hit@3": current})
        print(f"\nrecorded baseline: {GATED} hit@3 = {current:.4f}")
        return 0
    if not args.baseline.exists():
        print(f"\nno baseline at {args.baseline}; run with --update-baseline", file=sys.stderr)
        return 1
    floor = json.loads(args.baseline.read_text(encoding="utf-8"))["hit@3"]
    if current < floor - 1e-9:
        print(f"\nFAIL: {GATED} hit@3 {current:.4f} is below the baseline {floor:.4f}")
        return 1
    print(f"\nOK: {GATED} hit@3 {current:.4f} >= baseline {floor:.4f}")
    return 0


def _write_json(path: Path, data: dict) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")


if __name__ == "__main__":
    sys.exit(main())
