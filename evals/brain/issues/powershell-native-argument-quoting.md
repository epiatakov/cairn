---
id: powershell-native-argument-quoting
type: issue
title: PowerShell strips embedded double quotes when calling native executables
tags: [powershell, windows, quoting, json]
status: active
created: 2026-01-16
updated: 2026-01-16
---

**Symptom:** passing JSON such as `'{"name":"x"}'` to a native program from PowerShell arrives
as `{name:x}`, and the program fails to parse it.

**Cause:** Windows PowerShell 5.1 and PowerShell before 7.3 did not escape embedded double
quotes when building the command line for native executables.

**Workaround:** on PowerShell 7.3+, set `$PSNativeCommandArgumentPassing = 'Standard'`.
Otherwise escape the quotes as `\"`, or pass the data through a file or stdin.
