---
id: commit-message-style
type: note
title: Commit message style for this team
tags: [git, conventions]
status: active
created: 2026-01-05
updated: 2026-01-05
---

- Subject in the imperative mood, about 50 characters, no trailing period: "Add retry to upload client".
- Blank line, then a body that explains *why* the change was needed, wrapped at 72 columns.
- One logical change per commit, so `git revert` and [[bisect-a-regression]] stay useful.
- Reference the issue or ticket in the body, not the subject.
