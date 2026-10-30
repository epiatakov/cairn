---
id: ripgrep-wildcard-path-on-windows
type: issue
title: ripgrep rejects a wildcard path on Windows with "volume label syntax is incorrect"
tags: [ripgrep, windows, glob, path]
status: active
created: 2026-02-03
updated: 2026-10-27
links: [ripgrep-glob-on-windows]
tool: rg
fingerprint: [b33b8d120f94, c4488d7c5820]
state: workaround
occurrences: 9
first_seen: 2026-02-03
last_seen: 2026-10-27
workaround: Pass the directory and filter with a glob instead of a wildcard path, e.g. rg TODO C:\proj\src -g "*.py".
---

**Symptom:** `rg TODO C:\proj\src\*` fails with
`rg: C:\proj\src\*: The filename, directory name, or volume label syntax is incorrect. (os error 123)`.

**Cause:** Windows shells do not expand `*` in arguments, so ripgrep receives the wildcard as a
literal path. `*` is not a valid character in a Windows file name, so the OS rejects the path
before ripgrep can search anything.

**Workaround:**

- Pass the directory itself; ripgrep already searches it recursively: `rg TODO C:\proj\src`.
- Narrow by file name with a glob, not a path: `rg TODO C:\proj\src -g "*.py"`.
- Or filter by language: `rg TODO C:\proj\src --type py`.

See also [[ripgrep-glob-on-windows]] for quoting globs in `cmd.exe`.
