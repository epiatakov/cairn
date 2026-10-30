---
id: shell-script-bad-interpreter-crlf
type: issue
title: Shell script fails with bad interpreter because of CRLF line endings
tags: [shell, bash, line-endings, docker]
status: active
created: 2026-01-12
updated: 2026-01-12
---

**Symptom:** running a script in Linux or a container fails with
`/bin/bash^M: bad interpreter` or `/usr/bin/env: 'bash\r': No such file or directory`.

**Cause:** the script was checked out on Windows with CRLF line endings, so the shebang line
ends in a carriage return. See [[git-autocrlf-rewrites-line-endings]].

**Workaround:** add `*.sh text eol=lf` to `.gitattributes` and renormalize. For a single file,
`sed -i 's/\r$//' script.sh` (or `dos2unix`) fixes it immediately.
