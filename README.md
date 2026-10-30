# cairn

[![CI](https://github.com/epiatakov/cairn/actions/workflows/ci.yml/badge.svg)](https://github.com/epiatakov/cairn/actions/workflows/ci.yml)

**One second brain for every coding agent.**

cairn is a plain-Markdown knowledge store plus the plumbing that makes coding agents
(Claude Code, Codex, GitHub Copilot, Cursor) **recall** relevant knowledge before they work
and **capture** durable facts after they work, all from one shared source of truth.

> **Status: early.** The knowledge store, the `cairn` CLI, tool adapters, the recall hook
> and the hot-issues board work today. The capture hook and the eval harness are planned; see
> [ROADMAP.md](ROADMAP.md).
> Items below are marked _(planned)_ until they ship.

## Why another memory tool?

Memory layers for agents already exist (mem0, Letta, claude-mem, Basic Memory). cairn bets on
three things they don't combine:

1. **Cross-tool.** One brain, many agents. The same Markdown folder feeds Claude Code, Codex,
   Copilot and Cursor through thin adapters, so switching tools doesn't wipe what you've learned.
   _(Built: `cairn install claude|codex|copilot|cursor`.)_
2. **Enforced process, not hopeful prompting.** Hooks gate the work: a _recall gate_ searches
   the brain before a task starts, a _capture gate_ asks for durable facts when a substantive
   task ends, and a _hot-issues board_ lists known tool failures with their workarounds.
   _(The recall gate is built for Claude Code, and so is the hot-issues board with its hook
   mode; the capture gate is planned.)_
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

## Connect your agents

Run these in your project. Each writes only what it owns and `cairn uninstall <tool>` removes
exactly that. Add `--dry-run` to see the diff first, `--project DIR` to target another folder,
and `--brain DIR` if the brain is not `./brain`.

```bash
cairn install claude    # .claude/settings.json recall hook + a block in CLAUDE.md
cairn install codex     # a block in AGENTS.md
cairn install copilot   # a block in .github/copilot-instructions.md
cairn install cursor    # .cursor/rules/cairn.mdc
cairn skills export --tool claude   # brain skills -> .claude/skills/<id>/SKILL.md
cairn skills export --tool cursor   # brain skills -> .cursor/rules/cairn-skill-<id>.mdc
```

| Tool | What `install` writes | Recall |
| --- | --- | --- |
| Claude Code | `UserPromptSubmit` hook in `.claude/settings.json` (merged, your hooks kept), block in `CLAUDE.md` | Automatic, every prompt |
| Codex | Block in `AGENTS.md` | The agent runs `cairn recall "<task>"` |
| GitHub Copilot | Block in `.github/copilot-instructions.md` | The agent runs `cairn recall "<task>"` |
| Cursor | `.cursor/rules/cairn.mdc` (always applied) | The agent runs `cairn recall "<task>"` |

Blocks sit between `<!-- cairn:begin ... -->` and `<!-- cairn:end -->` markers; text outside
them is never touched, and installing twice gives the same file. Files cairn owns whole carry
a "managed by cairn" line, and cairn refuses to overwrite a file without it. Skills export is a
sync: re-running it updates exported skills and deletes ones that left the brain.

**The recall hook** pipes each prompt into `cairn recall --format claude-hook`. When an entry
scores above the threshold, Claude sees a short block before it starts:

```text
Relevant entries from the cairn brain (read the file, or `cairn show <id>`):
- ripgrep-glob-on-windows (issue): ripgrep glob on Windows matches nothing when single-quoted
  Use double quotes, which every Windows shell understands: `rg -g "*.py" TODO`.
  brain/issues/ripgrep-glob-on-windows.md
```

It stays silent on chit-chat ("thanks", "go ahead") and prompts with fewer than two content
words, and when nothing scores at least 1.5. Tune it with `--min-words N` (0 turns the filter
off), `--min-score S` and `--limit N` on the hook command. On any error (no brain, bad input,
a bug) it prints nothing and exits 0, so it never blocks a prompt. Try it by hand:

```bash
cairn recall "rg glob fails on windows" --brain examples/brain
echo '{"prompt": "rg glob fails on windows"}' \
  | cairn recall --format claude-hook --brain examples/brain
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
| `cairn recall <prompt> [--limit N] [--min-score S] [--min-words N] [--format text\|json\|claude-hook]` | A few high-precision pointers for a task. Skips trivial prompts. `claude-hook` reads hook JSON on stdin and never fails |
| `cairn install <tool> [--project DIR] [--dry-run]` | Wire cairn into `claude`, `codex`, `copilot` or `cursor`. Idempotent |
| `cairn uninstall <tool> [--project DIR] [--dry-run]` | Remove exactly what `install` added |
| `cairn skills export\|clean --tool claude\|cursor [--project DIR] [--dry-run]` | Sync brain skills into the tool's folder, or remove the exported ones |
| `cairn issue record --tool T --error TEXT\|-` | Record a tool failure: a new issue, or +1 on the known one |
| `cairn issue match --error TEXT\|- [--json]` | The known issue and workaround for an error, if any |
| `cairn issue list [--since 7d] [--state S] [--tool T]` | The hot-issues board, ranked by recent occurrences |
| `cairn issue resolve <id> --workaround W \| --fix F` | Attach a workaround or a root-cause fix |
| `cairn issue prune --older-than 30d` | Mark issues that stopped recurring as stale |

Every command accepts `--brain DIR`. Without it, cairn uses `$CAIRN_BRAIN`, then `./brain`.

The same operations are importable for adapters and future integrations:

```python
from cairn import Brain

brain = Brain.open("examples/brain")
for hit in brain.search("windows glob", limit=3):
    print(hit.entry.id, round(hit.score, 2), hit.snippet)
```

## Hot-issues board

Agents keep hitting the same tool failures. The board records each one once, fingerprinted so
the same error on another machine or path still matches, and hands back the workaround the next
time it happens:

```bash
cairn issue match --brain examples/brain \
  --error "rg: C:\proj\src\*: The filename, directory name, or volume label syntax is incorrect"
cairn issue list --brain examples/brain     # hottest first
```

`cairn issue match --format claude-hook` plugs into a Claude Code `PostToolUse` hook and injects
the workaround after a failed tool call; it stays silent otherwise. Lifecycle, fingerprinting and
the hook contract are in [docs/hot-issues.md](docs/hot-issues.md).

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
