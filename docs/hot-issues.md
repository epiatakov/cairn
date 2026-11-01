# Hot-issues board

Agents hit the same tool and environment failures again and again: a glob that `cmd.exe` does
not expand, an option placed after a sub-command, a repository git refuses to trust. Each time,
the agent spends turns rediscovering the same fix. The hot-issues board records each failure
once, with its workaround, and shows that workaround the next time the same failure appears.

The board is built from ordinary `issue` entries in the brain's `issues/` folder, so it is plain
Markdown: readable, diffable and reviewable like the rest of the brain.

## Commands

| Command | What it does |
| --- | --- |
| `cairn issue record --tool T --error TEXT\|- [--workaround W] [--session S] [--json]` | Record one occurrence. Increments the matching issue, or adds a new one |
| `cairn issue match --error TEXT\|- [--json]` | Print the known issue for an error, with its workaround. Exit 1 when nothing matches |
| `cairn issue match --format claude-hook` | Read a Claude Code hook payload from stdin; print `additionalContext` on a match. Always exits 0 |
| `cairn issue list [--since 7d] [--state S] [--tool T] [--all] [--json]` | The board, hottest first. Default: active issues that are not fixed |
| `cairn issue resolve <id> --workaround W \| --fix F` | Attach a workaround (state `workaround`) or a root-cause fix (state `fixed`) |
| `cairn issue prune --older-than 30d [--dry-run]` | Mark active issues that have not recurred in that window as `stale` |

Durations are days or weeks: `7d`, `2w`.

```bash
cairn issue match --brain examples/brain \
  --error "rg: C:\proj\src\*: The filename, directory name, or volume label syntax is incorrect"
# ripgrep-wildcard-path-on-windows  (matched by fingerprint, 1.00)
#   ripgrep rejects a wildcard path on Windows with "volume label syntax is incorrect"
#   state: workaround, seen 9x
#   workaround:
#     Pass the directory and filter with a glob instead of a wildcard path, e.g. rg TODO C:\proj\src -g "*.py".
```

## Data

An issue is an `issue` entry with these extra frontmatter fields. All are optional, so
hand-written issues stay valid; `cairn lint` checks them when present (`invalid-issue`) and
warns when two live issues share a fingerprint (`duplicate-fingerprint`).

| Field | Meaning |
| --- | --- |
| `tool` | The tool or command that failed (`rg`, `git`, `docker`) |
| `fingerprint` | List of 12-hex-digit error fingerprints that identify this issue |
| `state` | `open`, `workaround` or `fixed` |
| `occurrences` | How many times the failure was recorded |
| `sessions` | The last 10 distinct session ids that recorded it |
| `first_seen`, `last_seen` | `YYYY-MM-DD` |
| `workaround` | One line: what to do when it happens |
| `fix` | One line: how the root cause was removed |

When `workaround` is missing, cairn falls back to the body's `**Workaround:**` section, so
existing issue entries work on the board unchanged. A new issue's body stores the error
excerpt with paths, ids and numbers already redacted, so no local paths end up in the brain.

## Fingerprints and matching

A fingerprint is a hash of the error's **signature**:

1. Keep the lines that carry the failure: the first two lines that look like errors (`error`,
   `fatal`, `denied`, `not found`, `cannot`, ...), skipping near-empty lines such as `npm ERR!`.
2. Replace volatile parts with placeholders: Windows, UNC and POSIX paths become `{path}`; URLs,
   UUIDs, hex ids, timestamps and temp names get their own placeholders; loose numbers such as
   line numbers become `{n}`. Numbers that identify the failure stay: `exit code 127`,
   `HTTP 404`, `os error 123`.
3. Drop quotes and trailing punctuation, lowercase, collapse whitespace.

So `rg: C:\proj\src\*: ...` on one machine and `rg: D:\work\lib\*: ...` on another share a
fingerprint, while `ValueError` and `TypeError` with the same message do not.

`match` first looks for an exact fingerprint. If none matches, it falls back to BM25 over issue
entries and accepts the best hit only if it shares at least three of the error's words and
those words carry at least 60% of the error's IDF weight. This keeps short, generic errors
(`permission denied`) from matching a loosely related issue. When `record` matches by similarity
(at a stricter 75%), it adds the new fingerprint to the issue, so the next occurrence of that
variant matches exactly.

## Lifecycle

```text
open --resolve --workaround--> workaround --resolve --fix--> fixed
  \______________________________________________________________/
                         |
           not seen for N days: prune --> status: stale
```

- **open**: recorded, no known workaround yet.
- **workaround**: there is a way around it. Most issues live here.
- **fixed**: the root cause was removed. Fixed issues leave the default board.
- **stale**: `prune` sets `status: stale` on issues that have not recurred. They leave the
  default board but keep matching, because old knowledge is often still partly right.

Recurrence moves an issue back: recording a `stale` issue makes it `active` again, and
recording a `fixed` issue reopens it (to `workaround` if one is known, else `open`), keeping the
`fix` text for reference. A fix that did not hold is worth knowing about.

## Hot score

`list` orders issues by `occurrences * 0.5 ** (days_since_last_seen / 7)`: occurrences, halved
for every week since the issue was last seen. A failure that hit five times this week outranks
one that hit twenty times two months ago.

## Claude Code hook

`cairn issue match --format claude-hook` reads a `PostToolUse` (or `PostToolUseFailure`) hook
payload from stdin. If the tool call failed (a failure event, an `error` field, a non-zero exit
code, or error-looking `stderr`) and the error matches a known issue, it prints:

```json
{"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": "cairn hot-issues board: this failure matches known issue '...' ..."}}
```

On no match, a successful tool call, unparsable input, a missing brain or any other error, it
prints nothing and exits 0. A hook must never break the agent's turn. A relative `--brain`
(or the default `./brain`) is resolved against the `cwd` in the payload.

`cairn install claude` does not add this hook yet (it is on the roadmap), so add it to
`.claude/settings.json` by hand, next to the recall hook that `install` writes:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Bash",
        "hooks": [{ "type": "command", "command": "cairn issue match --format claude-hook" }]
      }
    ]
  }
}
```

## Design note: a cache of fixes, not a log

The board is deliberately not a failure log. A log grows with every failure and nobody reads
it; the board grows only when a *new kind* of failure appears, and every entry earns its place
by carrying a workaround the next agent can use. That is why `record` increments instead of
appending, why fingerprints strip everything that differs between machines, and why `prune`
retires issues that stop recurring.

The counts are a signal, not just a ranking. An issue that keeps climbing the board while
sitting in state `workaround` means agents keep paying for the same detour. That is the cue to
fix the root cause (pin the dependency, add the `.gitattributes` rule, change the script), then
`cairn issue resolve <id> --fix ...`. A healthy board trends toward `fixed` and `stale`, not
toward longer workarounds.
