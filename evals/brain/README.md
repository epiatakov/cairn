# Eval brain

The corpus for `python -m evals.retrieval` and the knowledge source for the agent A/B harness.
It is a normal cairn brain (`cairn lint --brain evals/brain` must stay clean), written for the
evals: generic, publicly known developer pitfalls, plus distractors that share vocabulary with
them, a stale near-duplicate and an archived entry. See [docs/evals.md](../../docs/evals.md).

Changing an entry changes the retrieval numbers. Regenerate the results and say so in the PR.
