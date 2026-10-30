---
id: git-autocrlf-rewrites-line-endings
type: fact
title: Git core.autocrlf rewrites line endings on checkout and commit
tags: [git, line-endings, windows, crlf]
status: active
created: 2026-01-10
updated: 2026-01-10
links: [shell-script-bad-interpreter-crlf]
---

With `core.autocrlf=true` (the default offered by the Git for Windows installer), Git converts
LF to CRLF when it checks files out and back to LF when it commits them. The repository stays
clean, but the working tree on Windows has CRLF files.

That breaks files that must keep LF when they leave the Windows working tree, such as shell
scripts copied into a Linux container. See [[shell-script-bad-interpreter-crlf]].

Prefer a committed `.gitattributes` over per-machine settings:

```
* text=auto
*.sh text eol=lf
```

After changing it, run `git add --renormalize .` and commit.
