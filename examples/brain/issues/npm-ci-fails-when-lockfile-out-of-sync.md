---
id: npm-ci-fails-when-lockfile-out-of-sync
type: issue
title: npm ci fails when package.json and package-lock.json are out of sync
tags: [npm, node, ci]
status: active
created: 2026-03-05
updated: 2026-03-05
tool: npm
fingerprint: [84bf9461a99e, b360142f2b35]
state: workaround
occurrences: 4
first_seen: 2026-03-05
last_seen: 2026-09-18
workaround: Run npm install locally and commit the updated package-lock.json; do not switch CI to npm install.
---

**Symptom:** CI fails with "npm ci can only install packages when your package.json and
package-lock.json are in sync", although `npm install` works locally.

**Cause:** someone changed a dependency in `package.json` without committing the updated
lockfile. `npm ci` never rewrites the lockfile; it refuses to install instead.

**Workaround:** run `npm install` locally, commit `package-lock.json`, and push. Do not switch
CI to `npm install`: that hides the drift and makes builds non-reproducible.
