import pytest

from cairn.model import Entry, EntryError, body_links, normalize_tags, slugify

VALID = """---
id: sample
type: fact
title: A sample fact
tags: [a, b]
created: 2026-01-01
updated: 2026-01-02
owner: me
---
Body with [[other-id]].
"""


def test_from_markdown_reads_fields_and_keeps_unknown_keys():
    entry = Entry.from_markdown(VALID)
    assert (entry.id, entry.type, entry.title) == ("sample", "fact", "A sample fact")
    assert entry.tags == ["a", "b"]
    assert entry.status == "active"
    assert entry.extra == {"owner": "me"}
    assert entry.outgoing_links() == ["other-id"]


def test_to_markdown_round_trips():
    entry = Entry.from_markdown(VALID)
    assert Entry.from_markdown(entry.to_markdown()) == entry


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (("type: fact", "type: memo"), "invalid type 'memo'"),
        (("id: sample", "id: Not Valid"), "invalid id"),
        (("created: 2026-01-01", "created: yesterday"), "invalid created date"),
        (("created: 2026-01-01", "created: 20260101"), "invalid created date"),
        (("updated: 2026-01-02", "updated: 2026-02-30"), "invalid updated date"),
        (("updated: 2026-01-02", "updated: 2025-12-31"), "earlier than 'created'"),
        (("tags: [a, b]", "tags: a"), "'tags' must be a list"),
        (("title: A sample fact\n", ""), "missing required field 'title'"),
        (("owner: me", "status: gone"), "invalid status 'gone'"),
    ],
)
def test_validation_errors(change, message):
    with pytest.raises(EntryError) as info:
        Entry.from_markdown(VALID.replace(*change))
    assert any(message in p for p in info.value.problems)


def test_body_links_ignore_code_and_support_labels():
    body = """See [[alpha]] and [[beta|the beta entry]].

`[[not-a-link]]` inline, and bash tests like [[ -f x ]] are ignored.

```bash
[[ -n "$x" ]] && echo [[gamma]]
```
"""
    assert body_links(body) == ["alpha", "beta"]


@pytest.mark.parametrize(
    ("title", "slug"),
    [
        ("ripgrep glob on Windows", "ripgrep-glob-on-windows"),
        ("  Café: naïve résumé!! ", "cafe-naive-resume"),
        ("C# & .NET 8", "c-net-8"),
        ("!!!", ""),
    ],
)
def test_slugify(title, slug):
    assert slugify(title) == slug


def test_slugify_cuts_at_word_boundary():
    slug = slugify("word " * 30, max_length=20)
    assert slug == "word-word-word-word"


def test_normalize_tags():
    assert normalize_tags(["Git, windows", "git", " ", "CI"]) == ["git", "windows", "ci"]
