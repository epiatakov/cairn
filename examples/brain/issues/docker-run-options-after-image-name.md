---
id: docker-run-options-after-image-name
type: issue
title: docker run options placed after the image name are run as the container command
tags: [docker, cli, flags]
status: active
created: 2026-04-14
updated: 2026-10-09
tool: docker
fingerprint: [75869bcb83ce]
state: workaround
occurrences: 5
first_seen: 2026-04-14
last_seen: 2026-10-09
workaround: Put every docker run option before the image name; anything after the image is the container's command and its arguments.
---

**Symptom:** `docker run my-image --rm -e DEBUG=1` fails with
`docker: Error response from daemon: failed to create task for container: ... exec: "--rm": executable file not found in $PATH: unknown.`

**Cause:** `docker run` reads its own options only up to the image name. Everything after the
image is passed to the container as the command, so `--rm` is executed as a program.

**Workaround:** move the options before the image: `docker run --rm -e DEBUG=1 my-image`. The
same rule applies to `docker exec` (options before the container name) and to many CLIs that
take a sub-command followed by its own arguments.
