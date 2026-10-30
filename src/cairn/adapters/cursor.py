"""Cursor: an always-applied project rule, plus skills exported as agent-requested rules."""

from __future__ import annotations

from ..model import Entry
from .base import (
    SKILL_MARKER,
    Adapter,
    Change,
    Context,
    instructions,
    owned_file,
    owned_file_removal,
    with_frontmatter,
)

RULE = ".cursor/rules/cairn.mdc"
RULE_MARKER = "<!-- managed by `cairn install cursor`; run `cairn uninstall cursor` to remove -->"


class CursorAdapter(Adapter):
    name = "cursor"
    skills_dir = ".cursor/rules"

    def install(self, ctx: Context) -> list[Change]:
        meta = {"description": "Recall from and add to the shared cairn brain"}
        body = f"{RULE_MARKER}\n\n{instructions(ctx)}"
        text = with_frontmatter(meta, body, flags={"alwaysApply": True})
        return [owned_file(ctx.project / RULE, text, RULE_MARKER)]

    def uninstall(self, ctx: Context) -> list[Change]:
        return [owned_file_removal(ctx.project / RULE, RULE_MARKER)]

    def skill_file(self, entry_id: str) -> str:
        return f"cairn-skill-{entry_id}.mdc"

    def render_skill(self, entry: Entry, ctx: Context) -> str:
        source = f"{ctx.brain}/skills/{entry.id}/SKILL.md"
        body = f"{SKILL_MARKER}\n<!-- source: {source} -->\n\n{entry.body}"
        return with_frontmatter({"description": entry.title}, body, flags={"alwaysApply": False})
