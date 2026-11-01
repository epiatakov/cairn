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


def test_link_ids_are_not_search_terms(write_entry, brain):
    write_entry("rotate-a-leaked-secret", type="skill", title="Rotate a credential")
    write_entry("untrack", title="Untrack a file", body="Then follow [[rotate-a-leaked-secret]].")
    write_entry("labelled", title="Other", body="Use [[untrack|git rm cached]] first.")
    assert [h.entry.id for h in brain.search("leaked secret")] == []
    assert [h.entry.id for h in brain.search("rotate")] == ["rotate-a-leaked-secret"]
    assert [h.entry.id for h in brain.search("cached")] == ["labelled"]
    assert brain.get("untrack").outgoing_links() == ["rotate-a-leaked-secret"]


def test_min_terms_and_min_score_gate(write_entry, brain):
    write_entry("db-lock", title="Database is locked", body="Enable WAL mode.")
    write_entry("db-wal", title="WAL mode", body="Readers do not block the writer.")
    one_word = brain.search("terraform state locked")
    assert [h.entry.id for h in one_word] == ["db-lock"] and one_word[0].matched == 1
    assert brain.search("terraform state locked", min_terms=2) == []
    assert [h.entry.id for h in brain.search("database locked", min_terms=2)] == ["db-lock"]
    # A one-word query needs only that word.
    assert [h.entry.id for h in brain.search("locked", min_terms=2)] == ["db-lock"]
    top = brain.search("wal mode")[0]
    assert brain.search("wal mode", min_score=top.score + 0.01) == []


def test_snippet_prefers_matching_line(write_entry, brain):
    write_entry("s", title="Shells", body="First line.\n\nUse double quotes on Windows.\n")
    assert brain.search("windows quotes")[0].snippet == "Use double quotes on Windows."


def test_example_brain_windows_glob_ranks_ripgrep_first():
    hits = Brain.open(EXAMPLE_BRAIN).search("windows glob")
    assert hits[0].entry.id == "ripgrep-glob-on-windows"
