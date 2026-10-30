---
id: python-venv-layout-differs-on-windows
type: fact
title: Python virtualenv executables live in Scripts on Windows, bin elsewhere
tags: [python, venv, windows]
status: active
created: 2026-01-20
updated: 2026-01-20
---

A virtual environment puts its interpreter and console scripts in `.venv\Scripts\` on
Windows and in `.venv/bin/` on Linux and macOS. Scripts that hard-code `.venv/bin/python`
break on Windows.

- Prefer `python -m pytest` over calling `.venv/bin/pytest` directly.
- In Python, `sysconfig.get_path("scripts")` returns the right folder for the running interpreter.
- PowerShell activates with `.venv\Scripts\Activate.ps1`.
