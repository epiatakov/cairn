from cairn import Brain
from cairn.lint import lint

from .conftest import EXAMPLE_BRAIN


def codes(brain):
    return sorted((p.severity, p.code) for p in lint(brain))


def test_example_brain_is_clean():
    assert lint(Brain.open(EXAMPLE_BRAIN)) == []


def test_reports_invalid_frontmatter(brain):
    (brain.root / "facts" / "bad.md").write_text("no frontmatter here\n", encoding="utf-8")
    (brain.root / "notes" / "worse.md").write_text(
        "---\nid: worse\ntype: note\n---\n", encoding="utf-8"
    )
    problems = lint(brain)
    assert {p.code for p in problems} == {"invalid-entry"}
    assert {p.path.name for p in problems} == {"bad.md", "worse.md"}
    assert any("missing required field 'title'" in p.message for p in problems)


def test_reports_duplicate_ids(write_entry, brain):
    write_entry("same", type="fact", title="Alpha topic")
    write_entry("same", type="note", title="Completely different subject")
    assert codes(brain) == [("error", "duplicate-id"), ("error", "duplicate-id")]


def test_reports_broken_links(write_entry, brain):
    write_entry("a", title="Alpha", body="See [[b]] and [[missing]].", links=["gone"])
    write_entry("b", title="Beta")
    messages = sorted(p.message for p in lint(brain))
    assert messages == ["link to unknown id 'gone'", "link to unknown id 'missing'"]


def test_reports_near_duplicates_as_warnings(write_entry, brain):
    write_entry("one", title="Configure the HTTP proxy for pip")
    write_entry("two", title="Configure the HTTP proxy for pip!")
    write_entry("old", title="Configure the HTTP proxy for pip", status="archived")
    assert codes(brain) == [("warning", "near-duplicate")]


def test_reports_wrong_folder_and_id_mismatch(brain):
    path = brain.root / "facts" / "file-name.md"
    path.write_text(
        "---\nid: other\ntype: note\ntitle: T\ncreated: 2026-01-01\nupdated: 2026-01-01\n---\n",
        encoding="utf-8",
    )
    assert codes(brain) == [("error", "wrong-folder"), ("warning", "id-mismatch")]
