---
id: bisect-a-regression
type: skill
title: Find the commit that introduced a regression with git bisect
tags: [git, debugging, regression]
status: active
created: 2026-03-18
updated: 2026-03-18
---

Use this when something worked in an older commit and is broken now.

1. Write a script that exits 0 when the behavior is good and 1 when it is bad. Exit 125 means
   "cannot test this commit" (for example, it does not build), and bisect skips it.
2. Start: `git bisect start <bad-commit> <good-commit>`.
3. Automate: `git bisect run ./check.sh`. Git binary-searches the history and prints the
   first bad commit.
4. Finish with `git bisect reset` to return to where you started.

Keep the check script outside the repository, or untracked, so checkouts do not change it.
Small, focused commits ([[commit-message-style]]) make the result far easier to act on.
