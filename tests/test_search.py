from cairn import Brain
from cairn.search import Index, tokenize

from .conftest import EXAMPLE_BRAIN


def test_tokenize_lowercases_drops_stopwords_and_folds_plurals():
    assert tokenize("The Windows globs in a Policies file") == ["window", "glob", "policy", "file"]
    assert tokenize("status class analysis") == ["status", "class", "analysis"]


def test_title_match_outranks_body_match(write_entry, brain):
    write_entry("in-body", title="Unrelated heading", body="Notes on docker volumes and more.")
    write_entry("in-title", title="Docker volumes", body="Some text about storage.")
    hits = brain.search("docker volumes")
    assert [h.entry.id for h in hits] == ["in-title", "in-body"]


def test_rare_terms_weigh_more(write_entry, brain):
    write_entry("common-1", title="python packaging")
    write_entry("common-2", title="python typing")
    write_entry("rare", title="python tomllib")
    assert brain.search("python tomllib")[0].entry.id == "rare"


def test_skips_archived_and_filters_type(write_entry, brain):
    write_entry("old", title="git hooks", status="archived")
    write_entry("live", type="issue", title="git hooks fail")
    write_entry("skill", type="skill", title="git hooks setup")
    assert [h.entry.id for h in brain.search("git hooks")] == ["live", "skill"]
    assert [h.entry.id for h in brain.search("git hooks", type="skill")] == ["skill"]
    assert len(brain.search("git hooks", include_archived=True)) == 3


def test_limit_and_no_match(write_entry, brain):
    for i in range(5):
        write_entry(f"e{i}", title=f"cache note {i}")
    assert len(brain.search("cache", limit=2)) == 2
    assert brain.search("nonexistentword") == []
    assert Index([]).search("anything") == []


def test_snippet_prefers_matching_line(write_entry, brain):
    write_entry("s", title="Shells", body="First line.\n\nUse double quotes on Windows.\n")
    assert brain.search("windows quotes")[0].snippet == "Use double quotes on Windows."


def test_example_brain_windows_glob_ranks_ripgrep_first():
    hits = Brain.open(EXAMPLE_BRAIN).search("windows glob")
    assert hits[0].entry.id == "ripgrep-glob-on-windows"
