# Roadmap

Each milestone is a small series of PRs. Items move to **Done** only when merged and tested.

## Done (v0.1)

- [x] Markdown brain: `facts/`, `skills/<id>/SKILL.md`, `issues/`, `notes/`, hand-parsed frontmatter
- [x] CLI: `init`, `add` (with near-duplicate refusal), `search` (BM25F, `--json`), `show`, `list`, `lint`, `index`
- [x] Importable API (`Brain`, `Entry`, `search`) for adapters
- [x] Example brain, tests, CI on Python 3.10 and 3.12

## Next: tool adapters

One brain, rendered into each tool's native format. Generated files are never edited by hand.

- [ ] **Claude Code**: skills export to `.claude/skills/`, a `CLAUDE.md` pointer, hook wiring
- [ ] **Codex**: an `AGENTS.md` section that points at the brain and its index
- [ ] **GitHub Copilot**: `.github/copilot-instructions.md` generation
- [ ] **Cursor**: project rules generation
- [ ] `cairn sync` to regenerate every adapter's output, with `--check` for CI

## Recall and capture hooks

- [ ] **Recall gate**: before a task starts, search the brain with the prompt and inject the top
  hits (built on `cairn search --json`)
- [ ] **Capture gate**: when a substantive task ends, require a capture or an explicit "nothing
  durable". Skip trivial turns such as pure Q&A (see "Lessons" in `docs/design.md`)
- [ ] Capture helpers: `cairn add` from a hook payload, with near-duplicate merge suggestions

## Hot-issues board

- [ ] `cairn issues`: active `issue` entries ranked by recency and hit count
- [ ] Inject matching hot issues when a tool error appears (for example, a failing command)
- [ ] Mark issues `stale` automatically when the workaround stops being used

## Eval harness

- [x] Retrieval eval: 50 labeled queries on a 42-entry eval brain, cairn vs flat BM25 and
  substring baselines, hit@1/hit@3/MRR and no-answer false positives, CI regression gate
- [x] A/B runner: 13 scripted tasks with deterministic checkers, with and without brain recall;
  a mock runner in CI and a Claude Code runner
- [x] Metrics: task success, turns, tokens, wall time, repeated-known-failure rate
- [ ] Real agent A/B results with Claude Code (needs an API budget)
- [ ] Runners for Codex, Copilot and Cursor
- [ ] A held-out query set written by someone who has not read the eval brain
- [ ] Retrieval follow-ups the eval found: a score floor for recall, and not indexing
  `[[link]]` ids as body text
- [ ] Published results in the README, regenerated in CI on a schedule

## Later / optional

- [ ] MCP server exposing `search`, `show` and `add` over the same API
- [ ] Optional embedding re-ranker, only if the eval harness shows a real gain over BM25
- [ ] Write-up: design notes and eval results
