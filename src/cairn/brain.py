"""A brain is a folder of Markdown entries. This module loads, queries and writes it."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from . import dedupe
from .model import SKILL_FILE, TYPE_DIRS, TYPES, Entry, EntryError, slugify
from .search import Hit, Index

DEFAULT_BRAIN = "brain"
ENV_VAR = "CAIRN_BRAIN"
INDEX_FILE = "INDEX.md"
README_FILE = "README.md"


class CairnError(Exception):
    """A user-facing error: the CLI prints the message and exits non-zero."""


class DuplicateError(CairnError):
    def __init__(self, matches: list[dedupe.Match]) -> None:
        self.matches = matches
        ids = ", ".join(f"{m.entry.id} ({m.similarity:.2f})" for m in matches)
        super().__init__(f"looks like a near-duplicate of: {ids}")


@dataclass(frozen=True)
class Problem:
    path: Path | None
    severity: str  # "error" | "warning"
    code: str
    message: str


def resolve_root(explicit: str | os.PathLike[str] | None = None) -> Path:
    """``--brain`` beats ``$CAIRN_BRAIN`` beats ``./brain``."""
    return Path(explicit or os.environ.get(ENV_VAR) or DEFAULT_BRAIN)


class Brain:
    def __init__(self, root: str | os.PathLike[str]) -> None:
        self.root = Path(root)
        self._entries: list[Entry] | None = None
        self._problems: list[Problem] = []
        self._index: Index | None = None

    @classmethod
    def open(cls, root: str | os.PathLike[str]) -> Brain:
        brain = cls(root)
        if not brain.root.is_dir():
            raise CairnError(f"no brain at '{brain.root}' (run 'cairn init' or pass --brain)")
        return brain

    @classmethod
    def init(cls, root: str | os.PathLike[str]) -> Brain:
        """Create the folder layout and a README. Safe to run on an existing brain."""
        brain = cls(root)
        for dirname in TYPE_DIRS.values():
            (brain.root / dirname).mkdir(parents=True, exist_ok=True)
        readme = brain.root / README_FILE
        if not readme.exists():
            _write(readme, BRAIN_README)
        return brain

    # -- reading ---------------------------------------------------------

    @property
    def entries(self) -> list[Entry]:
        """Every valid entry, in a stable order (type, then path)."""
        if self._entries is None:
            self._load()
        assert self._entries is not None
        return self._entries

    @property
    def problems(self) -> list[Problem]:
        """Files that could not be read or parsed during loading."""
        self.entries  # noqa: B018 - loads on first access
        return self._problems

    def entry_files(self) -> list[tuple[str, Path]]:
        """``(type, path)`` for every file in an entry location."""
        found = []
        for type_, dirname in TYPE_DIRS.items():
            folder = self.root / dirname
            pattern = f"*/{SKILL_FILE}" if type_ == "skill" else "*.md"
            found.extend((type_, p) for p in sorted(folder.glob(pattern)) if p.is_file())
        return found

    def _load(self) -> None:
        entries, problems = [], []
        for _, path in self.entry_files():
            try:
                text = path.read_text(encoding="utf-8")
                entries.append(Entry.from_markdown(text, path=path))
            except (OSError, UnicodeDecodeError) as exc:
                problems.append(Problem(path, "error", "unreadable", str(exc)))
            except EntryError as exc:
                problems.extend(Problem(path, "error", "invalid-entry", p) for p in exc.problems)
        self._entries, self._problems, self._index = entries, problems, None

    def reload(self) -> None:
        self._entries = None

    def get(self, entry_id: str) -> Entry | None:
        return next((e for e in self.entries if e.id == entry_id), None)

    def filter(self, *, type: str | None = None, status: str | None = None) -> list[Entry]:
        return [
            e
            for e in self.entries
            if (type is None or e.type == type) and (status is None or e.status == status)
        ]

    def search(self, query: str, **kwargs) -> list[Hit]:
        """BM25F search; see :meth:`cairn.search.Index.search` for options."""
        if self._index is None:
            self._index = Index(self.entries)
        return self._index.search(query, **kwargs)

    def relpath(self, path: Path | None) -> str:
        if path is None:
            return ""
        try:
            return path.relative_to(self.root).as_posix()
        except ValueError:
            return path.as_posix()

    # -- writing ---------------------------------------------------------

    def path_for(self, type: str, entry_id: str) -> Path:
        folder = self.root / TYPE_DIRS[type]
        return folder / entry_id / SKILL_FILE if type == "skill" else folder / f"{entry_id}.md"

    def unique_id(self, title: str) -> str:
        base = slugify(title)
        if not base:
            raise CairnError("cannot derive an id from the title; pass --id")
        taken = {e.id for e in self.entries} | {p.stem for _, p in self.entry_files()}
        taken |= {p.parent.name for t, p in self.entry_files() if t == "skill"}
        candidate, n = base, 2
        while candidate in taken:
            candidate, n = f"{base}-{n}", n + 1
        return candidate

    def new_entry(
        self,
        type: str,
        title: str,
        body: str = "",
        *,
        tags: list[str] | None = None,
        entry_id: str | None = None,
        status: str = "active",
        links: list[str] | None = None,
        today: date | None = None,
    ) -> Entry:
        """Build (but do not write) an entry with a fresh id and today's dates."""
        if type not in TYPES:
            raise CairnError(f"unknown type '{type}': expected one of {', '.join(TYPES)}")
        stamp = (today or date.today()).isoformat()
        return Entry(
            id=entry_id or self.unique_id(title),
            type=type,
            title=title.strip(),
            body=body.strip(),
            tags=list(tags or []),
            status=status,
            created=stamp,
            updated=stamp,
            links=list(links or []),
        )

    def add(self, entry: Entry, *, force: bool = False) -> Path:
        """Validate, check for near-duplicates (unless ``force``), and write ``entry``."""
        problems = entry.validate()
        if problems:
            raise CairnError("invalid entry: " + "; ".join(problems))
        path = self.path_for(entry.type, entry.id)
        if self.get(entry.id) or path.exists():
            raise CairnError(f"an entry with id '{entry.id}' already exists")
        if not force:
            live = [e for e in self.entries if e.status != "archived"]
            matches = dedupe.find_similar(entry.title, entry.body, live)
            if matches:
                raise DuplicateError(matches)
        path.parent.mkdir(parents=True, exist_ok=True)
        _write(path, entry.to_markdown(), exclusive=True)
        entry.path = path
        self.entries.append(entry)
        self._index = None
        return path

    def render_index(self) -> str:
        lines = [
            "# Brain index",
            "",
            "<!-- Generated by `cairn index`. Do not edit by hand. -->",
        ]
        for type_, dirname in TYPE_DIRS.items():
            group = sorted(self.filter(type=type_), key=lambda e: e.id)
            lines += ["", f"## {dirname.capitalize()} ({len(group)})", ""]
            if not group:
                lines.append("_None yet._")
            for e in group:
                status = "" if e.status == "active" else f" _({e.status})_"
                tags = f" `{', '.join(e.tags)}`" if e.tags else ""
                lines.append(f"- [{e.id}]({self.relpath(e.path)}): {e.title}{status}{tags}")
        return "\n".join(lines) + "\n"

    def write_index(self) -> Path:
        path = self.root / INDEX_FILE
        _write(path, self.render_index())
        return path


def _write(path: Path, text: str, *, exclusive: bool = False) -> None:
    with path.open("x" if exclusive else "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


BRAIN_README = """\
# Brain

A [cairn](https://github.com/epiatakov/cairn) brain: plain Markdown that coding agents
recall before work and add to after it.

## Layout

| Folder | Holds |
| --- | --- |
| `facts/<id>.md` | Durable truths about tools, systems and code |
| `skills/<id>/SKILL.md` | Step-by-step procedures (extra files may sit next to `SKILL.md`) |
| `issues/<id>.md` | Known tool failures with symptoms and workarounds |
| `notes/<id>.md` | Everything else worth keeping |

`INDEX.md` is generated by `cairn index`.

## Entry format

```markdown
---
id: git-autocrlf-rewrites-line-endings
type: fact
title: Git autocrlf rewrites line endings on Windows checkouts
tags: [git, windows]
status: active
created: 2026-01-31
updated: 2026-01-31
links: [shell-script-bad-interpreter-crlf]
---
Body in Markdown. Link other entries with [[some-id]].
```

`status` is `active`, `stale` (kept, but double-check before trusting) or `archived`
(hidden from search).

## Commands

```
cairn add fact --title "..." --tags a,b --body -
cairn search "query" [--json]
cairn lint
cairn index
```
"""
