import pytest

from cairn import Brain, DuplicateError
from cairn.dedupe import Fingerprint, find_similar, jaccard, shingles

from .conftest import EXAMPLE_BRAIN

BODY = (
    "cmd.exe does not treat single quotes as quoting, so ripgrep receives the glob with "
    "the quotes included. Use double quotes instead."
)


def test_shingles_and_jaccard_basics():
    assert shingles("Hi!") == frozenset({"hi"})
    assert shingles("") == frozenset()
    assert jaccard(shingles("abcdefg"), shingles("abcdefg")) == 1.0
    assert jaccard(frozenset(), shingles("abc")) == 0.0


@pytest.mark.parametrize(
    ("title", "body"),
    [
        ("ripgrep glob on Windows", BODY),
        ("Ripgrep glob on windows!", ""),
        ("ripgrep glob on Windows (cmd.exe)", BODY.replace("instead", "everywhere")),
    ],
)
def test_detects_near_duplicates(title, body):
    original = Fingerprint.of("ripgrep glob on Windows", BODY)
    assert original.similarity(Fingerprint.of(title, body)) >= 0.6


def test_distinct_topics_are_not_duplicates():
    a = Fingerprint.of("ripgrep glob on Windows", BODY)
    b = Fingerprint.of("ripgrep glob on Linux skips hidden files", "Pass --hidden.")
    assert a.similarity(b) < 0.3


def test_example_brain_has_no_near_duplicates():
    brain = Brain.open(EXAMPLE_BRAIN)
    for entry in brain.entries:
        others = [e for e in brain.entries if e is not entry]
        assert find_similar(entry.title, entry.body, others) == []


def test_add_refuses_duplicates_unless_forced(brain):
    brain.add(brain.new_entry("issue", "ripgrep glob on Windows", BODY))
    dup = brain.new_entry("issue", "Ripgrep glob on windows", "")
    with pytest.raises(DuplicateError) as info:
        brain.add(dup)
    assert [m.entry.id for m in info.value.matches] == ["ripgrep-glob-on-windows"]
    brain.add(dup, force=True)
    assert dup.id == "ripgrep-glob-on-windows-2"


def test_archived_entries_do_not_block_add(brain):
    old = brain.new_entry("fact", "Docker build cache tips", status="archived")
    brain.add(old)
    brain.add(brain.new_entry("fact", "Docker build cache tips"))
