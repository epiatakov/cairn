"""The entry data model: one Markdown file with frontmatter per piece of knowledge."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from . import frontmatter

TYPES = ("fact", "skill", "issue", "note")
STATUSES = ("active", "stale", "archived")
TYPE_DIRS = {"fact": "facts", "skill": "skills", "issue": "issues", "note": "notes"}
SKILL_FILE = "SKILL.md"

KNOWN_KEYS = ("id", "type", "title", "tags", "status", "created", "updated", "links")
REQUIRED_KEYS = ("id", "type", "title", "created", "updated")

ID_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
_LINK_RE = re.compile(r"\[\[([^\s\[\]|][^\[\]|]*?)(?:\|[^\[\]]*)?\]\]")
_FENCE_RE = re.compile(r"^(`{3,}|~{3,}).*?^\1[^\n]*$", re.MULTILINE | re.DOTALL)
_INLINE_CODE_RE = re.compile(r"`[^`\n]*`")
_CODE_RE = re.compile(f"{_FENCE_RE.pattern}|{_INLINE_CODE_RE.pattern}", re.MULTILINE | re.DOTALL)
MAX_SLUG_LENGTH = 60


class EntryError(ValueError):
    """Raised when an entry is malformed. ``problems`` lists every issue found."""

    def __init__(self, problems: list[str]) -> None:
        self.problems = problems
        super().__init__("; ".join(problems))


@dataclass
class Entry:
    id: str
    type: str
    title: str
    body: str = ""
    tags: list[str] = field(default_factory=list)
    status: str = "active"
    created: str = ""
    updated: str = ""
    links: list[str] = field(default_factory=list)
    extra: dict[str, frontmatter.Value] = field(default_factory=dict)
    path: Path | None = field(default=None, compare=False)

    @classmethod
    def from_markdown(cls, text: str, path: Path | None = None) -> Entry:
        """Parse an entry file. Raises :class:`EntryError` on any problem."""
        try:
            meta, body = frontmatter.parse(text)
        except frontmatter.FrontmatterError as exc:
            raise EntryError([f"frontmatter: {exc}"]) from exc

        problems = [f"missing required field '{key}'" for key in REQUIRED_KEYS if key not in meta]
        for key in ("id", "type", "title", "status", "created", "updated"):
            if isinstance(meta.get(key), list):
                problems.append(f"'{key}' must be a single value, not a list")
        for key in ("tags", "links"):
            if key in meta and not isinstance(meta[key], list):
                problems.append(f"'{key}' must be a list, e.g. {key}: [a, b]")
        if problems:
            raise EntryError(problems)

        def scalar(key: str, default: str = "") -> str:
            value = meta.get(key, default)
            assert isinstance(value, str)
            return value

        def items(key: str) -> list[str]:
            value = meta.get(key, [])
            assert isinstance(value, list)
            return value

        entry = cls(
            id=scalar("id"),
            type=scalar("type"),
            title=scalar("title"),
            body=body,
            tags=items("tags"),
            status=scalar("status", "active"),
            created=scalar("created"),
            updated=scalar("updated"),
            links=items("links"),
            extra={k: v for k, v in meta.items() if k not in KNOWN_KEYS},
            path=path,
        )
        problems = entry.validate()
        if problems:
            raise EntryError(problems)
        return entry

    def validate(self) -> list[str]:
        """Return schema problems; an empty list means the entry is valid."""
        problems = []
        if not ID_RE.fullmatch(self.id):
            problems.append(f"invalid id '{self.id}': use lowercase letters, digits and dashes")
        if self.type not in TYPES:
            problems.append(f"invalid type '{self.type}': expected one of {', '.join(TYPES)}")
        if self.status not in STATUSES:
            problems.append(
                f"invalid status '{self.status}': expected one of {', '.join(STATUSES)}"
            )
        if not self.title.strip():
            problems.append("title must not be empty")
        if any(not tag.strip() for tag in self.tags):
            problems.append("tags must not be empty strings")
        dates = {}
        for key in ("created", "updated"):
            value = getattr(self, key)
            try:
                if not _DATE_RE.fullmatch(value):
                    raise ValueError(value)
                dates[key] = date.fromisoformat(value)
            except ValueError:
                problems.append(f"invalid {key} date '{value}': expected YYYY-MM-DD")
        if len(dates) == 2 and dates["updated"] < dates["created"]:
            problems.append("'updated' is earlier than 'created'")
        return problems

    def to_markdown(self) -> str:
        meta: dict[str, frontmatter.Value] = {
            "id": self.id,
            "type": self.type,
            "title": self.title,
            "tags": list(self.tags),
            "status": self.status,
            "created": self.created,
            "updated": self.updated,
        }
        if self.links:
            meta["links"] = list(self.links)
        meta.update(self.extra)
        text = frontmatter.dump(meta)
        body = self.body.strip()
        return f"{text}\n{body}\n" if body else text

    def outgoing_links(self) -> list[str]:
        """Ids this entry points to: ``links:`` first, then ``[[id]]`` in the body."""
        seen: dict[str, None] = dict.fromkeys(self.links)
        seen.update(dict.fromkeys(body_links(self.body)))
        return list(seen)


def body_links(body: str) -> list[str]:
    """Extract ``[[id]]`` / ``[[id|label]]`` targets, ignoring code spans and fences."""
    text = _INLINE_CODE_RE.sub("", _FENCE_RE.sub("", body))
    return [match.group(1).strip() for match in _LINK_RE.finditer(text)]


def strip_links(body: str) -> str:
    """The body as prose: ``[[id]]`` removed, ``[[id|label]]`` reduced to its label.

    Code spans and fences are kept as written, so ``[[`` in shell snippets is untouched.
    """
    out, pos = [], 0
    for match in _CODE_RE.finditer(body):
        out += [_LINK_RE.sub(_link_label, body[pos : match.start()]), match.group(0)]
        pos = match.end()
    out.append(_LINK_RE.sub(_link_label, body[pos:]))
    return "".join(out)


def _link_label(match: re.Match[str]) -> str:
    label = match.group(0)[2:-2].partition("|")[2]
    return label.strip()


def slugify(text: str, max_length: int = MAX_SLUG_LENGTH) -> str:
    """Turn a title into an id: ASCII, lowercase, dash-separated, cut at a word boundary."""
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    words = re.findall(r"[a-z0-9]+", ascii_text.lower())
    slug = ""
    for word in words:
        candidate = f"{slug}-{word}" if slug else word
        if len(candidate) > max_length:
            break
        slug = candidate
    return slug or "-".join(words)[:max_length].strip("-")


def normalize_tags(raw: list[str]) -> list[str]:
    """Split comma-separated values, lowercase, drop blanks and duplicates."""
    tags = (t.strip().lower() for value in raw for t in value.split(","))
    return list(dict.fromkeys(t for t in tags if t))
