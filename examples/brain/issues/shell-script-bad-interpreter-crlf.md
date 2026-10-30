---
id: shell-script-bad-interpreter-crlf
type: issue
title: Shell script fails with bad interpreter because of CRLF line endings
tags: [shell, bash, line-endings, docker]
status: active
created: 2026-01-12
updated: 2026-01-12
tool: bash
fingerprint: [794c0a7b2a30, 856636e910ef]
state: workaround
occurrences: 6
first_seen: 2026-01-12
last_seen: 2026-10-21
workaround: Add "*.sh text eol=lf" to .gitattributes and renormalize; for one file, run dos2unix or sed -i 's/\r$//'.
---

**Symptom:** running a script in Linux or a container fails with
`/bin/bash^M: bad interpreter` or `/usr/bin/env: 'bash\r': No such file or directory`.

**Cause:** the script was checked out on Windows with CRLF line endings, so the shebang line
ends in a carriage return. See [[git-autocrlf-rewrites-line-endings]].

**Workaround:** add `*.sh text eol=lf` to `.gitattributes` and renormalize. For a single file,
`sed -i 's/\r$//' script.sh` (or `dos2unix`) fixes it immediately.
