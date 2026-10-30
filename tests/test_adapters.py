import io
import json
from pathlib import Path

import pytest

from cairn import CairnError
from cairn.adapters.base import BLOCK_BEGIN, BLOCK_END, remove_block, upsert_block
from cairn.cli import main

from .conftest import EXAMPLE_BRAIN

USER_HOOK = {"type": "command", "command": "echo user-hook"}


@pytest.fixture
def project(tmp_path: Path) -> Path:
    path = tmp_path / "project"
    path.mkdir()
    return path


def cairn(capsys, project: Path, *argv, brain: Path = EXAMPLE_BRAIN):
    code = main([*argv, "--project", str(project), "--brain", str(brain)])
    out, err = capsys.readouterr()
    assert code == 0, err
    return out


def snapshot(root: Path) -> dict[str, str]:
    return {
        p.relative_to(root).as_posix(): p.read_text(encoding="utf-8")
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


# -- managed blocks --------------------------------------------------------------------------


@pytest.mark.parametrize("original", ["", "# Notes\n", "# Notes\n\nMore text.\n", "no newline"])
def test_block_round_trip(original):
    once = upsert_block(original, "hello")
    assert upsert_block(once, "hello") == once
    assert once.count(BLOCK_BEGIN) == 1 and once.endswith(f"hello\n{BLOCK_END}\n")
    removed = remove_block(once)
    assert removed == (original if original.endswith("\n") or not original else original + "\n")


def test_block_replaced_in_place():
    text = f"top\n\n{BLOCK_BEGIN}\nold\n{BLOCK_END}\n\nbottom\n"
    assert upsert_block(text, "new") == f"top\n\n{BLOCK_BEGIN}\nnew\n{BLOCK_END}\n\nbottom\n"
    assert remove_block(text) == "top\n\n\nbottom\n"


def test_unterminated_block_is_an_error():
    with pytest.raises(CairnError, match="cairn:end"):
        upsert_block(f"{BLOCK_BEGIN}\nhalf a block\n", "x")


# -- install and uninstall, every tool -------------------------------------------------------

BLOCK_FILES = {
    "claude": "CLAUDE.md",
    "codex": "AGENTS.md",
    "copilot": ".github/copilot-instructions.md",
}


@pytest.mark.parametrize("tool", ["claude", "codex", "copilot", "cursor"])
def test_install_uninstall_on_empty_project(capsys, project, tool):
    cairn(capsys, project, "install", tool)
    installed = snapshot(project)
    assert installed
    assert any("cairn recall" in text for text in installed.values())

    out = cairn(capsys, project, "install", tool)
    assert snapshot(project) == installed, "install must be idempotent"
    assert all(line.startswith("unchanged ") for line in out.splitlines())

    cairn(capsys, project, "uninstall", tool)
    assert list(project.rglob("*")) == [], "uninstall must remove everything install added"
    cairn(capsys, project, "uninstall", tool)  # uninstalling twice is fine


@pytest.mark.parametrize("tool", ["claude", "codex", "copilot"])
def test_install_preserves_user_content(capsys, project, tool):
    path = project / BLOCK_FILES[tool]
    path.parent.mkdir(parents=True, exist_ok=True)
    original = "# House rules\n\nUse tabs. Never push on Fridays.\n"
    path.write_text(original, encoding="utf-8")

    cairn(capsys, project, "install", tool)
    text = path.read_text(encoding="utf-8")
    assert text.startswith(original)
    assert BLOCK_BEGIN in text

    # User edits outside the block survive a re-install.
    path.write_text(text + "\nAdded later by hand.\n", encoding="utf-8")
    cairn(capsys, project, "install", tool)
    assert path.read_text(encoding="utf-8").endswith("\nAdded later by hand.\n")

    cairn(capsys, project, "uninstall", tool)
    assert path.read_text(encoding="utf-8") == original + "\n\nAdded later by hand.\n"


def test_dry_run_writes_nothing(capsys, project):
    out = cairn(capsys, project, "install", "claude", "--dry-run")
    assert "would create .claude/settings.json" in out
    assert "would create CLAUDE.md" in out
    assert "+<!-- cairn:end -->" in out
    assert list(project.iterdir()) == []


def test_brain_inside_project_is_written_relative(capsys, project):
    (project / "brain").mkdir()
    cairn(capsys, project, "install", "codex", brain=project / "brain")
    text = (project / "AGENTS.md").read_text(encoding="utf-8")
    assert "--brain brain`" in text
    assert str(project) not in text


# -- claude settings.json --------------------------------------------------------------------


def settings(project: Path) -> dict:
    return json.loads((project / ".claude/settings.json").read_text(encoding="utf-8"))


def test_claude_hook_wiring(capsys, project):
    cairn(capsys, project, "install", "claude")
    groups = settings(project)["hooks"]["UserPromptSubmit"]
    assert len(groups) == 1
    (hook,) = groups[0]["hooks"]
    assert hook["type"] == "command"
    assert hook["command"] == f"cairn recall --format claude-hook --brain {EXAMPLE_BRAIN}"
    assert hook["timeout"] > 0


def test_claude_merge_keeps_existing_settings_and_hooks(capsys, project):
    existing = {
        "permissions": {"allow": ["Bash(ls:*)"]},
        "hooks": {
            "UserPromptSubmit": [{"hooks": [USER_HOOK]}],
            "PreToolUse": [{"matcher": "Bash", "hooks": [USER_HOOK]}],
        },
    }
    path = project / ".claude/settings.json"
    path.parent.mkdir()
    path.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")

    cairn(capsys, project, "install", "claude")
    merged = settings(project)
    assert merged["permissions"] == existing["permissions"]
    assert merged["hooks"]["PreToolUse"] == existing["hooks"]["PreToolUse"]
    groups = merged["hooks"]["UserPromptSubmit"]
    assert groups[0] == {"hooks": [USER_HOOK]}
    assert "cairn recall" in groups[1]["hooks"][0]["command"]

    cairn(capsys, project, "install", "claude")
    assert settings(project) == merged

    cairn(capsys, project, "uninstall", "claude")
    assert settings(project) == existing


def test_claude_reinstall_with_new_brain_updates_hook_in_place(capsys, project, tmp_path):
    cairn(capsys, project, "install", "claude")
    other = tmp_path / "other brain"
    other.mkdir()
    cairn(capsys, project, "install", "claude", brain=other)
    (group,) = settings(project)["hooks"]["UserPromptSubmit"]
    (hook,) = group["hooks"]
    assert hook["command"].endswith(f"--brain '{other}'")


def test_claude_uninstall_keeps_user_hooks_in_shared_group(capsys, project):
    cairn(capsys, project, "install", "claude")
    data = settings(project)
    data["hooks"]["UserPromptSubmit"][0]["hooks"].append(USER_HOOK)
    (project / ".claude/settings.json").write_text(json.dumps(data), encoding="utf-8")

    cairn(capsys, project, "uninstall", "claude")
    assert settings(project) == {"hooks": {"UserPromptSubmit": [{"hooks": [USER_HOOK]}]}}


@pytest.mark.parametrize("content", ["{not json", "[]", '{"hooks": {"UserPromptSubmit": {}}}'])
def test_claude_refuses_unexpected_settings(capsys, project, content):
    path = project / ".claude/settings.json"
    path.parent.mkdir()
    path.write_text(content, encoding="utf-8")
    code = main(["install", "claude", "--project", str(project), "--brain", str(EXAMPLE_BRAIN)])
    assert code == 1
    assert "cairn: error:" in capsys.readouterr().err
    assert path.read_text(encoding="utf-8") == content
    assert not (project / "CLAUDE.md").exists(), "nothing is written when any step fails"


def test_done_check_install_then_hook(capsys, project, monkeypatch):
    """The acceptance scenario: install into a project, then run the hook it wired up."""
    cairn(capsys, project, "install", "claude")
    command = settings(project)["hooks"]["UserPromptSubmit"][0]["hooks"][0]["command"]
    argv = command.split()[1:]  # drop the "cairn" program name
    payload = {"hook_event_name": "UserPromptSubmit", "cwd": str(project)}
    payload["prompt"] = "rg glob fails on windows"
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    assert main(argv) == 0
    out = json.loads(capsys.readouterr().out)
    assert "ripgrep-glob-on-windows" in out["hookSpecificOutput"]["additionalContext"]


# -- cursor ----------------------------------------------------------------------------------


def test_cursor_rule_format(capsys, project):
    cairn(capsys, project, "install", "cursor")
    text = (project / ".cursor/rules/cairn.mdc").read_text(encoding="utf-8")
    assert text.startswith("---\ndescription: ")
    assert "\nalwaysApply: true\n---\n" in text


def test_cursor_never_clobbers_a_user_rule(capsys, project):
    rule = project / ".cursor/rules/cairn.mdc"
    rule.parent.mkdir(parents=True)
    rule.write_text("my own rule\n", encoding="utf-8")
    code = main(["install", "cursor", "--project", str(project)])
    assert code == 1
    assert "was not written by cairn" in capsys.readouterr().err
    cairn(capsys, project, "uninstall", "cursor")
    assert rule.read_text(encoding="utf-8") == "my own rule\n"


# -- skills export ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("tool", "path"),
    [
        ("claude", ".claude/skills/bisect-a-regression/SKILL.md"),
        ("cursor", ".cursor/rules/cairn-skill-bisect-a-regression.mdc"),
    ],
)
def test_skills_export(capsys, project, tool, path):
    cairn(capsys, project, "skills", "export", "--tool", tool)
    text = (project / path).read_text(encoding="utf-8")
    assert "git bisect run" in text
    if tool == "claude":
        assert text.startswith("---\nname: bisect-a-regression\ndescription: Find the commit")
    else:
        assert "\nalwaysApply: false\n" in text
    exported = snapshot(project)
    assert len(exported) == 2  # both example skills

    out = cairn(capsys, project, "skills", "export", "--tool", tool)
    assert snapshot(project) == exported
    assert all(line.startswith("unchanged ") for line in out.splitlines())

    cairn(capsys, project, "skills", "clean", "--tool", tool)
    assert list(project.rglob("*")) == []


def test_skills_export_prunes_removed_skills_and_keeps_user_skills(capsys, project, brain):
    from cairn import Entry

    def skill(entry_id, status="active"):
        entry = Entry(entry_id, "skill", entry_id, "Do it.", status=status)
        entry.created = entry.updated = "2026-01-01"
        brain.add(entry, force=True)

    skill("keep-me")
    skill("drop-me")
    skill("old-one", status="archived")
    user_skill = project / ".claude/skills/mine/SKILL.md"
    user_skill.parent.mkdir(parents=True)
    user_skill.write_text("---\nname: mine\n---\nMine.\n", encoding="utf-8")

    cairn(capsys, project, "skills", "export", "--tool", "claude", brain=brain.root)
    skills = project / ".claude/skills"
    assert sorted(p.name for p in skills.iterdir()) == ["drop-me", "keep-me", "mine"]

    (brain.root / "skills/drop-me/SKILL.md").unlink()
    out = cairn(capsys, project, "skills", "export", "--tool", "claude", brain=brain.root)
    assert "deleted .claude/skills/drop-me/SKILL.md" in out
    assert sorted(p.name for p in skills.iterdir()) == ["keep-me", "mine"]

    cairn(capsys, project, "skills", "clean", "--tool", "claude", brain=brain.root)
    assert sorted(p.name for p in skills.iterdir()) == ["mine"]


def test_skills_export_refuses_to_overwrite_user_skill(capsys, project):
    user_skill = project / ".claude/skills/bisect-a-regression/SKILL.md"
    user_skill.parent.mkdir(parents=True)
    user_skill.write_text("mine\n", encoding="utf-8")
    code = main(
        ["skills", "export", "--tool", "claude", "--project", str(project),
         "--brain", str(EXAMPLE_BRAIN)]
    )  # fmt: skip
    assert code == 1
    assert user_skill.read_text(encoding="utf-8") == "mine\n"
