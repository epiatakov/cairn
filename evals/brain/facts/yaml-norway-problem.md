---
id: yaml-norway-problem
type: fact
title: YAML 1.1 parsers read unquoted no, yes, on and off as booleans
tags: [yaml, config, booleans, parsing]
status: active
created: 2026-02-12
updated: 2026-02-12
---

YAML 1.1 loaders, including PyYAML's default, treat `yes`, `no`, `on`, `off`, `y` and `n`
(in any case) as booleans. `country: NO`, Norway's ISO code, loads as `False`. Version
strings are affected too: `version: 1.10` loads as the float `1.1`.

Quote such values: `country: "NO"`, `version: "1.10"`. YAML 1.2 only treats `true` and
`false` as booleans, but many tools still implement 1.1.
