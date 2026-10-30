---
id: shell-script-bad-interpreter-crlf
type: issue
title: Shell script fails with bad interpreter because of CRLF line endings
tags: [shell, bash, crlf, line-endings, docker]
status: active
created: 2026-01-12
updated: 2026-02-01
---

**Symptom:** running a script on Linux or in a container fails with
`/bin/bash^M: bad interpreter: No such file or directory`,
`/usr/bin/env: 'bash\r': No such file or directory` or `$'\r': command not found`.

**Cause:** the script has CRLF line endings, usually from a Windows checkout, so the shebang
line ends in a carriage return. See [[git-autocrlf-rewrites-line-endings]].

**Workaround:** strip the carriage returns (`sed -i 's/\r$//' script.sh` or `dos2unix`) and
add `*.sh text eol=lf` to `.gitattributes` so the fix survives the next checkout.
