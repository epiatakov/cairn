---
id: lockfiles-pin-transitive-dependencies
type: fact
title: Lockfiles pin the whole dependency tree while manifests only declare ranges
tags: [dependencies, lockfile, npm, pip, poetry]
status: active
created: 2026-02-02
updated: 2026-02-02
---

Manifests (`package.json`, `pyproject.toml`) declare version ranges for direct dependencies.
Lockfiles (`package-lock.json`, `poetry.lock`, `uv.lock`) record the exact resolved version and
hash of every package, including transitive ones, so installs are reproducible.

Commit lockfiles for applications. For libraries, also test against a fresh resolution so
users with newer dependencies are covered.
