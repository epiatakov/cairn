"""Tool adapters: render one brain into each coding tool's native files.

Each adapter plans :class:`~cairn.adapters.base.Change` objects; :func:`apply` writes them.
"""

from __future__ import annotations

from ..brain import CairnError
from .base import Adapter, Change, Context, apply
from .claude import ClaudeAdapter
from .codex import CodexAdapter
from .copilot import CopilotAdapter
from .cursor import CursorAdapter

ADAPTERS: dict[str, type[Adapter]] = {
    a.name: a for a in (ClaudeAdapter, CodexAdapter, CopilotAdapter, CursorAdapter)
}
SKILL_TOOLS = tuple(name for name, a in ADAPTERS.items() if a.skills_dir)


def get_adapter(name: str) -> Adapter:
    try:
        return ADAPTERS[name]()
    except KeyError:
        raise CairnError(f"unknown tool '{name}': expected one of {', '.join(ADAPTERS)}") from None


__all__ = ["ADAPTERS", "SKILL_TOOLS", "Adapter", "Change", "Context", "apply", "get_adapter"]
