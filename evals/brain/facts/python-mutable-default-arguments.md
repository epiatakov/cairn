---
id: python-mutable-default-arguments
type: fact
title: Python evaluates default arguments once, so mutable defaults are shared between calls
tags: [python, functions, defaults]
status: active
created: 2026-03-03
updated: 2026-03-03
---

`def add_tag(tag, tags=[])` creates the list once, when the function is defined. Every call
that relies on the default appends to the same list, so values leak between calls.

```python
def add_tag(tag, tags=None):
    tags = [] if tags is None else tags
```
