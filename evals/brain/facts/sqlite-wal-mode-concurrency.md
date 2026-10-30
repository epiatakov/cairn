---
id: sqlite-wal-mode-concurrency
type: fact
title: SQLite WAL mode lets readers proceed while a writer commits
tags: [sqlite, database, concurrency, wal]
status: active
created: 2026-01-25
updated: 2026-01-25
links: [sqlite-database-is-locked]
---

In the default rollback-journal mode, a writer blocks readers while it commits. In
write-ahead-log mode readers and the writer do not block each other; there is still only one
writer at a time.

```sql
PRAGMA journal_mode=WAL;   -- persistent: stored in the database file
PRAGMA busy_timeout=5000;  -- per connection: wait instead of failing at once
```

In Python, `sqlite3.connect(path, timeout=5)` sets the busy timeout. WAL does not work on
network file systems. See [[sqlite-database-is-locked]].
