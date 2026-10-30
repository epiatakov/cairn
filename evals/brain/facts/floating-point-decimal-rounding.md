---
id: floating-point-decimal-rounding
type: fact
title: Binary floating point cannot represent most decimal fractions exactly
tags: [floats, precision, money, python, javascript]
status: active
created: 2026-02-06
updated: 2026-02-06
---

`0.1 + 0.2 == 0.30000000000000004` in Python, JavaScript and most other languages, because
0.1 has no exact binary representation.

- Store money as integer cents or use `decimal.Decimal`.
- Round only for display.
- Compare floats with a tolerance, for example `math.isclose`.
