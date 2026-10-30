---
id: utf8-bom-breaks-shebang
type: fact
title: A UTF-8 byte order mark before the shebang breaks script execution
tags: [encoding, bom, utf-8, shell]
status: active
created: 2026-01-14
updated: 2026-01-14
---

Some Windows editors save UTF-8 with a byte order mark (bytes `EF BB BF`). The kernel only
honours a shebang when `#!` are the first two bytes of the file, so a BOM turns
`#!/bin/bash` into an unknown command: `#!/bin/bash: No such file or directory` or
`exec format error`.

Strict JSON parsers reject a BOM too (Python: `JSONDecodeError: Unexpected UTF-8 BOM`).

Fix: save the file as UTF-8 without BOM. In Python, read such files with
`encoding="utf-8-sig"`, which strips the BOM if present.
