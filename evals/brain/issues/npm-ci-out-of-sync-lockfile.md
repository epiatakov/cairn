---
id: npm-ci-out-of-sync-lockfile
type: issue
title: npm ci errors when the lock file and package.json disagree
tags: [npm, lockfile]
status: stale
created: 2025-10-05
updated: 2026-02-14
---

**Symptom:** `npm ci` refuses to install and says the lock file and package.json are not in sync.

**Workaround:** delete `node_modules` and `package-lock.json`, run `npm install`, commit.

(Stale: regenerating the whole lockfile upgrades every transitive dependency at once. See
[[npm-ci-lockfile-out-of-sync]] for the narrower fix.)
