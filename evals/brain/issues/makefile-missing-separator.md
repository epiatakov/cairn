---
id: makefile-missing-separator
type: issue
title: make fails with missing separator when recipes are indented with spaces
tags: [make, makefile, tabs, whitespace]
status: active
created: 2026-03-05
updated: 2026-03-05
---

**Symptom:** `Makefile:4: *** missing separator.  Stop.`

**Cause:** recipe lines must start with a tab character. An editor that converts tabs to
spaces breaks every recipe.

**Workaround:** indent recipes with a real tab and add an `.editorconfig` section
`[Makefile]` with `indent_style = tab`. GNU make 3.82+ can also change the prefix with
`.RECIPEPREFIX`.
