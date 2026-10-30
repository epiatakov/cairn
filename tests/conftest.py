from __future__ import annotations

from pathlib import Path

import pytest

from cairn import Brain, Entry

EXAMPLE_BRAIN = Path(__file__).resolve().parent.parent / "examples" / "brain"


@pytest.fixture
def brain(tmp_path: Path) -> Brain:
    return Brain.init(tmp_path / "brain")


@pytest.fixture
def write_entry(brain: Brain):
    """Write an entry file directly, bypassing ``Brain.add`` checks."""

    def write(entry_id: str, type: str = "fact", title: str | None = None, body: str = "", **kw):
        entry = Entry(
            id=entry_id,
            type=type,
            title=title or entry_id.replace("-", " "),
            body=body,
            created=kw.pop("created", "2026-01-01"),
            updated=kw.pop("updated", "2026-01-01"),
            **kw,
        )
        path = brain.path_for(type, entry_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(entry.to_markdown(), encoding="utf-8")
        brain.reload()
        return path

    return write
