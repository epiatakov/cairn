"""The ``cairn`` command line."""

from __future__ import annotations

import argparse
import contextlib
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from . import __version__
from .brain import INDEX_FILE, Brain, CairnError, DuplicateError, resolve_root
from .lint import lint
from .model import STATUSES, TYPES, Entry, normalize_tags

JSON_SCHEMA_VERSION = 1


def main(argv: Sequence[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        with contextlib.suppress(AttributeError, ValueError):
            stream.reconfigure(errors="replace")  # type: ignore[union-attr]
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except CairnError as exc:
        print(f"cairn: error: {exc}", file=sys.stderr)
        return 1


def build_parser() -> argparse.ArgumentParser:
    brain_help = "brain folder (default: $CAIRN_BRAIN or ./brain)"
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--brain", default=argparse.SUPPRESS, metavar="DIR", help=brain_help)

    parser = argparse.ArgumentParser(
        prog="cairn",
        description="One second brain for every coding agent.",
    )
    parser.add_argument("--version", action="version", version=f"cairn {__version__}")
    parser.add_argument("--brain", default=None, metavar="DIR", help=brain_help)
    sub = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    p = sub.add_parser("init", parents=[common], help="create a brain folder")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("add", parents=[common], help="add an entry (refuses near-duplicates)")
    p.add_argument("type", choices=TYPES)
    p.add_argument("--title", required=True)
    p.add_argument("--tags", action="append", default=[], help="comma-separated; repeatable")
    body = p.add_mutually_exclusive_group()
    body.add_argument("--body", help="entry body; '-' reads stdin")
    body.add_argument("--body-file", type=Path, metavar="PATH")
    p.add_argument("--id", dest="entry_id", help="explicit id (default: slug of the title)")
    p.add_argument("--status", choices=STATUSES, default="active")
    p.add_argument("--link", action="append", default=[], metavar="ID", help="repeatable")
    p.add_argument("--force", action="store_true", help="add even if near-duplicates exist")
    p.set_defaults(func=cmd_add)

    p = sub.add_parser("search", parents=[common], help="BM25 search (skips archived)")
    p.add_argument("query", nargs="+")
    p.add_argument("--type", choices=TYPES)
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--json", action="store_true", help="stable machine-readable output")
    p.set_defaults(func=cmd_search)

    p = sub.add_parser("show", parents=[common], help="print one entry")
    p.add_argument("id")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_show)

    p = sub.add_parser("list", parents=[common], help="list entries")
    p.add_argument("--type", choices=TYPES)
    p.add_argument("--status", choices=STATUSES)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("lint", parents=[common], help="check frontmatter, ids, links, duplicates")
    p.add_argument("--strict", action="store_true", help="fail on warnings too")
    p.set_defaults(func=cmd_lint)

    p = sub.add_parser("index", parents=[common], help=f"regenerate {INDEX_FILE}")
    p.add_argument("--check", action="store_true", help=f"fail if {INDEX_FILE} is out of date")
    p.set_defaults(func=cmd_index)
    return parser


def _open(args: argparse.Namespace) -> Brain:
    return Brain.open(resolve_root(args.brain))


def _emit_json(payload: dict) -> None:
    print(json.dumps({"version": JSON_SCHEMA_VERSION, **payload}, indent=2))


def entry_to_dict(brain: Brain, entry: Entry, *, body: bool = False) -> dict:
    data = {
        "id": entry.id,
        "type": entry.type,
        "title": entry.title,
        "status": entry.status,
        "tags": entry.tags,
        "created": entry.created,
        "updated": entry.updated,
        "links": entry.outgoing_links(),
        "path": brain.relpath(entry.path),
    }
    if body:
        data["body"] = entry.body
    return data


def cmd_init(args: argparse.Namespace) -> int:
    brain = Brain.init(resolve_root(args.brain))
    print(f"initialized brain at {brain.root}")
    return 0


def cmd_add(args: argparse.Namespace) -> int:
    brain = _open(args)
    if args.body_file:
        try:
            body = args.body_file.read_text(encoding="utf-8")
        except OSError as exc:
            raise CairnError(f"cannot read --body-file: {exc}") from exc
    elif args.body == "-":
        body = sys.stdin.read()
    else:
        body = args.body or ""
    entry = brain.new_entry(
        args.type,
        args.title,
        body,
        tags=normalize_tags(args.tags),
        entry_id=args.entry_id,
        status=args.status,
        links=args.link,
    )
    try:
        path = brain.add(entry, force=args.force)
    except DuplicateError as exc:
        lines = ["refusing to add a near-duplicate (use --force to add anyway):"]
        lines += [f"  {m.entry.id} ({m.similarity:.2f}) {m.entry.title}" for m in exc.matches]
        raise CairnError("\n".join(lines)) from exc
    print(f"added {entry.id} ({brain.relpath(path)})")
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    if args.limit < 1:
        raise CairnError("--limit must be at least 1")
    brain = _open(args)
    query = " ".join(args.query)
    hits = brain.search(query, type=args.type, limit=args.limit)
    if args.json:
        results = [
            {**entry_to_dict(brain, h.entry), "score": round(h.score, 4), "snippet": h.snippet}
            for h in hits
        ]
        _emit_json({"query": query, "results": results})
        return 0
    if not hits:
        print("no matches")
    for h in hits:
        flag = "" if h.entry.status == "active" else f" [{h.entry.status}]"
        print(f"{h.score:6.2f}  {h.entry.type:<5}  {h.entry.id}{flag}")
        print(f"        {h.entry.title}")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    brain = _open(args)
    entry = brain.get(args.id)
    if entry is None:
        from difflib import get_close_matches

        close = get_close_matches(args.id, [e.id for e in brain.entries], n=3)
        hint = f"; did you mean: {', '.join(close)}?" if close else ""
        raise CairnError(f"no entry with id '{args.id}'{hint}")
    if args.json:
        _emit_json({"entry": entry_to_dict(brain, entry, body=True)})
    else:
        print(entry.to_markdown(), end="")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    brain = _open(args)
    entries = brain.filter(type=args.type, status=args.status)
    if args.json:
        _emit_json({"entries": [entry_to_dict(brain, e) for e in entries]})
        return 0
    width = max((len(e.id) for e in entries), default=0)
    for e in entries:
        print(f"{e.id:<{width}}  {e.type:<5}  {e.status:<8}  {e.title}")
    return 0


def cmd_lint(args: argparse.Namespace) -> int:
    brain = _open(args)
    problems = lint(brain)
    for p in problems:
        print(f"{brain.relpath(p.path) or brain.root}: {p.severity} [{p.code}] {p.message}")
    errors = sum(p.severity == "error" for p in problems)
    warnings = len(problems) - errors
    print(f"{len(brain.entries)} entries, {errors} error(s), {warnings} warning(s)")
    return 1 if errors or (args.strict and warnings) else 0


def cmd_index(args: argparse.Namespace) -> int:
    brain = _open(args)
    path = brain.root / INDEX_FILE
    if args.check:
        current = path.read_text(encoding="utf-8") if path.exists() else ""
        if current.replace("\r\n", "\n") != brain.render_index():
            print(f"{INDEX_FILE} is out of date; run 'cairn index'")
            return 1
        print(f"{INDEX_FILE} is up to date")
        return 0
    brain.write_index()
    print(f"wrote {brain.relpath(path)} ({len(brain.entries)} entries)")
    return 0
