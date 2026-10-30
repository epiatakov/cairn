---
id: git-dubious-ownership-in-container
type: issue
title: git refuses to work in a repository owned by another user (dubious ownership)
tags: [git, docker, ci, permissions]
status: active
created: 2026-05-20
updated: 2026-10-24
tool: git
fingerprint: [665378bc801b]
state: workaround
occurrences: 7
first_seen: 2026-05-20
last_seen: 2026-10-24
workaround: Mark the checkout as safe with git config --global --add safe.directory <repo-path>, or run git as the user that owns the files.
---

**Symptom:** inside a container or CI job, every git command fails with
`fatal: detected dubious ownership in repository at '/workspace/app'`.

**Cause:** since Git 2.35.2, git refuses to operate in a repository whose files are owned by a
different user than the one running git. Bind-mounted checkouts in containers often trigger it.

**Workaround:** trust that one path with
`git config --global --add safe.directory /workspace/app`, or run the container with the same
user id as the owner of the files. Avoid `safe.directory '*'` on shared machines: it turns the
check off for every repository.
