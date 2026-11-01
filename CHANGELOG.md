# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[semantic versioning](https://semver.org/). Until 1.0, minor versions may change the CLI;
`--json` output stays versioned (see `docs/design.md`).

## [0.1.0] - 2026-11-01

First public release.

### Added

- Plain-Markdown brain: `facts/`, `skills/<id>/SKILL.md`, `issues/`, `notes/`, with a
  hand-written frontmatter parser (standard library only, no runtime dependencies).
- CLI: `cairn init`, `add` (refuses near-duplicates), `search` (BM25F, `--gate`, `--json`),
  `show`, `list`, `lint`, `index`.
- Recall: `cairn recall` with a trivial-prompt filter and a no-answer gate, and a Claude Code
  `UserPromptSubmit` hook mode (`--format claude-hook`) that never blocks a prompt.
- Tool adapters: `cairn install|uninstall claude|codex|copilot|cursor` and
  `cairn skills export|clean --tool claude|cursor`, with `--dry-run`. Only cairn's own
  blocks, hooks and marked files are ever changed.
- Hot-issues board: `cairn issue record|match|list|resolve|prune`, error fingerprints, a BM25
  fallback, and a Claude Code `PostToolUse` hook mode for `issue match`.
- Importable API: `cairn.Brain`, `cairn.Entry`, `cairn.search`.
- Evals (repository only, not installed): a retrieval eval with two baselines and a CI
  regression gate, and an agent A/B harness with a mock runner and a Claude Code runner.

[0.1.0]: https://github.com/epiatakov/cairn/releases/tag/v0.1.0
