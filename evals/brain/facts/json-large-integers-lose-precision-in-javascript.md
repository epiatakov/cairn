---
id: json-large-integers-lose-precision-in-javascript
type: fact
title: JSON integers above 2^53 lose precision when parsed in JavaScript
tags: [json, javascript, integers, precision, api]
status: active
created: 2026-02-05
updated: 2026-02-05
---

`JSON.parse` turns every number into an IEEE-754 double. Integers above
`Number.MAX_SAFE_INTEGER` (2^53 - 1 = 9007199254740991) are rounded silently, so 64-bit
database ids or snowflake ids change by a few units on the client.

Fix on the producer side: serialize such ids as strings (`"id": "9223372036854775807"`).
A BigInt-aware JSON parser on the client also works, but every consumer needs it.
