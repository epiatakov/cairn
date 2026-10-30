# Design

This document covers the v0.1 core: the data model, retrieval, deduplication and linting.
Planned pieces (adapters, hooks, hot-issues board, eval harness) are described only where they
shape today's decisions.

## Data model

A **brain** is a directory. Every entry is one UTF-8 Markdown file with a frontmatter block:

| Field | Required | Values |
| --- | --- | --- |
| `id` | yes | `lowercase-dash-slug`, unique across the brain |
| `type` | yes | `fact`, `skill`, `issue` or `note` |
| `title` | yes | one line |
| `created`, `updated` | yes | `YYYY-MM-DD`, with `updated >= created` |
| `tags` | no | list, e.g. `[git, windows]` |
| `status` | no (`active`) | `active`, `stale` or `archived` |
| `links` | no | list of ids. Body `[[id]]` and `[[id\|label]]` links count too |

Unknown keys are preserved, so adapters can attach their own metadata without schema changes.

**Types** describe the kind of knowledge, which later drives where adapters surface it:

- `fact`: a durable truth about a tool, system or codebase.
- `skill`: a procedure. It lives at `skills/<id>/SKILL.md`, following the public skills-folder
  pattern, so scripts or references can sit next to it and adapters can export the folder whole.
- `issue`: a known failure with symptom, cause and workaround. This is the raw material for the
  hot-issues board.
- `note`: anything else worth keeping.

**Status** replaces deletion. `stale` entries still show up in search, flagged, because old
knowledge is often still partly right. `archived` entries are hidden from search and dedupe but
stay on disk for history and links.

**Layout** is `facts/<id>.md`, `skills/<id>/SKILL.md`, `issues/<id>.md`, `notes/<id>.md`.
`INDEX.md` is generated and gives agents a cheap table of contents to read before searching.

### Why hand-parsed frontmatter

The runtime is standard-library only, so a hook can run `cairn` on any machine with Python and
nothing else. Python has no YAML parser in the standard library, so cairn parses a small,
documented subset: `key: value`, quoted strings, inline `[a, b]` lists, block `- item` lists
and full-line comments. Everything cairn writes is also valid YAML, so other tools (editors,
static-site generators) can still read the files. The parser rejects anything outside the
subset with a line number, instead of guessing.

## Retrieval: BM25F, no vector database in v1

`cairn search` ranks entries with BM25F: term frequencies are length-normalized per field
(title, tags, body), weighted 3 : 2 : 1, summed, then saturated once (`k1 = 1.2`, `b = 0.75`).
The tokenizer lowercases, folds accents, drops a short stopword list and folds simple plurals.

Why not embeddings and a vector store?

- **Scale.** A personal or team brain has hundreds to a few thousand entries. BM25 over that is
  milliseconds in pure Python, with no index to build or keep in sync.
- **The queries are lexical.** Agents search with error messages, tool names, flags and file
  names (`rg -g`, `SQLITE_BUSY`, `bad interpreter`). Exact-term matching is a strength here,
  not a weakness.
- **Explainable.** When recall misses, you can see why: the words aren't there. That makes the
  fix obvious (add a tag, edit the title), and it keeps the eval harness honest.
- **Zero dependencies and zero services.** No model download, no API key, no database process.
  This matters for hooks, which must be fast and must never fail closed.
- **Measure first.** An embedding re-ranker is on the roadmap as an option. It gets added only
  if the eval harness shows a real gain over BM25 on real tasks.

Known trade-off: synonyms and paraphrases ("line endings" vs "CRLF") need shared words. Tags are
the cheap fix, and the capture flow is expected to add them.

## Near-duplicate detection

Brains rot when the same fact is captured five times with small differences. `cairn add`
compares the new entry against every non-archived entry and refuses if any is too similar,
printing the matching ids (`--force` overrides). `cairn lint` reports similar pairs as warnings.

Similarity is the higher of two Jaccard scores over character 5-gram shingles:

1. **Titles only.** This catches a title-only capture that restates a longer existing entry,
   where comparing full texts would dilute the overlap.
2. **Title plus body.** This catches the same content under a reworded title.

The threshold is 0.6. On the example brain, unrelated pairs score at most about 0.15, and
reworded duplicates score 0.7 or more. Free paraphrases ("doesn't match" vs "matches nothing")
can score below the threshold. That is accepted for v1: a false refusal costs more trust than a
missed duplicate, which lint and review can still catch.

## Lint

`cairn lint` exits non-zero on errors and zero on warnings only (`--strict` fails on warnings).

| Severity | Code | Meaning |
| --- | --- | --- |
| error | `invalid-entry` | Frontmatter does not parse, or a field is missing or invalid |
| error | `unreadable` | The file is not readable as UTF-8 |
| error | `duplicate-id` | Two files share an id |
| error | `broken-link` | `links:` or a body `[[id]]` points to an unknown id |
| error | `wrong-folder` | The `type` does not match the folder the file is in |
| warning | `id-mismatch` | The id differs from the file name (or skill folder name) |
| warning | `near-duplicate` | Two live entries are above the similarity threshold |

`[[...]]` inside code spans and fenced blocks is ignored, so a shell test such as
`[[ -f x ]]` is never treated as a link.

## Machine interface

`--json` output on `search`, `show` and `list` is a contract for hooks and adapters. Every
payload carries `"version": 1`. Fields may be added, but changing or removing one requires a
version bump. Paths are relative to the brain and always use `/`.

The same operations are importable (`cairn.Brain`, `cairn.Entry`, `cairn.search`), so adapters
and a future MCP server don't have to shell out.

## Lessons

These came from running recall/capture processes with coding agents. They constrain the hook
design that comes next.

- **A capture or completion gate must skip trivial turns.** If every turn, including pure Q&A,
  "what does this flag do?" or a one-line fix, has to end with a capture block or a
  "nothing to capture" declaration, two things happen. Every answer gains boilerplate that
  users learn to scroll past. And agents learn to satisfy the gate mechanically, emitting the
  token that passes the check instead of thinking about what was learned. A gate that is
  always on stops measuring anything. The gate should fire only on substantive work: files
  changed, commands run, a failure diagnosed. On everything else it should stay silent.
- **Recall must be cheap or it gets skipped.** If the pre-task search is slow or noisy, agents
  and people route around it. That is one more reason for BM25 over a heavier stack, and for
  showing a few high-precision hits instead of a long list.
- **Duplicates are the main way a brain decays.** Refusing at write time is much cheaper than
  cleaning up later, so the check lives in `add` itself, not only in lint.
