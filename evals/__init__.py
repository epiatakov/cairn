"""Evaluation harnesses for cairn: offline retrieval metrics and an agent A/B runner.

Not part of the installed package. Run from the repository root, for example
``python -m evals.retrieval`` or ``python -m evals.agent --runner mock``.
"""

from pathlib import Path

EVALS_DIR = Path(__file__).resolve().parent
EVAL_BRAIN = EVALS_DIR / "brain"
RESULTS_DIR = EVALS_DIR / "results"
