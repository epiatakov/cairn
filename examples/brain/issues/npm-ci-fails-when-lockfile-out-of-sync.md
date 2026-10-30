---
id: npm-ci-fails-when-lockfile-out-of-sync
type: issue
title: npm ci fails when package.json and package-lock.json are out of sync
tags: [npm, node, ci]
status: active
created: 2026-03-05
updated: 2026-03-05
---

**Symptom:** CI fails with "npm ci can only install packages when your package.json and
package-lock.json are in sync", although `npm install` works locally.

**Cause:** someone changed a dependency in `package.json` without committing the updated
lockfile. `npm ci` never rewrites the lockfile; it refuses to install instead.

**Workaround:** run `npm install` locally, commit `package-lock.json`, and push. Do not switch
CI to `npm install`: that hides the drift and makes builds non-reproducible.
