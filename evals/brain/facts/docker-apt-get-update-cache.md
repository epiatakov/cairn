---
id: docker-apt-get-update-cache
type: fact
title: Run apt-get update and apt-get install in the same Dockerfile RUN step
tags: [docker, dockerfile, apt, cache]
status: active
created: 2026-02-20
updated: 2026-02-20
---

A separate `RUN apt-get update` line becomes its own cached layer. When the install line
changes later, Docker reuses the old package index, and the build fails with
`E: Unable to locate package` or 404 errors from the mirror.

```dockerfile
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*
```
