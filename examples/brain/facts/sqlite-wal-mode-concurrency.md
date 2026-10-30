---
id: sqlite-wal-mode-concurrency
type: fact
title: SQLite WAL mode lets readers and one writer work at the same time
tags: [sqlite, database, concurrency]
status: active
created: 2026-02-03
updated: 2026-02-03
---

`PRAGMA journal_mode=WAL;` switches SQLite to write-ahead logging. The setting is stored in
the database file, so it only needs to run once.

- Readers no longer block the writer, and the writer no longer blocks readers.
- There is still only one writer at a time. Set `PRAGMA busy_timeout=5000;` so a second
  writer waits instead of failing at once with `SQLITE_BUSY`.
- WAL needs shared memory, so it does not work on network file systems.
