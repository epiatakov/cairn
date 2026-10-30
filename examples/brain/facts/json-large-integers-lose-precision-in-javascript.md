---
id: json-large-integers-lose-precision-in-javascript
type: fact
title: Large JSON integers lose precision in JavaScript
tags: [javascript, json, api]
status: active
created: 2026-02-14
updated: 2026-02-14
---

JavaScript numbers are IEEE 754 doubles, so integers above `Number.MAX_SAFE_INTEGER`
(2^53 - 1 = 9007199254740991) are rounded by `JSON.parse`. 64-bit database ids and
snowflake ids silently change value in the browser.

Send such ids as strings in API responses, and parse them with `BigInt` only where
arithmetic is needed.
