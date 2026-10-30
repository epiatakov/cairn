---
id: write-a-migration
type: skill
title: Write a database schema migration safely
tags: [database, migration, sql, deploy]
status: active
created: 2026-02-10
updated: 2026-04-02
---

Use this when a change needs a new table, column, index or constraint.

1. **Never edit a migration that has been applied anywhere.** Add a new one.
2. **Expand, then contract.** Ship the additive change first (new nullable column, new
   table), deploy code that writes both shapes, backfill, and only then drop the old shape
   in a later migration.
3. **Keep schema and data changes apart.** Backfill large tables in batches outside the
   schema migration so locks stay short.
4. **Add `NOT NULL` in steps:** add the column as nullable, backfill, then add the constraint.
5. **Build indexes without blocking writes.** On PostgreSQL use `CREATE INDEX CONCURRENTLY`,
   which cannot run inside a transaction, so put it in its own migration.
6. **Write the down migration**, or state in the file that the change is irreversible.
7. Run up, down and up again against a copy of production-sized data before merging.
