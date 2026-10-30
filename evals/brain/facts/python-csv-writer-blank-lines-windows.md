---
id: python-csv-writer-blank-lines-windows
type: fact
title: Python csv writer adds blank rows on Windows unless the file is opened with newline=''
tags: [python, csv, windows, line-endings]
status: active
created: 2026-01-20
updated: 2026-01-20
---

The `csv` module writes `\r\n` row terminators itself. If the file is opened in text mode
without `newline=""`, Windows translates each `\n` again, so rows end in `\r\r\n` and
spreadsheet programs show an empty row between every record.

Always open CSV files with `open(path, "w", newline="", encoding="utf-8")`, for reading too.
