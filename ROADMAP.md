# Roadmap

Each milestone is a small series of PRs. Items move to **Done** only when merged and tested.

## Done (v0.1)

- [x] Markdown brain: `facts/`, `skills/<id>/SKILL.md`, `issues/`, `notes/`, hand-parsed frontmatter
- [x] CLI: `init`, `add` (with near-duplicate refusal), `search` (BM25F, `--json`), `show`, `list`, `lint`, `index`
- [x] Importable API (`Brain`, `Entry`, `search`) for adapters
- [x] Example brain, tests, CI on Python 3.10 and 3.12

## Next: tool adapters

One brain, rendered into each tool's native format. Generated files are never edited by hand.

- [x] **Claude Code**: skills export to `.claude/skills/`, a `CLAUDE.md` pointer, hook wiring
  (`cairn install claude`, `cairn skills export --tool claude`)
- [x] **Codex**: an `AGENTS.md` section that points at the brain and its index
- [x] **GitHub Copilot**: `.github/copilot-instructions.md` generation
- [x] **Cursor**: project rules generation, plus skills as agent-requested rules
- [ ] `cairn sync` to regenerate every adapter's output, with `--check` for CI

## Recall and capture hooks

- [x] **Recall gate**: before a task starts, search the brain with the prompt and inject the top
  hits (`cairn recall`, wired as a Claude Code `UserPromptSubmit` hook; skips trivial prompts)
- [ ] Recall hooks for other tools, as they gain prompt hooks (today they get instructions only)
- [ ] **Capture gate**: when a substantive task ends, require a capture or an explicit "nothing
  durable". Skip trivial turns such as pure Q&A (see "Lessons" in `docs/design.md`)
- [ ] Capture helpers: `cairn add` from a hook payload, with near-duplicate merge suggestions

## Hot-issues board

- [x] `cairn issue record|match|list|resolve|prune`: issues fingerprinted, counted and ranked by
  a recency-weighted hot score (see `docs/hot-issues.md`)
- [x] Error fingerprints that survive path, number, id and timestamp differences, with a BM25
  fallback that learns new variants
- [x] `cairn issue match --format claude-hook`: inject the matching workaround after a failed
  tool call (silent on no match or any error)
- [x] `cairn issue prune`: mark issues `stale` when they stop recurring
- [ ] Record occurrences from the hook itself, so agents don't have to call `record`
- [ ] Hook output for other agents (Codex, Copilot, Cursor) once their adapters land

## Eval harness

- [x] Retrieval eval: 50 labeled queries on a 42-entry eval brain, cairn vs flat BM25 and
  substring baselines, hit@1/hit@3/MRR and no-answer false positives, CI regression gate
- [x] A/B runner: 13 scripted tasks with deterministic checkers, with and without brain recall;
  a mock runner in CI and a Claude Code runner
- [x] Metrics: task success, turns, tokens, wall time, repeated-known-failure rate
- [ ] Real agent A/B results with Claude Code (needs an API budget)
- [ ] Runners for Codex, Copilot and Cursor
- [ ] A held-out query set written by someone who has not read the eval brain
- [x] Retrieval follow-ups the eval found: a no-answer gate for recall (at least two shared
  words; no-answer false positives 5 of 10 -> 2 of 10), and `[[link]]` ids are no longer
  indexed as body text
- [ ] Published results in the README, regenerated in CI on a schedule

## Later / optional

- [ ] MCP server exposing `search`, `show` and `add` over the same API
- [ ] Optional embedding re-ranker, only if the eval harness shows a real gain over BM25
- [ ] Write-up: design notes and eval results
