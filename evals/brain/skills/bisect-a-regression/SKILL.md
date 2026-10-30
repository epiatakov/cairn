---
id: bisect-a-regression
type: skill
title: Find the commit that introduced a regression with git bisect
tags: [git, debugging, regression]
status: active
created: 2026-03-18
updated: 2026-03-18
---

1. Write a script that exits 0 when the behavior is good and 1 when it is bad (125 skips a
   commit that cannot be tested).
2. `git bisect start <bad> <good>`.
3. `git bisect run ./check.sh` binary-searches the history and prints the first bad commit.
4. `git bisect reset` returns to where you started.

Keep the check script untracked so checkouts do not change it.
