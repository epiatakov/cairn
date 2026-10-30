import io
import json
from datetime import date, timedelta

import pytest

from cairn import Brain, CairnError
from cairn.cli import main
from cairn.issues import (
    board,
    check_fields,
    fingerprint,
    match,
    occurrences,
    parse_duration,
    prune,
    record,
    resolve,
    sessions,
    signature,
    state,
)
from cairn.lint import lint

from .conftest import EXAMPLE_BRAIN

TODAY = date(2026, 10, 30)
RG_ERROR = r"rg: C:\proj\src\*: The filename, directory name, or volume label syntax is incorrect"


def run(capsys, *argv, stdin=None, monkeypatch=None):
    if stdin is not None:
        monkeypatch.setattr("sys.stdin", io.StringIO(stdin))
    code = main(list(argv))
    out, err = capsys.readouterr()
    return code, out, err


# -- fingerprinting ------------------------------------------------------


@pytest.mark.parametrize(
    "a, b",
    [
        (
            RG_ERROR,
            r"rg: D:\Users\sam\work\lib\*: The filename, directory name, or volume "
            "label syntax is incorrect",
        ),
        (
            "/home/alice/app/run.sh: /bin/bash^M: bad interpreter: No such file or directory",
            "/srv/ci/build-77/run.sh: /bin/bash^M: bad interpreter: No such file or directory",
        ),
        (
            'File "/tmp/x/main.py", line 12\nValueError: invalid literal for int(): "abc"',
            "File '/opt/y/main.py', line 940\nValueError: invalid literal for int(): 'abc'",
        ),
        (
            "2026-01-02T03:04:05Z ERROR job 3fa9c1e2b7d0 failed after 12 retries",
            "2026-09-30 23:59:01 ERROR job 0badc0ffee11 failed after 3 retries",
        ),
        (
            "error: cannot open /tmp/tmpk3j2_x/cache.db (id 0x7ffe1234)",
            "error: cannot open C:\\Temp\\tmp9a8b\\cache.db (id 0x1)",
        ),
        (
            "fatal: request 123e4567-e89b-12d3-a456-426614174000 timed out, see https://x.test/a?b=1",
            "fatal: request 00000000-0000-4000-8000-000000000000 timed out, see https://y.test/",
        ),
        ("\x1b[31merror:\x1b[0m `foo` not found", "error: 'foo' not found"),
    ],
)
def test_fingerprint_is_stable_across_machines(a, b):
    assert fingerprint(a) == fingerprint(b)
    assert len(fingerprint(a)) == 12


def test_fingerprint_keeps_the_error_class_and_meaningful_codes():
    assert fingerprint("ValueError: bad input") != fingerprint("TypeError: bad input")
    assert fingerprint("HTTP 404 from registry") != fingerprint("HTTP 500 from registry")
    assert fingerprint("process failed, exit code 1") != fingerprint(
        "process failed, exit code 127"
    )
    assert "os error 123" in signature(RG_ERROR + " (os error 123)")


def test_signature_prefers_error_lines_over_noise():
    text = "Compiling 42 files\nnpm ERR!\nnpm ERR! code EUSAGE\nnpm ERR! cannot install x\n"
    assert signature(text) == "npm err code eusage | npm err cannot install x"
    assert fingerprint("   \n\n") == ""


# -- record / match ------------------------------------------------------


def test_record_creates_then_increments(brain):
    first = record(brain, "rg", RG_ERROR, session="s1", today=TODAY)
    assert first.created and first.method == "new"
    entry = first.entry
    assert entry.type == "issue" and entry.path.parent.name == "issues"
    assert entry.extra["fingerprint"] == [first.fingerprint]
    assert state(entry) == "open" and occurrences(entry) == 1
    assert "{path}" in entry.body and "proj" not in entry.body  # local paths are not stored

    variant = RG_ERROR.replace(r"C:\proj\src", r"E:\other\dir")
    second = record(brain, "rg", variant, session="s2", today=TODAY + timedelta(days=2))
    assert not second.created and second.method == "fingerprint"
    again = Brain.open(brain.root).get(entry.id)
    assert occurrences(again) == 2
    assert sessions(again) == ["s1", "s2"]
    assert again.extra["first_seen"] == "2026-10-30"
    assert again.extra["last_seen"] == "2026-11-01"
    assert again.updated == "2026-11-01"
    assert lint(brain) == []


def test_record_learns_new_fingerprints_from_similar_errors(brain):
    record(brain, "rg", RG_ERROR, today=TODAY)
    rec = record(brain, "rg", RG_ERROR + " (os error 123)", today=TODAY)
    assert rec.method == "similarity"
    assert len(rec.entry.extra["fingerprint"]) == 2
    assert match(brain, RG_ERROR + ". (os error 123)").method == "fingerprint"


def test_record_sets_workaround_and_reopens_fixed_issues(brain):
    entry = record(brain, "git", "fatal: detected dubious ownership", today=TODAY).entry
    record(brain, "git", "fatal: detected dubious ownership", workaround_text="trust it")
    assert state(brain.get(entry.id)) == "workaround"
    resolve(brain, entry.id, fix_text="run as the owner")
    assert state(brain.get(entry.id)) == "fixed"
    record(brain, "git", "fatal: detected dubious ownership")
    reopened = brain.get(entry.id)
    assert state(reopened) == "workaround" and reopened.extra["fix"] == "run as the owner"


def test_record_rejects_empty_input(brain):
    with pytest.raises(CairnError):
        record(brain, "rg", "  \n")
    with pytest.raises(CairnError):
        record(brain, " ", "error: x")


def test_match_prefers_fingerprint_then_similarity_and_rejects_unrelated():
    brain = Brain.open(EXAMPLE_BRAIN)
    exact = match(brain, RG_ERROR)
    assert exact.entry.id == "ripgrep-wildcard-path-on-windows"
    assert exact.method == "fingerprint"

    reworded = "rg: X:\\a\\*: filename, directory name or volume label syntax incorrect (0x7b)"
    fuzzy = match(brain, reworded)
    assert fuzzy.entry.id == "ripgrep-wildcard-path-on-windows"
    assert fuzzy.method == "similarity" and 0.5 <= fuzzy.confidence <= 1

    for unrelated in (
        "permission denied: ./run.sh",
        "ModuleNotFoundError: No module named 'requests'",
        "docker: invalid reference format",
    ):
        assert match(brain, unrelated) is None, unrelated


def test_match_ignores_archived_issues(brain, write_entry):
    fp = fingerprint("boom: it broke")
    write_entry("old", type="issue", status="archived", extra={"fingerprint": [fp]})
    assert match(brain, "boom: it broke") is None


def test_hand_written_issues_expose_body_workaround():
    entry = Brain.open(EXAMPLE_BRAIN).get("ripgrep-glob-on-windows")
    entry.extra.pop("workaround", None)
    from cairn.issues import workaround

    assert workaround(entry).startswith("- Use double quotes")
    assert state(entry) == "workaround"


# -- board / resolve / prune --------------------------------------------


def _issue(write_entry, entry_id, occ, seen, **extra):
    write_entry(
        entry_id,
        type="issue",
        title=f"{entry_id} failure",
        extra={"tool": "rg", "occurrences": str(occ), "last_seen": seen, **extra},
        updated=seen,
    )


def test_board_orders_by_hot_score_and_filters(brain, write_entry):
    _issue(write_entry, "old-but-frequent", 20, "2026-09-01")
    _issue(write_entry, "recent", 3, "2026-10-29")
    _issue(write_entry, "fresh-single", 1, "2026-10-30", tool="git")
    _issue(write_entry, "done", 50, "2026-10-30", state="fixed", fix="patched")
    ids = [e.id for e in board(brain, today=TODAY)]
    assert ids == ["recent", "fresh-single", "old-but-frequent"]
    assert [e.id for e in board(brain, since_days=7, today=TODAY)] == ["recent", "fresh-single"]
    assert [e.id for e in board(brain, tools=["git"], today=TODAY)] == ["fresh-single"]
    assert [e.id for e in board(brain, states=["fixed"], today=TODAY)] == ["done"]
    assert board(brain, include_all=True, today=TODAY)[0].id == "done"


def test_resolve_sets_state(brain, write_entry):
    _issue(write_entry, "flaky", 2, "2026-10-01")
    entry = resolve(brain, "flaky", workaround_text="retry with --jobs 1", today=TODAY)
    assert state(entry) == "workaround" and entry.updated == "2026-10-30"
    entry = resolve(brain, "flaky", fix_text="pinned the dependency")
    assert state(entry) == "fixed"
    assert entry.extra["workaround"] == "retry with --jobs 1"
    with pytest.raises(CairnError):
        resolve(brain, "flaky", workaround_text="a", fix_text="b")
    with pytest.raises(CairnError):
        resolve(brain, "missing", fix_text="x")


def test_prune_marks_stale_and_recurrence_revives(brain, write_entry):
    _issue(write_entry, "ancient", 4, "2026-08-01")
    _issue(write_entry, "current", 1, "2026-10-20")
    assert [e.id for e in prune(brain, 30, today=TODAY, dry_run=True)] == ["ancient"]
    assert brain.get("ancient").status == "active"
    assert [e.id for e in prune(brain, 30, today=TODAY)] == ["ancient"]
    assert Brain.open(brain.root).get("ancient").status == "stale"
    assert prune(brain, 30, today=TODAY) == []

    fp = fingerprint("ancient: it broke again")
    entry = brain.get("ancient")
    entry.extra["fingerprint"] = [fp]
    from cairn.issues import save

    save(brain, entry)
    record(brain, "rg", "ancient: it broke again", today=TODAY)
    assert brain.get("ancient").status == "active"


def test_parse_duration():
    assert parse_duration("7d") == 7
    assert parse_duration("2w") == 14
    with pytest.raises(CairnError):
        parse_duration("soon")


# -- lint ----------------------------------------------------------------


def test_lint_checks_issue_fields(brain, write_entry):
    bad = {
        "fingerprint": ["XYZ"],
        "state": "maybe",
        "occurrences": "lots",
        "first_seen": "2026-05-02",
        "last_seen": "2026-05-01",
    }
    write_entry("bad-issue", type="issue", extra=bad)
    messages = sorted(p.message for p in lint(brain) if p.code == "invalid-issue")
    assert len(messages) == 4
    assert any("invalid fingerprint 'XYZ'" in m for m in messages)
    assert any("'last_seen' is earlier" in m for m in messages)


def test_lint_requires_text_for_resolved_states(brain, write_entry):
    write_entry("fixed-issue", type="issue", extra={"state": "fixed"})
    assert [p.message for p in lint(brain)] == ["state is 'fixed' but no 'fix' is recorded"]


def test_lint_warns_on_shared_fingerprints(brain, write_entry):
    fp = fingerprint("boom")
    write_entry("one", type="issue", title="Alpha failure", extra={"fingerprint": [fp]})
    write_entry("two", type="issue", title="Beta problem", extra={"fingerprint": [fp]})
    assert {(p.severity, p.code) for p in lint(brain)} == {("warning", "duplicate-fingerprint")}


def test_plain_issue_entries_stay_valid(brain, write_entry):
    write_entry("plain", type="issue", body="**Symptom:** x")
    assert lint(brain) == []
    assert check_fields(brain.get("plain")) == []


# -- CLI and hook --------------------------------------------------------


def test_cli_record_list_resolve_prune(tmp_path, capsys, monkeypatch):
    root = str(tmp_path / "b")
    run(capsys, "init", "--brain", root)
    code, out, _ = run(
        capsys, "issue", "record", "--tool", "rg", "--error", "-", "--session", "a",
        "--brain", root, stdin=RG_ERROR, monkeypatch=monkeypatch,
    )  # fmt: skip
    assert code == 0 and out.startswith("recorded new issue rg-path-the-filename")
    code, out, _ = run(
        capsys, "issue", "record", "--tool", "rg", "--error", RG_ERROR, "--json", "--brain", root
    )
    payload = json.loads(out)
    assert payload["version"] == 1 and payload["created"] is False
    issue = payload["issue"]
    assert issue["occurrences"] == 2 and issue["state"] == "open"
    issue_id = issue["id"]

    code, out, _ = run(capsys, "issue", "list", "--since", "7d", "--json", "--brain", root)
    listed = json.loads(out)["issues"]
    assert [i["id"] for i in listed] == [issue_id]
    assert set(listed[0]) >= {"hot", "tool", "state", "occurrences", "last_seen", "workaround"}

    code, out, _ = run(
        capsys, "issue", "resolve", issue_id, "--workaround", "pass the dir", "--brain", root
    )
    assert code == 0 and "state workaround" in out
    code, out, _ = run(capsys, "issue", "list", "--brain", root)
    assert issue_id in out and "workaround" in out

    code, out, _ = run(capsys, "issue", "prune", "--older-than", "30d", "--brain", root)
    assert code == 0 and "0 issue(s) marked stale" in out
    code, _, err = run(capsys, "issue", "prune", "--older-than", "x", "--brain", root)
    assert code == 1 and "invalid duration" in err
    assert run(capsys, "lint", "--brain", root)[0] == 0


def test_cli_match_text_and_json(capsys):
    brain = str(EXAMPLE_BRAIN)
    code, out, _ = run(capsys, "issue", "match", "--error", RG_ERROR, "--brain", brain)
    assert code == 0
    assert out.startswith("ripgrep-wildcard-path-on-windows")
    assert 'rg TODO C:\\proj\\src -g "*.py"' in out

    code, out, _ = run(capsys, "issue", "match", "--error", RG_ERROR, "--json", "--brain", brain)
    payload = json.loads(out)
    assert payload["match"]["id"] == "ripgrep-wildcard-path-on-windows"
    assert payload["match"]["method"] == "fingerprint"
    assert payload["fingerprint"] == fingerprint(RG_ERROR)

    code, out, _ = run(capsys, "issue", "match", "--error", "all good", "--brain", brain)
    assert (code, out) == (1, "")
    code, out, _ = run(capsys, "issue", "match", "--error", "fine", "--json", "--brain", brain)
    assert code == 1 and json.loads(out)["match"] is None


def _hook(capsys, monkeypatch, payload, brain=str(EXAMPLE_BRAIN)):
    stdin = payload if isinstance(payload, str) else json.dumps(payload)
    return run(
        capsys, "issue", "match", "--format", "claude-hook", "--brain", brain,
        stdin=stdin, monkeypatch=monkeypatch,
    )  # fmt: skip


def test_hook_emits_additional_context_for_known_failures(capsys, monkeypatch):
    payload = {
        "session_id": "abc",
        "hook_event_name": "PostToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": "rg TODO C:\\proj\\src\\*"},
        "tool_response": {"stdout": "", "stderr": RG_ERROR + " (os error 123)"},
    }
    code, out, err = _hook(capsys, monkeypatch, payload)
    assert code == 0 and err == ""
    output = json.loads(out)["hookSpecificOutput"]
    assert output["hookEventName"] == "PostToolUse"
    assert "ripgrep-wildcard-path-on-windows" in output["additionalContext"]
    assert "Workaround: Pass the directory" in output["additionalContext"]
    assert out.isascii()


def test_hook_handles_failure_events_and_exit_codes(capsys, monkeypatch):
    failure = {"hook_event_name": "PostToolUseFailure", "tool_name": "Bash", "error": RG_ERROR}
    _, out, _ = _hook(capsys, monkeypatch, failure)
    assert json.loads(out)["hookSpecificOutput"]["hookEventName"] == "PostToolUseFailure"

    exit_code = {
        "hook_event_name": "PostToolUse",
        "tool_response": {"stdout": RG_ERROR, "exit_code": 2},
    }
    _, out, _ = _hook(capsys, monkeypatch, exit_code)
    assert "ripgrep-wildcard-path-on-windows" in out


@pytest.mark.parametrize(
    "payload, brain",
    [
        ({"hook_event_name": "PostToolUse", "tool_response": {"stdout": RG_ERROR}}, None),
        ({"hook_event_name": "PostToolUse", "tool_response": {"stderr": "warning: slow"}}, None),
        ({"hook_event_name": "PostToolUse", "tool_response": {"stderr": "error: zzz"}}, None),
        ("not json at all", None),
        ("[1, 2, 3]", None),
        ("", None),
        ({"hook_event_name": "PostToolUseFailure", "error": RG_ERROR}, "/no/such/brain"),
    ],
)
def test_hook_is_silent_on_no_match_or_any_error(capsys, monkeypatch, payload, brain):
    code, out, err = _hook(capsys, monkeypatch, payload, brain or str(EXAMPLE_BRAIN))
    assert (code, out, err) == (0, "", "")


def test_example_issues_match_their_documented_errors():
    brain = Brain.open(EXAMPLE_BRAIN)
    cases = {
        "shell-script-bad-interpreter-crlf": "/x/y.sh: /bin/bash^M: bad interpreter: "
        "No such file or directory",
        "git-dubious-ownership-in-container": "fatal: detected dubious ownership in "
        "repository at '/home/u/repo'",
        "docker-run-options-after-image-name": "docker: Error response from daemon: failed to "
        "create task for container: failed to create shim task: OCI runtime create failed: "
        'runc create failed: unable to start container process: exec: "--rm": executable '
        "file not found in $PATH: unknown.",
        "npm-ci-fails-when-lockfile-out-of-sync": "npm error `npm ci` can only install packages "
        "when your package.json and package-lock.json or npm-shrinkwrap.json are in sync. "
        "Please update your lock file with `npm install` before continuing.",
        "ripgrep-wildcard-path-on-windows": RG_ERROR + ". (os error 123)",
    }
    for issue_id, error in cases.items():
        found = match(brain, error)
        assert found is not None and found.entry.id == issue_id, issue_id
        assert found.method == "fingerprint", issue_id
