---
id: token-expiry-wrong-outside-utc
type: issue
title: Token expiry is off by hours on machines not set to UTC
tags: [python, datetime, timezone, auth]
status: active
created: 2026-02-16
updated: 2026-02-16
links: [python-datetime-utcnow-naive]
---

**Symptom:** tokens look expired as soon as they are issued, or live hours too long, on
developer laptops. Tests pass in CI.

**Cause:** the expiry is computed with `datetime.utcnow().timestamp()`, which applies the
local UTC offset a second time. See [[python-datetime-utcnow-naive]].

**Workaround:** compute with aware datetimes, `datetime.now(timezone.utc)`, or with
`time.time()`.
