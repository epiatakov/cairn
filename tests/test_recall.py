import io
import json

import pytest

from cairn import Brain
from cairn.cli import main
from cairn.recall import MAX_QUERY_CHARS, is_trivial, recall, render_text

from .conftest import EXAMPLE_BRAIN

BRAIN = str(EXAMPLE_BRAIN)


def run(capsys, *argv, stdin=None, monkeypatch=None):
    if stdin is not None:
        monkeypatch.setattr("sys.stdin", io.StringIO(stdin))
    code = main(list(argv))
    out, err = capsys.readouterr()
    return code, out, err


def hook_payload(prompt, **extra):
    return json.dumps(
        {"session_id": "s1", "hook_event_name": "UserPromptSubmit", "prompt": prompt, **extra}
    )


@pytest.mark.parametrize(
    "prompt", ["", "   ", "thanks!", "Thank you very much", "ok, go ahead", "lgtm", "fix it", "y"]
)
def test_trivial_prompts(prompt):
    assert is_trivial(prompt)


@pytest.mark.parametrize(
    "prompt", ["rg glob fails on windows", "npm ci fails", "why is sqlite locked?"]
)
def test_substantive_prompts(prompt):
    assert not is_trivial(prompt)


def test_trivial_filter_is_configurable():
    assert is_trivial("ripgrep", min_words=2)
    assert not is_trivial("ripgrep", min_words=1)
    assert not is_trivial("thanks", min_words=0)
    assert is_trivial("ripgrep glob windows", min_words=4)


def test_recall_applies_threshold_and_limit():
    brain = Brain.open(EXAMPLE_BRAIN)
    hits = recall(brain, "rg glob fails on windows")
    assert hits[0].entry.id == "ripgrep-glob-on-windows"
    assert all(h.score >= 1.5 for h in hits)
    assert len(recall(brain, "rg glob fails on windows", min_score=0, limit=2)) == 2
    assert recall(brain, "rg glob fails on windows", min_score=100) == []


def test_recall_needs_two_shared_words():
    brain = Brain.open(EXAMPLE_BRAIN)
    # "sqlite" alone clears the score floor; nothing else in the prompt is in the brain.
    prompt = "helm chart sqlite backup"
    assert [h.entry.id for h in recall(brain, prompt, min_terms=1)] == [
        "sqlite-wal-mode-concurrency"
    ]
    assert recall(brain, prompt) == []
    assert all(h.matched >= 2 for h in recall(brain, "rg glob fails on windows"))


def test_recall_caps_long_prompts():
    brain = Brain.open(EXAMPLE_BRAIN)
    prompt = "rg glob fails on windows " + "x" * MAX_QUERY_CHARS + " sqlite wal"
    ids = [h.entry.id for h in recall(brain, prompt)]
    assert ids[0] == "ripgrep-glob-on-windows"
    assert "sqlite-wal-mode-concurrency" not in ids


def test_render_text_points_at_files():
    brain = Brain.open(EXAMPLE_BRAIN)
    text = render_text(brain, recall(brain, "rg glob fails on windows"))
    assert "- ripgrep-glob-on-windows (issue): ripgrep glob on Windows" in text
    assert f"{EXAMPLE_BRAIN.as_posix()}/issues/ripgrep-glob-on-windows.md" in text
    assert render_text(brain, []) == ""


def test_cli_text_and_json(capsys):
    code, out, _ = run(capsys, "recall", "rg", "glob", "fails", "on", "windows", "--brain", BRAIN)
    assert code == 0
    assert "ripgrep-glob-on-windows" in out

    code, out, _ = run(capsys, "recall", "rg glob fails", "--format", "json", "--brain", BRAIN)
    payload = json.loads(out)
    assert payload["version"] == 1
    assert payload["skipped"] is False
    top = payload["results"][0]
    assert top["id"] == "ripgrep-glob-on-windows"
    assert top["path"] == "issues/ripgrep-glob-on-windows.md"
    assert set(top) >= {"type", "title", "status", "score", "snippet"}

    code, out, _ = run(capsys, "recall", "rg glob fails", "--json", "--brain", BRAIN)
    assert json.loads(out) == payload, "--json is an alias for --format json"

    code, out, _ = run(capsys, "recall", "thanks", "--format", "json", "--brain", BRAIN)
    assert json.loads(out)["skipped"] is True
    assert json.loads(out)["results"] == []

    assert run(capsys, "recall", "thanks", "--brain", BRAIN)[1] == "skipped: trivial prompt\n"
    assert run(capsys, "recall", "quantum chromodynamics", "--brain", BRAIN)[1] == (
        "no relevant entries\n"
    )
    prompt = "helm chart sqlite backup"
    assert run(capsys, "recall", prompt, "--brain", BRAIN)[1] == "no relevant entries\n"
    assert "sqlite-wal" in run(capsys, "recall", prompt, "--min-terms", "1", "--brain", BRAIN)[1]


def test_cli_errors_outside_hook_mode(capsys, tmp_path):
    code, _, err = run(capsys, "recall", "--brain", BRAIN)
    assert code == 1 and "give a prompt" in err
    code, _, err = run(capsys, "recall", "rg glob", "--brain", str(tmp_path / "nope"))
    assert code == 1 and "no brain" in err


def test_claude_hook_contract(capsys, monkeypatch):
    code, out, err = run(
        capsys, "recall", "--format", "claude-hook", "--brain", BRAIN,
        stdin=hook_payload("rg glob fails on windows"), monkeypatch=monkeypatch,
    )  # fmt: skip
    assert code == 0 and err == ""
    output = json.loads(out)
    assert output["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"
    context = output["hookSpecificOutput"]["additionalContext"]
    assert "ripgrep-glob-on-windows" in context
    assert out.isascii()


def test_claude_hook_resolves_relative_brain_against_payload_cwd(capsys, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    payload = hook_payload("rg glob fails on windows", cwd=str(EXAMPLE_BRAIN.parent))
    code, out, _ = run(
        capsys, "recall", "--format", "claude-hook", "--brain", "brain",
        stdin=payload, monkeypatch=monkeypatch,
    )  # fmt: skip
    assert code == 0
    assert "ripgrep-glob-on-windows" in out


@pytest.mark.parametrize(
    "stdin",
    [
        hook_payload("thanks!"),  # trivial
        hook_payload("quantum chromodynamics lattice"),  # nothing above the threshold
        "not json",
        "",
        "[1, 2]",
        json.dumps({"prompt": 42}),
        json.dumps({"no_prompt": True}),
    ],
)
def test_claude_hook_is_silent(capsys, monkeypatch, stdin):
    code, out, err = run(
        capsys, "recall", "--format", "claude-hook", "--brain", BRAIN,
        stdin=stdin, monkeypatch=monkeypatch,
    )  # fmt: skip
    assert (code, out, err) == (0, "", "")


def test_claude_hook_is_silent_without_a_brain(capsys, monkeypatch, tmp_path):
    code, out, err = run(
        capsys, "recall", "--format", "claude-hook", "--brain", str(tmp_path / "missing"),
        stdin=hook_payload("rg glob fails on windows"), monkeypatch=monkeypatch,
    )  # fmt: skip
    assert (code, out, err) == (0, "", "")


def test_claude_hook_survives_bad_flags(capsys, monkeypatch):
    code, out, _ = run(
        capsys, "recall", "--format", "claude-hook", "--no-such-flag",
        stdin=hook_payload("rg glob"), monkeypatch=monkeypatch,
    )  # fmt: skip
    assert (code, out) == (0, "")
    with pytest.raises(SystemExit):
        main(["recall", "--no-such-flag"])


def test_claude_hook_survives_unexpected_errors(capsys, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("bug")

    monkeypatch.setattr("cairn.recall.recall", boom)
    code, out, err = run(
        capsys, "recall", "--format", "claude-hook", "--brain", BRAIN,
        stdin=hook_payload("rg glob fails on windows"), monkeypatch=monkeypatch,
    )  # fmt: skip
    assert (code, out, err) == (0, "", "")
