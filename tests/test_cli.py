import io
import json

import pytest

from cairn.cli import main

from .conftest import EXAMPLE_BRAIN


def run(capsys, *argv):
    code = main(list(argv))
    out, err = capsys.readouterr()
    return code, out, err


def test_round_trip(tmp_path, capsys, monkeypatch):
    root = str(tmp_path / "brain")
    assert run(capsys, "init", "--brain", root)[0] == 0
    assert (tmp_path / "brain" / "README.md").exists()

    monkeypatch.setattr("sys.stdin", io.StringIO('Use `rg -g "*.py"` in cmd.exe.\n'))
    code, out, _ = run(
        capsys, "add", "issue", "--title", "ripgrep glob on Windows",
        "--tags", "ripgrep,Windows", "--tags", "glob", "--body", "-", "--brain", root,
    )  # fmt: skip
    assert code == 0
    assert "ripgrep-glob-on-windows (issues/ripgrep-glob-on-windows.md)" in out

    body_file = tmp_path / "body.md"
    body_file.write_text("Readers do not block writers.", encoding="utf-8")
    code, _, _ = run(
        capsys, "--brain", root, "add", "fact", "--title", "SQLite WAL mode",
        "--body-file", str(body_file), "--link", "ripgrep-glob-on-windows",
    )  # fmt: skip
    assert code == 0

    code, out, _ = run(capsys, "search", "windows", "glob", "--json", "--brain", root)
    payload = json.loads(out)
    assert payload["version"] == 1
    assert payload["query"] == "windows glob"
    top = payload["results"][0]
    assert top["id"] == "ripgrep-glob-on-windows"
    assert top["tags"] == ["ripgrep", "windows", "glob"]
    assert top["path"] == "issues/ripgrep-glob-on-windows.md"
    assert set(top) >= {"type", "title", "status", "score", "snippet", "links"}

    code, out, _ = run(capsys, "show", "sqlite-wal-mode", "--json", "--brain", root)
    entry = json.loads(out)["entry"]
    assert entry["body"] == "Readers do not block writers."
    assert entry["links"] == ["ripgrep-glob-on-windows"]

    code, out, _ = run(capsys, "show", "sqlite-wal-mode", "--brain", root)
    assert out.startswith("---\nid: sqlite-wal-mode\n")

    code, out, _ = run(capsys, "list", "--type", "fact", "--brain", root)
    assert out.split() == ["sqlite-wal-mode", "fact", "active", "SQLite", "WAL", "mode"]

    assert run(capsys, "lint", "--brain", root)[0] == 0
    assert run(capsys, "index", "--check", "--brain", root)[0] == 1
    assert run(capsys, "index", "--brain", root)[0] == 0
    assert run(capsys, "index", "--check", "--brain", root)[0] == 0


def test_add_refuses_near_duplicate(tmp_path, capsys):
    root = str(tmp_path / "b")
    run(capsys, "init", "--brain", root)
    run(capsys, "add", "fact", "--title", "Pin line endings with gitattributes", "--brain", root)
    code, _, err = run(
        capsys, "add", "fact", "--title", "Pin line endings with .gitattributes", "--brain", root
    )
    assert code == 1
    assert "near-duplicate" in err
    assert "pin-line-endings-with-gitattributes" in err
    args = ["add", "fact", "--title", "Pin line endings with .gitattributes", "--force"]
    assert run(capsys, *args, "--brain", root)[0] == 0


def test_brain_from_environment(capsys, monkeypatch):
    monkeypatch.setenv("CAIRN_BRAIN", str(EXAMPLE_BRAIN))
    code, out, _ = run(capsys, "search", "windows glob", "--limit", "1")
    assert code == 0
    assert "ripgrep-glob-on-windows" in out


def test_errors(tmp_path, capsys):
    code, _, err = run(capsys, "list", "--brain", str(tmp_path / "missing"))
    assert code == 1
    assert "no brain at" in err

    code, _, err = run(capsys, "show", "ripgrep-glob-on-window", "--brain", str(EXAMPLE_BRAIN))
    assert code == 1
    assert "did you mean: ripgrep-glob-on-windows" in err

    with pytest.raises(SystemExit) as info:
        main(["add", "memo", "--title", "x"])
    assert info.value.code == 2


def test_lint_exit_codes(tmp_path, capsys):
    root = tmp_path / "b"
    run(capsys, "init", "--brain", str(root))
    note = "---\nid: n\ntype: note\ntitle: N\ncreated: 2026-01-01\nupdated: 2026-01-01\n---\n"
    (root / "notes" / "other-name.md").write_text(note, encoding="utf-8")
    code, out, _ = run(capsys, "lint", "--brain", str(root))
    assert code == 0
    assert "warning [id-mismatch]" in out
    assert run(capsys, "lint", "--strict", "--brain", str(root))[0] == 1
    (root / "notes" / "bad.md").write_text("oops\n", encoding="utf-8")
    assert run(capsys, "lint", "--brain", str(root))[0] == 1


def test_search_gate_is_opt_in(capsys):
    root = str(EXAMPLE_BRAIN)
    code, out, _ = run(capsys, "search", "helm chart sqlite backup", "--json", "--brain", root)
    assert [r["id"] for r in json.loads(out)["results"]] == ["sqlite-wal-mode-concurrency"]
    code, out, _ = run(
        capsys, "search", "helm", "chart", "sqlite", "backup", "--gate", "--brain", root
    )
    assert (code, out) == (0, "no matches\n")
    code, out, _ = run(capsys, "search", "windows glob", "--gate", "--brain", root)
    assert "ripgrep-glob-on-windows" in out


def test_example_index_is_current(capsys):
    assert run(capsys, "index", "--check", "--brain", str(EXAMPLE_BRAIN))[0] == 0
