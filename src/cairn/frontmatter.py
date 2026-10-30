"""A small, hand-written parser for the YAML-like frontmatter used by brain entries.

Supported subset (everything cairn writes stays valid YAML):

    ---
    key: plain scalar
    quoted: "double \\"quoted\\"" or 'single ''quoted'''
    inline: [a, b, "c, d"]
    block:
      - a
      - b
    # full-line comments
    ---

Values are always strings or lists of strings; no type coercion happens here.
Trailing ``# comments`` on value lines are not supported, so ``title: Issue #12``
keeps the ``#12``.
"""

from __future__ import annotations

import re

Value = str | list[str]

_KEY_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_-]*")
_BLOCK_ITEM_RE = re.compile(r"\s+-(?:\s+(.*))?$")
_YAML_INDICATORS = "[]{}&*!|>'\"%@`#,?:-"
_YAML_KEYWORDS = {"true", "false", "yes", "no", "on", "off", "null", "~"}
_NUMBER_RE = re.compile(r"[-+]?(\d+(\.\d*)?|\.\d+)([eE][-+]?\d+)?")


class FrontmatterError(ValueError):
    """Raised when frontmatter cannot be parsed. ``line`` is 1-based."""

    def __init__(self, message: str, line: int | None = None) -> None:
        self.message = message
        self.line = line
        super().__init__(f"line {line}: {message}" if line else message)


def parse(text: str) -> tuple[dict[str, Value], str]:
    """Split ``text`` into ``(metadata, body)``."""
    lines = text.lstrip("﻿").replace("\r\n", "\n").split("\n")
    if not lines or lines[0].strip() != "---":
        raise FrontmatterError("file must start with '---'", 1)
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        raise FrontmatterError("missing closing '---'", 1) from None

    meta: dict[str, Value] = {}
    i = 1
    while i < end:
        line, lineno = lines[i], i + 1
        i += 1
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if line[0].isspace():
            raise FrontmatterError("unexpected indentation", lineno)
        key, sep, raw = line.partition(":")
        key = key.strip()
        if not sep or not _KEY_RE.fullmatch(key):
            raise FrontmatterError("expected 'key: value'", lineno)
        if key in meta:
            raise FrontmatterError(f"duplicate key '{key}'", lineno)
        raw = raw.strip()
        if raw:
            meta[key] = _parse_value(raw, lineno)
            continue
        # An empty value may open a block list.
        items: list[str] = []
        while i < end:
            match = _BLOCK_ITEM_RE.match(lines[i])
            if not match:
                break
            items.append(_parse_scalar((match.group(1) or "").strip(), i + 1))
            i += 1
        meta[key] = items if items else ""

    body = "\n".join(lines[end + 1 :]).lstrip("\n").rstrip()
    return meta, body


def dump(meta: dict[str, Value]) -> str:
    """Render ``meta`` as a frontmatter block, including both ``---`` fences."""
    out = ["---"]
    for key, value in meta.items():
        if not _KEY_RE.fullmatch(key):
            raise ValueError(f"invalid frontmatter key: {key!r}")
        if isinstance(value, list):
            items = ", ".join(_quote(v, in_list=True) for v in value)
            out.append(f"{key}: [{items}]")
        else:
            out.append(f"{key}: {_quote(value)}")
    out.append("---")
    return "\n".join(out) + "\n"


def _parse_value(raw: str, lineno: int) -> Value:
    if raw.startswith("["):
        if not raw.endswith("]"):
            raise FrontmatterError("unterminated list, expected ']'", lineno)
        return _parse_inline_list(raw[1:-1], lineno)
    return _parse_scalar(raw, lineno)


def _parse_scalar(raw: str, lineno: int) -> str:
    if raw[:1] == '"':
        if len(raw) < 2 or not raw.endswith('"') or _odd_escape(raw):
            raise FrontmatterError("unterminated double-quoted string", lineno)
        return re.sub(r'\\([\\"])', r"\1", raw[1:-1])
    if raw[:1] == "'":
        if len(raw) < 2 or not raw.endswith("'"):
            raise FrontmatterError("unterminated single-quoted string", lineno)
        return raw[1:-1].replace("''", "'")
    return raw


def _odd_escape(raw: str) -> bool:
    """True if the closing quote of ``raw`` is escaped by an odd run of backslashes."""
    inner = raw[1:-1]
    run = len(inner) - len(inner.rstrip("\\"))
    return run % 2 == 1


def _parse_inline_list(inner: str, lineno: int) -> list[str]:
    items: list[str] = []
    buf: list[str] = []
    quote: str | None = None
    i = 0
    while i < len(inner):
        ch = inner[i]
        if quote:
            buf.append(ch)
            if ch == "\\" and quote == '"' and i + 1 < len(inner):
                buf.append(inner[i + 1])
                i += 1
            elif ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
            buf.append(ch)
        elif ch == ",":
            items.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
        i += 1
    if quote:
        raise FrontmatterError("unterminated quoted list item", lineno)
    items.append("".join(buf).strip())
    return [_parse_scalar(item, lineno) for item in items if item]


def _quote(value: str, *, in_list: bool = False) -> str:
    if "\n" in value or "\r" in value:
        raise ValueError("frontmatter values must be single-line")
    if _needs_quotes(value) or (in_list and any(c in value for c in ",[]{}")):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return value


def _needs_quotes(value: str) -> bool:
    return (
        not value
        or value != value.strip()
        or value[0] in _YAML_INDICATORS
        or ": " in value
        or " #" in value
        or value.endswith(":")
        or value.lower() in _YAML_KEYWORDS
        or bool(_NUMBER_RE.fullmatch(value))
    )
