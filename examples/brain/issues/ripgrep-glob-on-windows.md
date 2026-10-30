---
id: ripgrep-glob-on-windows
type: issue
title: ripgrep glob on Windows matches nothing when single-quoted
tags: [ripgrep, windows, glob, shell]
status: active
created: 2026-01-08
updated: 2026-04-11
links: [powershell-strips-quotes-in-native-arguments]
---

**Symptom:** `rg -g '*.py' TODO` finds nothing in `cmd.exe`, even though matching files exist.
The same command works in bash and in PowerShell.

**Cause:** `cmd.exe` does not treat single quotes as quoting, so ripgrep receives the glob
`'*.py'` with the quotes included, and no path matches it.

**Workaround:**

- Use double quotes, which every Windows shell understands: `rg -g "*.py" TODO`.
- Write path globs with forward slashes (`-g "src/**/*.ts"`); that form works on every platform.
- For language filters, `rg --type py TODO` avoids globs entirely.
