"""GitHub Copilot: a managed block in ``.github/copilot-instructions.md``."""

from __future__ import annotations

from .base import Adapter, Change, Context, block_install, block_uninstall, instructions

FILE = ".github/copilot-instructions.md"


class CopilotAdapter(Adapter):
    name = "copilot"

    def install(self, ctx: Context) -> list[Change]:
        return [block_install(ctx.project / FILE, instructions(ctx))]

    def uninstall(self, ctx: Context) -> list[Change]:
        return [block_uninstall(ctx.project / FILE)]
