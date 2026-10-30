"""Codex (and any agent that reads ``AGENTS.md``): a managed block in ``AGENTS.md``."""

from __future__ import annotations

from .base import Adapter, Change, Context, block_install, block_uninstall, instructions

FILE = "AGENTS.md"


class CodexAdapter(Adapter):
    name = "codex"

    def install(self, ctx: Context) -> list[Change]:
        return [block_install(ctx.project / FILE, instructions(ctx))]

    def uninstall(self, ctx: Context) -> list[Change]:
        return [block_uninstall(ctx.project / FILE)]
