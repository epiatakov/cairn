"""Claude Code: a ``UserPromptSubmit`` recall hook, a ``CLAUDE.md`` block, skills export."""

from __future__ import annotations

import json
from pathlib import Path

from ..brain import CairnError
from ..model import Entry
from .base import (
    SKILL_MARKER,
    Adapter,
    Change,
    Context,
    block_install,
    block_uninstall,
    instructions,
    read,
    with_frontmatter,
)

SETTINGS = ".claude/settings.json"
EVENT = "UserPromptSubmit"
HOOK_TIMEOUT = 10  # seconds; recall takes milliseconds, this only bounds a stuck process


def hook_command(ctx: Context) -> str:
    return f"cairn recall --format claude-hook --brain {ctx.brain_arg}"


def is_cairn_hook(hook: object) -> bool:
    """True for a hook entry that ``cairn install claude`` wrote (any brain path)."""
    if not isinstance(hook, dict) or not isinstance(hook.get("command"), str):
        return False
    command = hook["command"]
    return command.startswith("cairn recall ") and "--format claude-hook" in command


class ClaudeAdapter(Adapter):
    name = "claude"
    skills_dir = ".claude/skills"

    def install(self, ctx: Context) -> list[Change]:
        return [
            _settings_change(ctx.project / SETTINGS, lambda s: _add_hook(s, hook_command(ctx))),
            block_install(ctx.project / "CLAUDE.md", instructions(ctx, hook=True)),
        ]

    def uninstall(self, ctx: Context) -> list[Change]:
        return [
            _settings_change(ctx.project / SETTINGS, _remove_hooks),
            block_uninstall(ctx.project / "CLAUDE.md"),
        ]

    def skill_file(self, entry_id: str) -> str:
        return f"{entry_id}/SKILL.md"

    def render_skill(self, entry: Entry, ctx: Context) -> str:
        source = f"{ctx.brain}/skills/{entry.id}/SKILL.md"
        body = f"{SKILL_MARKER}\n<!-- source: {source} -->\n\n{entry.body}"
        return with_frontmatter({"name": entry.id, "description": entry.title}, body)


def _settings_change(path: Path, edit) -> Change:
    before = read(path)
    if before is None:
        settings: dict = {}
    else:
        try:
            settings = json.loads(before) if before.strip() else {}
        except json.JSONDecodeError as exc:
            raise CairnError(f"{path} is not valid JSON ({exc}); fix it first") from exc
        if not isinstance(settings, dict):
            raise CairnError(f"{path} must contain a JSON object")
    if not edit(settings):
        return Change(path, before, before)
    after = json.dumps(settings, indent=2) + "\n" if settings else None
    return Change(path, before, after)


def _groups(settings: dict) -> list:
    hooks = settings.get("hooks", {})
    if not isinstance(hooks, dict) or not isinstance(hooks.get(EVENT, []), list):
        raise CairnError(f"unexpected shape for hooks.{EVENT} in {SETTINGS}; fix it first")
    return hooks.get(EVENT, [])


def _add_hook(settings: dict, command: str) -> bool:
    """Add the recall hook, or update the brain path of an existing one. Returns True if the
    settings changed."""
    ours = {"type": "command", "command": command, "timeout": HOOK_TIMEOUT}
    for group in _groups(settings):
        for i, hook in enumerate(group.get("hooks", []) if isinstance(group, dict) else []):
            if is_cairn_hook(hook):
                if hook == ours:
                    return False
                group["hooks"][i] = ours
                return True
    settings.setdefault("hooks", {}).setdefault(EVENT, []).append({"hooks": [ours]})
    return True


def _remove_hooks(settings: dict) -> bool:
    """Remove cairn's hooks, and any group, event or ``hooks`` key they leave empty."""
    groups, changed = _groups(settings), False
    for group in list(groups):
        if not isinstance(group, dict) or not isinstance(group.get("hooks"), list):
            continue
        kept = [h for h in group["hooks"] if not is_cairn_hook(h)]
        if len(kept) == len(group["hooks"]):
            continue
        changed = True
        if kept:
            group["hooks"] = kept
        else:
            groups.remove(group)
    if changed and not groups:
        del settings["hooks"][EVENT]
        if not settings["hooks"]:
            del settings["hooks"]
    return changed
