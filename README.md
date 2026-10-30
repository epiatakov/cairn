# cairn

[![CI](https://github.com/epiatakov/cairn/actions/workflows/ci.yml/badge.svg)](https://github.com/epiatakov/cairn/actions/workflows/ci.yml)

**One second brain for every coding agent.**

cairn is a plain-Markdown knowledge store plus the plumbing that makes coding agents
(Claude Code, Codex, GitHub Copilot, Cursor) **recall** relevant knowledge before they work
and **capture** durable facts after they work, all from one shared source of truth.

> **Status: early.** The knowledge store and the `cairn` CLI work today. Tool adapters, hooks,
> the hot-issues board and the eval harness are planned; see [ROADMAP.md](ROADMAP.md).
> Items below are marked _(planned)_ until they ship.

## Why another memory tool?

Memory layers for agents already exist (mem0, Letta, claude-mem, Basic Memory). cairn bets on
three things they don't combine:

1. **Cross-tool.** One brain, many agents. The same Markdown folder feeds Claude Code, Codex,
   Copilot and Cursor through thin adapters, so switching tools doesn't wipe what you've learned.
   _(The shared store and its importable API are built; the adapters are planned.)_
2. **Enforced process, not hopeful prompting.** Hooks gate the work: a _recall gate_ searches
   the brain before a task starts, a _capture gate_ asks for durable facts when a substantive
   task ends, and a _hot-issues board_ lists known tool failures with their workarounds.
   _(Planned. Issue entries and the stable `search --json` output the hooks will use are built.)_
3. **Measured value.** An A/B eval harness runs the same tasks with and without the brain and
   reports the difference, so "it helps" is a number, not a feeling. _(Planned.)_

## 60-second quickstart

```bash
git clone https://github.com/epiatakov/cairn && cd cairn
pip install -e .

# Search the example brain that ships with the repo
cairn search "windows glob" --brain examples/brain
cairn show ripgrep-glob-on-windows --brain examples/brain

# Start your own brain (./brain by default, or set CAIRN_BRAIN)
cairn init
cairn add issue --title "ripgrep glob on Windows" --tags ripgrep,windows \
  --body "cmd.exe ignores single quotes; use double quotes: rg -g \"*.py\""
cairn search "rg glob" --json      # stable JSON for hooks and scripts
cairn lint                         # frontmatter, duplicate ids, broken [[links]], near-duplicates
cairn index                        # regenerate brain/INDEX.md
```

## What a brain looks like

A brain is a folder you can read, grep, diff and commit:

```text
brain/
  facts/git-autocrlf-rewrites-line-endings.md
  issues/ripgrep-glob-on-windows.md
  skills/write-a-migration/SKILL.md
  notes/commit-message-style.md
  INDEX.md        # generated
  README.md
```

Each entry is Markdown with a small frontmatter block:

```markdown
---
id: ripgrep-glob-on-windows
type: issue                      # fact | skill | issue | note
title: ripgrep glob on Windows matches nothing when single-quoted
tags: [ripgrep, windows, glob, shell]
status: active                   # active | stale | archived
created: 2026-01-08
updated: 2026-04-11
links: [powershell-strips-quotes-in-native-arguments]
---

**Symptom:** ... **Cause:** ... **Workaround:** ... See also [[git-autocrlf-rewrites-line-endings]].
```

## Commands

| Command | What it does |
| --- | --- |
| `cairn init` | Create the folder layout and a README inside the brain |
| `cairn add <type> --title ... [--tags a,b] [--body TEXT \| --body - \| --body-file F]` | Add an entry with a slug id. Refuses near-duplicates (lists their ids) unless `--force` |
| `cairn search <query> [--type T] [--limit N] [--json]` | BM25 search over title (weighted highest), tags and body. Skips archived entries |
| `cairn show <id> [--json]` | Print one entry |
| `cairn list [--type T] [--status S] [--json]` | List entries |
| `cairn lint [--strict]` | Report invalid frontmatter, duplicate ids, broken links (errors) and near-duplicates (warnings). Exits non-zero on errors |
| `cairn index [--check]` | Regenerate `INDEX.md`, or check that it is current |

Every command accepts `--brain DIR`. Without it, cairn uses `$CAIRN_BRAIN`, then `./brain`.

The same operations are importable for adapters and future integrations:

```python
from cairn import Brain

brain = Brain.open("examples/brain")
for hit in brain.search("windows glob", limit=3):
    print(hit.entry.id, round(hit.score, 2), hit.snippet)
```

## Design principles

- **Plain files are the database.** Markdown with frontmatter, readable by people, git and any
  agent. No server, no lock-in, nothing to migrate when cairn changes.
- **One source of truth.** Tool-specific files are generated from the brain, never edited by hand.
- **Zero runtime dependencies.** The CLI is standard-library Python, so a hook can call it anywhere.
- **Boring retrieval first.** BM25 is fast, explainable and good enough for a personal brain.
  Embeddings get added only if the eval harness shows they pay off. See [docs/design.md](docs/design.md).
- **Process over prompts.** Recall and capture should be enforced by hooks, but only where they
  add value: a gate that fires on every trivial turn trains agents to game it.
- **Stable contracts.** `--json` output is versioned so hooks don't break on cosmetic changes.
- **Clean room.** Everything is original code built on public patterns. See [CLEAN_ROOM.md](CLEAN_ROOM.md).

## Development

```bash
pip install -e ".[dev]"
pytest
ruff check . && ruff format --check .
```

Contributor and agent conventions live in [AGENTS.md](AGENTS.md).

## License

[MIT](LICENSE)
