---
id: npm-ci-lockfile-out-of-sync
type: issue
title: npm ci fails when package-lock.json is out of sync with package.json
tags: [npm, node, lockfile, ci]
status: active
created: 2026-01-22
updated: 2026-02-14
links: [lockfiles-pin-transitive-dependencies]
---

**Symptom:** CI fails with `npm ci can only install packages when your package.json and
package-lock.json are in sync` followed by lines like `Missing: left-pad@^1.3.0 from lock file`.

**Cause:** a dependency was added or changed in `package.json` without regenerating the lockfile.

**Workaround:** run `npm install` locally with the same npm major version as CI and commit the
updated `package-lock.json`. Do not switch CI to `npm install`: it hides the drift and makes
builds non-reproducible. See [[lockfiles-pin-transitive-dependencies]].
