---
id: ripgrep-glob-single-quotes-windows
type: issue
title: ripgrep glob matches nothing on Windows cmd when single-quoted
tags: [ripgrep, rg, glob, windows, cmd, quoting]
status: active
created: 2026-01-08
updated: 2026-03-11
---

**Symptom:** `rg --files -g '*.py'` lists nothing (or `No files were searched`) in `cmd.exe`
or a `.bat` file, but works in bash.

**Cause:** `cmd.exe` does not treat single quotes as quoting, so ripgrep receives the glob
`'*.py'` with the quote characters in it, which matches no file name.

**Workaround:** use double quotes, which work in cmd, PowerShell and bash: `rg -g "*.py"`.
See also [[powershell-native-argument-quoting]].
