---
id: modulenotfound-wrong-interpreter
type: issue
title: ModuleNotFoundError right after pip install because pip belongs to another interpreter
tags: [python, pip, venv, imports]
status: active
created: 2026-02-26
updated: 2026-02-26
---

**Symptom:** `ModuleNotFoundError: No module named 'requests'` right after
`pip install requests` succeeded.

**Cause:** the `pip` on `PATH` installs into a different interpreter than the `python` that
runs the code, for example a system Python versus an activated virtual environment.

**Workaround:** always use `python -m pip install ...`, and check
`python -c "import sys; print(sys.executable)"`.
