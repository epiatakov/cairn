import pytest

from cairn import frontmatter
from cairn.frontmatter import FrontmatterError


def test_parses_scalars_lists_and_body():
    text = """---
id: git-crlf
title: "Quoted: with colon"
single: 'it''s'
tags: [git, "a, b", windows]
empty: []
block:
  - one
  - "two"
# a comment
---

Body line one.

Body line two.
"""
    meta, body = frontmatter.parse(text)
    assert meta == {
        "id": "git-crlf",
        "title": "Quoted: with colon",
        "single": "it's",
        "tags": ["git", "a, b", "windows"],
        "empty": [],
        "block": ["one", "two"],
    }
    assert body == "Body line one.\n\nBody line two."


def test_keeps_hash_in_plain_values():
    meta, _ = frontmatter.parse("---\ntitle: Issue #12 in C#\n---\n")
    assert meta["title"] == "Issue #12 in C#"


def test_handles_crlf_and_bom():
    meta, body = frontmatter.parse("﻿---\r\nid: x\r\n---\r\nhello\r\n")
    assert meta == {"id": "x"}
    assert body == "hello"


def test_escapes_in_double_quotes():
    meta, _ = frontmatter.parse('---\na: "say \\"hi\\" \\\\ ok"\n---\n')
    assert meta["a"] == 'say "hi" \\ ok'


@pytest.mark.parametrize(
    ("text", "message", "line"),
    [
        ("id: x\n", "must start with '---'", 1),
        ("---\nid: x\n", "missing closing '---'", 1),
        ("---\nid: x\nid: y\n---\n", "duplicate key 'id'", 3),
        ("---\njust text\n---\n", "expected 'key: value'", 2),
        ("---\ntags: [a, b\n---\n", "unterminated list", 2),
        ('---\ntitle: "open\n---\n', "unterminated double-quoted", 2),
        ('---\ntitle: "esc\\"\n---\n', "unterminated double-quoted", 2),
        ("---\n  indented: x\n---\n", "unexpected indentation", 2),
    ],
)
def test_reports_errors_with_line_numbers(text, message, line):
    with pytest.raises(FrontmatterError) as info:
        frontmatter.parse(text)
    assert message in info.value.message
    assert info.value.line == line


@pytest.mark.parametrize(
    "value",
    ["plain", "Fix: colon", "#hash", "[bracket", "true", "123", "", " padded ", 'a "q" \\ b'],
)
def test_dump_round_trips_scalars(value):
    meta, _ = frontmatter.parse(frontmatter.dump({"v": value}))
    assert meta == {"v": value}


def test_dump_round_trips_lists():
    tags = ["a", "with, comma", "[x]", "yes"]
    meta, _ = frontmatter.parse(frontmatter.dump({"tags": tags, "none": []}))
    assert meta == {"tags": tags, "none": []}


def test_dump_rejects_multiline_values():
    with pytest.raises(ValueError):
        frontmatter.dump({"title": "two\nlines"})
