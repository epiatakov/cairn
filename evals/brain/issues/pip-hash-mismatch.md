---
id: pip-hash-mismatch
type: issue
title: pip install fails because packages do not match the hashes in the requirements file
tags: [pip, python, hashes, requirements]
status: active
created: 2026-02-24
updated: 2026-02-24
---

**Symptom:** `ERROR: THESE PACKAGES DO NOT MATCH THE HASHES FROM THE REQUIREMENTS FILE.`

**Cause:** in hash-checking mode (enabled by `--require-hashes` or by any `--hash` in the
file) every package, including transitive ones, needs a matching hash. A dependency without
a hash, a different platform wheel, or a proxy serving a different file triggers it.

**Workaround:** regenerate the file with `pip-compile --generate-hashes` on the target
platform, and clear a possibly corrupt cache with `pip cache purge`.
