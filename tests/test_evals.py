"""Tests for the eval harnesses in ``evals/`` (retrieval metrics and the agent A/B runner)."""

from __future__ import annotations

import json
import math

import pytest

from cairn import Brain
from cairn.lint import lint
from evals import EVAL_BRAIN
from evals.agent import build_prompt, render_markdown, run_all, run_one, summarize
from evals.agent.runners import ClaudeRunner, MockRunner, parse_output
from evals.agent.tasks import TASKS
from evals.retrieval import (
    KINDS,
    CairnBM25F,
    FlatBM25,
    Substring,
    calibrate_threshold,
    evaluate,
    first_rank,
    load_queries,
    recall_floor,
    run,
)
from evals.retrieval import render_markdown as render_retrieval


@pytest.fixture(scope="module")
def eval_brain() -> Brain:
    return Brain.open(EVAL_BRAIN)


# -- retrieval ----------------------------------------------------------------


def test_eval_brain_is_clean(eval_brain):
    assert len(eval_brain.entries) >= 40
    assert [p for p in lint(eval_brain) if p.severity == "error"] == []


def test_queries_are_well_formed(eval_brain):
    queries = load_queries()
    ids = {e.id for e in eval_brain.entries if e.status != "archived"}
    assert 40 <= len(queries) <= 60
    assert len({q.id for q in queries}) == len(queries)
    assert {q.kind for q in queries} == set(KINDS)
    for q in queries:
        assert (q.kind == "none") == (not q.expected), q.id
        assert set(q.expected) <= ids, q.id


def test_first_rank_and_threshold():
    assert first_rank(["a", "b", "c"], ("c", "b")) == 2
    assert first_rank(["a"], ("z",)) is None
    assert calibrate_threshold([5.0, 1.0, 3.0, 4.0, 2.0, 6.0, 7.0, 8.0, 9.0, 10.0]) == 2.0
    assert calibrate_threshold([]) == math.inf


def test_evaluate_scores_a_toy_retriever():
    class Fixed:
        name = "fixed"

        def search(self, query):
            return {"q": [("x", 3.0), ("y", 2.0)], "n": [("x", 1.0)]}[query]

    from evals.retrieval import Query

    queries = [Query("1", "exact", "q", ("y",)), Query("2", "none", "n", ())]
    m = evaluate(Fixed(), queries)["metrics"]
    assert (m["hit@1"], m["hit@3"], m["mrr"]) == (0.0, 1.0, 0.5)
    assert m["none_any_result"] == 1.0
    assert m["none_fp_at_threshold"] == 0.0  # no correct top-1 hit, so the threshold is inf


def test_recall_floor_counts_hits_at_the_hook_threshold():
    per_query = [
        {"kind": "exact", "rank": 1, "top": [["a", 2.0]]},
        {"kind": "exact", "rank": 1, "top": [["a", 1.0]]},
        {"kind": "none", "rank": None, "top": [["b", 1.6]]},
        {"kind": "none", "rank": None, "top": []},
    ]
    floor = recall_floor({"per_query": per_query}, min_score=1.5)
    assert floor == {"min_score": 1.5, "kept": 0.5, "none_fp": 0.5}


def test_baselines_rank_sensible_entries(eval_brain):
    live = [e for e in eval_brain.entries if e.status != "archived"]
    for retriever in (CairnBM25F(eval_brain), FlatBM25(live), Substring(live)):
        top = retriever.search("database is locked")
        assert top and top[0][0] == "sqlite-database-is-locked", retriever.name
        assert retriever.search("zzzz qqqq") == []
        assert "rg-glob-broken-on-windows" not in [i for i, _ in retriever.search("rg glob")]


def test_run_matches_committed_results_and_renders():
    results = run()
    committed = json.loads((EVAL_BRAIN.parent / "results" / "retrieval.json").read_text("utf-8"))
    assert results == committed, "run `python -m evals.retrieval` and commit the results"
    table = render_retrieval(results, load_queries())
    assert "| cairn-bm25f |" in table and "| bm25-flat |" in table and "| substring |" in table


# -- agent harness ------------------------------------------------------------


def test_task_count_and_brain_ids(eval_brain):
    assert 10 <= len(TASKS) <= 15
    assert len({t.id for t in TASKS}) == len(TASKS)
    ids = {e.id for e in eval_brain.entries}
    for task in TASKS:
        assert set(task.brain_ids) <= ids, task.id


@pytest.mark.parametrize("task", TASKS, ids=lambda t: t.id)
def test_checker_tells_reference_fix_from_naive_fix(task, tmp_path):
    states = {}
    for mode in ("fresh", "naive", "solve"):
        repo = tmp_path / mode
        task.setup(repo)
        if mode != "fresh":
            getattr(task, mode)(repo)
        states[mode] = task.check(repo)
    assert not states["fresh"].passed
    assert not states["naive"].passed and states["naive"].pitfall, states["naive"].detail
    assert states["solve"].passed and not states["solve"].pitfall, states["solve"].detail


def test_mock_runner_end_to_end(eval_brain):
    tasks = TASKS[:3]
    records = run_all(MockRunner(), tasks, repeats=2)
    assert len(records) == len(tasks) * 2 * 2
    summary = summarize(records)
    assert summary["arms"]["brain"]["runs"] == 6
    assert summary["arms"]["none"]["pass_rate"] == 0.0
    assert summary["arms"]["none"]["pitfall_rate"] == 1.0
    for r in records:
        assert r.passed == bool(r.recall_hit), r
    table = render_markdown(records)
    assert "| brain | 6 |" in table and "| none | 6 |" in table


def test_mock_brain_arm_fails_when_recall_misses(tmp_path):
    empty = Brain.init(tmp_path / "empty")
    record = run_one(TASKS[0], "brain", MockRunner(), empty)
    assert record.recalled == [] and record.recall_hit is False
    assert not record.passed and record.pitfall


def test_brain_prompt_includes_recalled_notes(eval_brain):
    task = TASKS[0]
    hits = eval_brain.search(task.prompt, limit=3)
    prompt = build_prompt(task, hits)
    assert hits[0].entry.id in prompt and task.prompt in prompt
    assert build_prompt(task, []).startswith(task.prompt)


def test_claude_runner_skips_without_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    reason = ClaudeRunner(executable="definitely-not-installed").unavailable_reason()
    assert "not on PATH" in reason
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/claude")
    assert "ANTHROPIC_API_KEY" in ClaudeRunner().unavailable_reason()


def test_claude_runner_command_and_output_parsing():
    cmd = ClaudeRunner(model="sonnet", max_turns=7).command()
    assert cmd[:2] == ["claude", "--print"] and "--bare" in cmd
    assert cmd[cmd.index("--max-turns") + 1] == "7" and cmd[cmd.index("--model") + 1] == "sonnet"
    assert cmd[-3:] == ["--disallowedTools", "WebFetch", "WebSearch"]

    out = json.dumps(
        {
            "type": "result",
            "subtype": "success",
            "is_error": False,
            "num_turns": 6,
            "total_cost_usd": 0.12,
            "usage": {"input_tokens": 100, "cache_read_input_tokens": 900, "output_tokens": 50},
        }
    )
    result = parse_output(out)
    assert (result.turns, result.input_tokens, result.output_tokens) == (6, 1000, 50)
    assert result.cost_usd == 0.12 and result.error is None
    assert parse_output("", 1, "boom").error == "boom"
    failed = parse_output(json.dumps({"is_error": True, "subtype": "error_max_turns"}))
    assert failed.error == "error_max_turns"
