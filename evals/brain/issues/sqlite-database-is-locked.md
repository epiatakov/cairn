---
id: sqlite-database-is-locked
type: issue
title: SQLite raises database is locked under concurrent access
tags: [sqlite, python, locking, concurrency]
status: active
created: 2026-01-26
updated: 2026-01-26
links: [sqlite-wal-mode-concurrency]
---

**Symptom:** `sqlite3.OperationalError: database is locked` (`SQLITE_BUSY`) when a web app,
worker or test suite opens the database from several connections.

**Cause:** another connection holds the write lock longer than the busy timeout. In
rollback-journal mode, readers also block during commits.

**Workaround:** enable WAL mode, keep write transactions short, set a busy timeout, and do not
share one connection between threads. See [[sqlite-wal-mode-concurrency]].
