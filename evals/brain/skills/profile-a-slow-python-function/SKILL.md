---
id: profile-a-slow-python-function
type: skill
title: Profile a slow Python function
tags: [python, performance, profiling]
status: active
created: 2026-03-26
updated: 2026-03-26
---

1. Reproduce with a fixed input and time it with `python -m timeit` or `time.perf_counter`.
2. `python -m cProfile -o out.prof script.py`, then inspect with `pstats` sorted by
   cumulative time.
3. For a running process, `py-spy top --pid <pid>` samples without restarting it.
4. Optimize the top entry only, then measure again.
