---
id: too-many-open-files
type: issue
title: Too many open files errors come from the per-process descriptor limit
tags: [linux, macos, ulimit, file-descriptors]
status: active
created: 2026-03-14
updated: 2026-03-14
---

**Symptom:** `OSError: [Errno 24] Too many open files` or `EMFILE` in file watchers, test
runners or servers.

**Cause:** the soft limit on open descriptors is low (often 256 on macOS, 1024 on Linux), or
the program leaks handles.

**Workaround:** check with `ulimit -n` and raise the soft limit; close files with `with`
blocks; find leaks with `lsof -p <pid>`.
