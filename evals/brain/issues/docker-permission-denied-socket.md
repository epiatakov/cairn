---
id: docker-permission-denied-socket
type: issue
title: Permission denied on the Docker daemon socket
tags: [docker, linux, permissions]
status: active
created: 2026-03-18
updated: 2026-03-18
---

**Symptom:** `Got permission denied while trying to connect to the Docker daemon socket at
unix:///var/run/docker.sock`.

**Cause:** the user is not in the `docker` group.

**Workaround:** `sudo usermod -aG docker $USER`, then log out and back in. Membership is
root-equivalent; rootless Docker avoids that.
