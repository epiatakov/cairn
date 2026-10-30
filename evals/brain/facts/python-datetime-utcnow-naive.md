---
id: python-datetime-utcnow-naive
type: fact
title: datetime.utcnow() returns a naive datetime that timestamp() treats as local time
tags: [python, datetime, timezone, utc]
status: active
created: 2026-02-15
updated: 2026-02-15
---

`datetime.utcnow()` returns the current UTC time with `tzinfo=None`. Calling `.timestamp()` on
a naive datetime assumes it is local time, so the epoch value is off by the machine's UTC
offset. The bug is invisible on servers and CI runners that run in UTC.

Use aware datetimes: `datetime.now(timezone.utc)`. `utcnow()` is deprecated since Python 3.12.
