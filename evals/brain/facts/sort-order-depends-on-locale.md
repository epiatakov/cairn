---
id: sort-order-depends-on-locale
type: fact
title: sort and ls order depend on the locale; set LC_ALL=C for stable output
tags: [shell, sort, locale, reproducibility]
status: active
created: 2026-03-01
updated: 2026-03-01
---

`sort` collates with the current locale. `en_US.UTF-8` ignores case and punctuation on the
first pass, while the `C` locale compares bytes, so the same input sorts differently on a
laptop and on a CI runner, and generated files churn.

Use `LC_ALL=C sort` in scripts that produce committed or compared output. Python's `sorted()`
compares code points and does not depend on the locale.
