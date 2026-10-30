---
id: powershell-strips-quotes-in-native-arguments
type: issue
title: PowerShell strips embedded double quotes from native command arguments
tags: [powershell, windows, shell, json]
status: active
created: 2026-02-21
updated: 2026-02-21
---

**Symptom:** `tool --data '{"name": "x"}'` works in bash, but from Windows PowerShell 5.1
the program receives `{name: x}` and fails to parse JSON.

**Cause:** before PowerShell 7.3, embedded double quotes in arguments passed to external
programs were not escaped. PowerShell 7.3 and later pass them through correctly
(see `$PSNativeCommandArgumentPassing`).

**Workaround:**

- Pass structured data through a file or stdin instead of an argument.
- On 5.1, escape the quotes for the target program: `'{\"name\": \"x\"}'`.
- Or run the command from PowerShell 7.3+.
