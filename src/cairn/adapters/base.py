"""Shared machinery for tool adapters.

Adapters never write directly. They return a list of :class:`Change` objects (file before and
after), which :func:`apply` writes. That gives ``--dry-run`` for free and keeps every adapter
testable without touching disk.

Ownership rules, so user content is never clobbered:

- In shared files (``CLAUDE.md``, ``AGENTS.md``, ...), cairn owns only the text between its
  begin/end markers.
- Files cairn creates whole (a Cursor rule, an exported skill) carry a marker line. A file
  without it is the user's: cairn refuses to overwrite it and never deletes it.
"""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass
from pathlib import Path

from .. import frontmatter
from ..brain import Brain, CairnError
from ..model import Entry

BLOCK_BEGIN = "<!-- cairn:begin (managed by `cairn install`; edit outside this block) -->"
BLOCK_END = "<!-- cairn:end -->"
_BLOCK_RE = re.compile(
    r"^<!-- cairn:begin[^\n]*\n.*?^<!-- cairn:end -->[^\n]*(?:\n|\Z)", re.MULTILINE | re.DOTALL
)
SKILL_MARKER = "<!-- managed by `cairn skills export`; edit the brain entry, not this file -->"


@dataclass(frozen=True)
class Context:
    """Where to install, and the brain path to write into generated files."""

    project: Path
    brain: str  # relative to the project when the brain lives inside it, else absolute

    @classmethod
    def create(cls, project: Path, brain: Path) -> Context:
        project, brain = project.resolve(), brain.resolve()
        try:
            shown = brain.relative_to(project).as_posix() or "."
        except ValueError:
            shown = brain.as_posix()
        return cls(project, shown)

    @property
    def brain_arg(self) -> str:
        """The brain path, quoted for a shell command line."""
        return shlex.quote(self.brain)


@dataclass(frozen=True)
class Change:
    """One file's planned state. ``None`` means the file does not exist (before) or is
    deleted (after)."""

    path: Path
    before: str | None
    after: str | None

    @property
    def action(self) -> str:
        if self.before == self.after:
            return "unchanged"
        if self.after is None:
            return "delete"
        return "create" if self.before is None else "update"


class Adapter:
    """One coding tool. Subclasses implement :meth:`install` and :meth:`uninstall`."""

    name = ""
    #: Project-relative folder for exported skills; ``None`` if the tool has no such concept.
    skills_dir: str | None = None

    def install(self, ctx: Context) -> list[Change]:
        raise NotImplementedError

    def uninstall(self, ctx: Context) -> list[Change]:
        raise NotImplementedError

    def skill_file(self, entry_id: str) -> str:
        """Path of an exported skill, relative to :attr:`skills_dir`."""
        raise NotImplementedError

    def render_skill(self, entry: Entry, ctx: Context) -> str:
        raise NotImplementedError

    def export_skills(self, brain: Brain, ctx: Context) -> list[Change]:
        """Write every live skill, and delete exported skills that left the brain."""
        if self.skills_dir is None:
            raise CairnError(f"'{self.name}' has no skills folder to export to")
        wanted = {}
        for entry in brain.filter(type="skill"):
            if entry.status != "archived":
                wanted[ctx.project / self.skills_dir / self.skill_file(entry.id)] = entry
        changes = [
            owned_file(path, self.render_skill(e, ctx), SKILL_MARKER) for path, e in wanted.items()
        ]
        changes += [c for c in self.clean_skills(ctx) if c.path not in wanted]
        return changes

    def clean_skills(self, ctx: Context) -> list[Change]:
        """Delete every skill file cairn exported (files without the marker are kept)."""
        if self.skills_dir is None:
            raise CairnError(f"'{self.name}' has no skills folder to export to")
        folder = ctx.project / self.skills_dir
        pattern = self.skill_file("*")
        return [
            Change(path, text, None)
            for path in sorted(folder.glob(pattern))
            if (text := read(path)) is not None and SKILL_MARKER in text
        ]


def instructions(ctx: Context, *, hook: bool = False) -> str:
    """The text every tool gets: recall before work, capture durable facts after."""
    recall = (
        "A recall hook adds relevant entries to each prompt. For more, run"
        if hook
        else "Before starting a task, run this and read the entries it points to"
    )
    return f"""\
## cairn brain

This project shares a cairn brain at `{ctx.brain}`: plain-Markdown facts, known issues,
skills and notes used by every coding agent here. `{ctx.brain}/INDEX.md` lists them all.

- {recall}:
  `cairn recall "<task in a few words>" --brain {ctx.brain_arg}`
- When a task teaches something durable (a tool quirk, a fix, a procedure), add it:
  `cairn add fact|issue|skill|note --title "..." --tags a,b --body "..." --brain {ctx.brain_arg}`
  Skip trivial turns. If `cairn add` reports a near-duplicate, update that entry instead.
"""


# -- managed blocks in shared files ---------------------------------------------------------


def upsert_block(text: str, body: str) -> str:
    """Insert or replace the cairn block. Text outside the markers is kept byte for byte."""
    block = f"{BLOCK_BEGIN}\n{body.rstrip()}\n{BLOCK_END}\n"
    match = _find_block(text)
    if match:
        return text[: match.start()] + block + text[match.end() :]
    if not text.strip():
        return block
    return text + ("" if text.endswith("\n") else "\n") + "\n" + block


def remove_block(text: str) -> str:
    """Remove the cairn block and the blank line :func:`upsert_block` put before it."""
    match = _find_block(text)
    if not match:
        return text
    before, after = text[: match.start()], text[match.end() :]
    if not after and before.endswith("\n\n"):
        before = before[:-1]
    return before + after


def _find_block(text: str) -> re.Match[str] | None:
    match = _BLOCK_RE.search(text)
    if match is None and "<!-- cairn:begin" in text:
        raise CairnError("found a cairn:begin marker without a matching cairn:end; fix it by hand")
    return match


def block_install(path: Path, body: str) -> Change:
    before = read(path)
    return Change(path, before, upsert_block(before or "", body))


def block_uninstall(path: Path) -> Change:
    before = read(path)
    if before is None:
        return Change(path, None, None)
    after = remove_block(before)
    return Change(path, before, after if after.strip() else None)


# -- files cairn owns whole ------------------------------------------------------------------


def owned_file(path: Path, content: str, marker: str) -> Change:
    before = read(path)
    if before is not None and marker not in before:
        raise CairnError(f"{path} exists and was not written by cairn; move it away first")
    return Change(path, before, content)


def owned_file_removal(path: Path, marker: str) -> Change:
    before = read(path)
    if before is None or marker not in before:
        return Change(path, before, before)
    return Change(path, before, None)


def with_frontmatter(
    meta: dict[str, frontmatter.Value], body: str, *, flags: dict[str, bool] | None = None
) -> str:
    """``meta`` holds strings; ``flags`` are written as YAML booleans (``true``/``false``),
    which cairn's own frontmatter writer would quote."""
    head = frontmatter.dump(meta).removesuffix("---\n")
    head += "".join(f"{key}: {str(value).lower()}\n" for key, value in (flags or {}).items())
    return f"{head}---\n{body.rstrip()}\n"


# -- reading and writing ---------------------------------------------------------------------


def read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except (OSError, UnicodeDecodeError) as exc:
        raise CairnError(f"cannot read {path}: {exc}") from exc


def apply(changes: list[Change], project: Path) -> None:
    """Write the planned changes. Deleting a file also removes parent folders left empty."""
    for change in changes:
        if change.action == "unchanged":
            continue
        if change.after is None:
            change.path.unlink()
            _prune_empty_dirs(change.path.parent, project)
        else:
            change.path.parent.mkdir(parents=True, exist_ok=True)
            with change.path.open("w", encoding="utf-8", newline="\n") as fh:
                fh.write(change.after)


def _prune_empty_dirs(folder: Path, stop: Path) -> None:
    stop = stop.resolve()
    while folder.resolve() != stop and stop in folder.resolve().parents:
        try:
            folder.rmdir()
        except OSError:
            return
        folder = folder.parent
