---
id: rotate-a-leaked-secret
type: skill
title: Rotate a secret that was committed to a repository
tags: [security, secrets, git, credentials]
status: active
created: 2026-03-20
updated: 2026-03-20
---

1. Revoke or rotate the credential first. Assume it is compromised the moment it was pushed.
2. Check the provider's access logs for use since the commit.
3. Remove it from the working tree and stop tracking it (see [[gitignore-does-not-untrack-files]]).
4. If required, rewrite history with `git filter-repo` and coordinate the force-push.
5. Add a secret scanner to pre-commit and CI.
