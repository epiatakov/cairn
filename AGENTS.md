# AGENTS.md

Canonical instructions for coding agents (and humans) working on this repository.
`CLAUDE.md` and any other tool-specific files point here; edit this file, not them.

## Project

cairn is "one second brain for every coding agent": a plain-Markdown knowledge store
(`src/cairn/`) plus a CLI, `cairn`, with adapters for Claude Code, Codex, Copilot and Cursor,
a recall hook and a hot-issues board. A capture hook is planned (see `ROADMAP.md`). The eval
harness lives in `evals/` (not part of the installed package).

## Stack

- Python 3.10+ with a `src/` layout. The distribution is `cairn-brain`, the import package is `cairn`.
- **Runtime: standard library only.** Do not add runtime dependencies.
- Dev: pytest and ruff (pinned in `pyproject.toml`). CI runs on Python 3.10 and 3.12.

## Commands

```bash
pip install -e ".[dev]"            # set up
pytest                             # tests
ruff check . && ruff format --check .   # lint and format check
ruff format .                      # apply formatting
cairn lint --brain examples/brain  # the example brain must stay clean
cairn index --brain examples/brain # regenerate examples/brain/INDEX.md after editing examples
python -m evals.retrieval          # retrieval eval; commit evals/results/retrieval.json if it changes
python -m evals.agent --runner mock  # agent harness self-test
```

## Layout

| Path | Purpose |
| --- | --- |
| `src/cairn/frontmatter.py` | Hand-written frontmatter parser and writer (YAML subset) |
| `src/cairn/model.py` | `Entry`, schema validation, ids, `[[links]]` |
| `src/cairn/brain.py` | `Brain`: load, query, add, `INDEX.md` |
| `src/cairn/search.py` | Tokenizer and BM25F index |
| `src/cairn/dedupe.py` | Shingle-Jaccard near-duplicate detection |
| `src/cairn/lint.py` | Brain consistency checks |
| `src/cairn/issues.py` | Hot-issues board: fingerprints, matching, record/resolve/prune |
| `src/cairn/issue_cli.py` | `cairn issue ...` subcommands and the Claude Code hook mode |
| `src/cairn/recall.py` | Recall: trivial-prompt filter, thresholded search, hook output |
| `src/cairn/adapters/` | One module per tool (`claude`, `codex`, `copilot`, `cursor`) on `base.py` |
| `src/cairn/agents_cli.py` | `recall`, `install`, `uninstall`, `skills` subcommands |
| `src/cairn/cli.py` | argparse CLI; keep logic in the modules above |
| `examples/brain/` | Example brain used by docs and tests |
| `evals/brain/` | Eval brain; changing it changes the published numbers |
| `evals/retrieval/` | Labeled queries, baselines and metrics (`python -m evals.retrieval`) |
| `evals/agent/` | Agent A/B tasks, checkers and runners (`python -m evals.agent`) |
| `docs/design.md` | Data model and design decisions |
| `docs/hot-issues.md` | Hot-issues board: fingerprints, lifecycle, hook |
| `docs/evals.md` | Eval method, datasets, metrics and threats to validity |

## Conventions

- **Small PRs, tests required.** Every behavior change comes with a test. Keep each PR to one
  concern.
- Keep the public API (`cairn.Brain`, `cairn.Entry`, `cairn.search`) small and stable; adapters
  and a future MCP server import it.
- `--json` output is a contract. Additive changes only. Bump `JSON_SCHEMA_VERSION` in `cli.py`
  for anything else.
- User-facing errors raise `CairnError` and print one clear line. No tracebacks for expected
  failures.
- Read and write files as UTF-8 with LF line endings. CLI output stays ASCII.
- Type hints on public functions; docstrings where the why isn't obvious.
- Update `README.md` and `ROADMAP.md` when a planned item ships. Never describe planned work as
  built.

## Clean-room rule

Only original code written here, built from public patterns (AGENTS.md, Claude Code hooks,
skills folders, BM25). Never add employer names, internal product or tool names, internal file
layouts, or copied code. Example entries must be generic, publicly known facts. See
`CLEAN_ROOM.md`.
