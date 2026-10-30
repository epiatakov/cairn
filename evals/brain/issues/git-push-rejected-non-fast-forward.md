---
id: git-push-rejected-non-fast-forward
type: issue
title: git push is rejected as non-fast-forward when the remote has new commits
tags: [git, push, rebase]
status: active
created: 2026-03-16
updated: 2026-03-16
---

**Symptom:** `! [rejected] main -> main (fetch first)` or `Updates were rejected because the
tip of your current branch is behind its remote counterpart`.

**Workaround:** `git pull --rebase`, resolve conflicts, then push. Never force-push a shared
branch; on your own branch after a rebase, use `git push --force-with-lease`.
