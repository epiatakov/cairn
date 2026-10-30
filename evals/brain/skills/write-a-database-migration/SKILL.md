---
id: write-a-database-migration
type: skill
title: Write a zero-downtime database schema migration
tags: [database, migrations, sql, deploy]
status: active
created: 2026-03-24
updated: 2026-03-24
---

Use expand and contract:

1. Expand: add new columns as nullable, or new tables, without touching the old ones.
2. Backfill in small batches.
3. Deploy code that writes both and reads the new shape.
4. Contract: add constraints, then drop old columns in a later release.

Keep every step reversible and test it on a copy of production-sized data.
