---
id: reproduce-a-flaky-test
type: skill
title: Reproduce and fix a flaky test
tags: [testing, flaky, ci, pytest]
status: active
created: 2026-03-28
updated: 2026-03-28
---

1. Run it in a loop until it fails: `for i in $(seq 50); do pytest -x tests/test_x.py || break; done`.
2. Randomize test order to expose shared state, and record the seed.
3. Look for time, network, ordering and concurrency assumptions.
4. Quarantine only with a tracked issue; fix the root cause, not the timeout.
