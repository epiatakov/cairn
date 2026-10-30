---
id: git-autocrlf-rewrites-line-endings
type: fact
title: Git autocrlf rewrites line endings on Windows checkouts
tags: [git, windows, line-endings]
status: active
created: 2026-01-12
updated: 2026-03-02
links: [shell-script-bad-interpreter-crlf]
---

With `core.autocrlf=true` (the Git for Windows installer default), Git converts LF to
CRLF when it checks files out and back to LF when it commits them. The repository stays
clean, but the working tree does not match what Linux CI sees.

Pin line endings in the repository instead of relying on each machine's config:

```gitattributes
* text=auto
*.sh text eol=lf
*.bat text eol=crlf
```

After adding `.gitattributes` to an existing repo, run `git add --renormalize .` once.
