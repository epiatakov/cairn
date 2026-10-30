---
id: gitignore-does-not-untrack-files
type: issue
title: Adding a path to .gitignore does not stop Git tracking an already committed file
tags: [git, gitignore, secrets]
status: active
created: 2026-03-07
updated: 2026-03-07
links: [rotate-a-leaked-secret]
---

**Symptom:** a file listed in `.gitignore` still shows up in `git status` and in diffs.

**Cause:** `.gitignore` only applies to untracked files. A file that is already committed
stays tracked.

**Workaround:** `git rm --cached path/to/file` keeps the local copy and removes it from the
index; commit that. If the file held credentials, they are still in history:
follow [[rotate-a-leaked-secret]].
