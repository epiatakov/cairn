---
id: docker-copy-order-for-cache
type: fact
title: Copy dependency manifests before source code to keep the Docker layer cache
tags: [docker, dockerfile, cache, build-speed]
status: active
created: 2026-02-21
updated: 2026-02-21
---

Each instruction is cached until one of its inputs changes. With `COPY . .` before
`RUN pip install -r requirements.txt`, every source edit invalidates the install layer.

Copy the manifest first, install, then copy the rest:

```dockerfile
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
```

Add a `.dockerignore` so build output and `.git` do not invalidate the cache either.
