---
id: python-venv-layout-differs-on-windows
type: fact
title: Python virtual environments use Scripts instead of bin on Windows
tags: [python, venv, virtualenv, windows]
status: active
created: 2026-02-10
updated: 2026-02-10
---

On Linux and macOS a virtual environment has `.venv/bin/python` and `.venv/bin/activate`. On
Windows it has `.venv\Scripts\python.exe`, `Scripts\activate.bat` and `Scripts\Activate.ps1`.

Scripts that hardcode `bin/python` fail on Windows. Choose the folder with
`"Scripts" if os.name == "nt" else "bin"`, or ask the interpreter with
`sysconfig.get_path("scripts")`.
