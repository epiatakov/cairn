---
id: port-already-in-use
type: issue
title: Server fails to start with address already in use
tags: [networking, ports, eaddrinuse, linux]
status: active
created: 2026-03-12
updated: 2026-03-12
---

**Symptom:** `OSError: [Errno 98] Address already in use` or `Error: listen EADDRINUSE: :::3000`.

**Cause:** another process listens on the port, often a previous dev server that did not
exit, or the old socket is still in `TIME_WAIT`.

**Workaround:** find the owner with `lsof -i :3000` or `ss -ltnp`, stop it, and set
`SO_REUSEADDR` on servers that restart quickly.
