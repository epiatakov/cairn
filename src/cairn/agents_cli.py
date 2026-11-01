"""CLI commands that connect cairn to coding agents: ``recall``, ``install``, ``uninstall``
and ``skills``. :func:`register` adds them to the main parser in :mod:`cairn.cli`."""

from __future__ import annotations

import argparse
import contextlib
import difflib
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from . import recall as recall_mod
from .adapters import ADAPTERS, SKILL_TOOLS, Change, Context, apply, get_adapter
from .brain import Brain, CairnError, resolve_root

FORMATS = ("text", "json", "claude-hook")


def register(sub: argparse._SubParsersAction, common: argparse.ArgumentParser) -> None:
    p = sub.add_parser("recall", parents=[common], help="relevant pointers for a task prompt")
    p.add_argument("prompt", nargs="*", help="the task (read from stdin with claude-hook)")
    p.add_argument("--limit", type=int, default=recall_mod.DEFAULT_LIMIT)
    p.add_argument(
        "--min-score",
        type=float,
        default=recall_mod.DEFAULT_MIN_SCORE,
        metavar="S",
        help=f"drop weaker hits (default: {recall_mod.DEFAULT_MIN_SCORE})",
    )
    p.add_argument(
        "--min-terms",
        type=int,
        default=recall_mod.DEFAULT_MIN_TERMS,
        metavar="N",
        help="drop hits sharing fewer than N distinct words with the prompt "
        f"(default: {recall_mod.DEFAULT_MIN_TERMS})",
    )
    p.add_argument(
        "--min-words",
        type=int,
        default=recall_mod.DEFAULT_MIN_WORDS,
        metavar="N",
        help="skip prompts with fewer content words, or only chit-chat; 0 turns this off "
        f"(default: {recall_mod.DEFAULT_MIN_WORDS})",
    )
    p.add_argument(
        "--format",
        choices=FORMATS,
        default="text",
        help="claude-hook reads Claude Code UserPromptSubmit JSON on stdin and never fails",
    )
    p.add_argument(
        "--json", action="store_const", const="json", dest="format", help="same as --format json"
    )
    p.set_defaults(func=cmd_recall)

    tools = ", ".join(ADAPTERS)
    for name, func, verb in (
        ("install", cmd_install, "wire cairn into"),
        ("uninstall", cmd_uninstall, "remove cairn from"),
    ):
        p = sub.add_parser(name, parents=[common], help=f"{verb} a tool ({tools})")
        p.add_argument("tool", choices=list(ADAPTERS))
        _project_args(p)
        p.set_defaults(func=func)

    p = sub.add_parser("skills", help="export brain skills to a tool's skills folder")
    skills = p.add_subparsers(dest="skills_command", required=True, metavar="ACTION")
    for name, help_ in (
        ("export", "write every live skill; delete exported skills that left the brain"),
        ("clean", "delete every skill file cairn exported"),
    ):
        p = skills.add_parser(name, parents=[common], help=help_)
        p.add_argument("--tool", required=True, choices=list(SKILL_TOOLS))
        _project_args(p)
        p.set_defaults(func=cmd_skills)


def _project_args(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--project", type=Path, default=Path("."), metavar="DIR", help="default: current dir"
    )
    p.add_argument("--dry-run", action="store_true", help="show the changes, write nothing")


def is_claude_hook(argv: Sequence[str] | None) -> bool:
    """True when the command line asks for a Claude Code hook mode (``cairn recall`` or
    ``cairn issue match``), which must never fail: exit code 2 would block the prompt."""
    argv = list(sys.argv[1:] if argv is None else argv)
    return "claude-hook" in argv or "--format=claude-hook" in argv


def read_hook_payload() -> object:
    """The hook's JSON payload from stdin, decoded as UTF-8 whatever the console encoding."""
    buffer = getattr(sys.stdin, "buffer", None)
    raw = buffer.read().decode("utf-8", "replace") if buffer else sys.stdin.read()
    return json.loads(raw)


def hook_brain_root(brain: str | None, payload: object) -> Path:
    """``--brain`` for a hook. A relative path is resolved against the payload's ``cwd``,
    since hooks may run from a subfolder of the project."""
    root = resolve_root(brain)
    cwd = payload.get("cwd") if isinstance(payload, dict) else None
    if not root.is_absolute() and isinstance(cwd, str) and cwd:
        root = Path(cwd) / root
    return root


# -- recall ----------------------------------------------------------------------------------


def cmd_recall(args: argparse.Namespace) -> int:
    if args.format == "claude-hook":
        # A recall hook must never block or break the user's prompt: any failure is silent.
        with contextlib.suppress(Exception):
            _claude_hook(args)
        return 0
    if args.limit < 1:
        raise CairnError("--limit must be at least 1")
    prompt = " ".join(args.prompt).strip()
    if not prompt:
        raise CairnError('give a prompt, e.g. cairn recall "rg glob fails on windows"')
    brain = Brain.open(resolve_root(args.brain))
    trivial = recall_mod.is_trivial(prompt, args.min_words)
    hits = [] if trivial else _recall(brain, prompt, args)
    if args.format == "json":
        from .cli import emit_json, hit_to_dict

        results = [hit_to_dict(brain, h) for h in hits]
        emit_json({"query": prompt, "skipped": trivial, "results": results})
    elif hits:
        print(recall_mod.render_text(brain, hits), end="")
    else:
        print("skipped: trivial prompt" if trivial else "no relevant entries")
    return 0


def _recall(brain: Brain, prompt: str, args: argparse.Namespace) -> list:
    return recall_mod.recall(
        brain, prompt, limit=args.limit, min_score=args.min_score, min_terms=args.min_terms
    )


def _claude_hook(args: argparse.Namespace) -> None:
    payload = read_hook_payload()
    prompt = payload.get("prompt") if isinstance(payload, dict) else None
    if not isinstance(prompt, str) or recall_mod.is_trivial(prompt, args.min_words):
        return
    brain = Brain.open(hook_brain_root(args.brain, payload))
    hits = _recall(brain, prompt, args) if args.limit >= 1 else []
    if hits:
        context = recall_mod.render_text(brain, hits)
        print(json.dumps(recall_mod.claude_hook_output(context)))


# -- install, uninstall, skills --------------------------------------------------------------


def _context(args: argparse.Namespace) -> Context:
    if not args.project.is_dir():
        raise CairnError(f"no project folder at '{args.project}'")
    return Context.create(args.project, resolve_root(args.brain))


def cmd_install(args: argparse.Namespace) -> int:
    ctx = _context(args)
    return _run(get_adapter(args.tool).install(ctx), ctx, args.dry_run)


def cmd_uninstall(args: argparse.Namespace) -> int:
    ctx = _context(args)
    return _run(get_adapter(args.tool).uninstall(ctx), ctx, args.dry_run)


def cmd_skills(args: argparse.Namespace) -> int:
    ctx = _context(args)
    adapter = get_adapter(args.tool)
    if args.skills_command == "export":
        brain = Brain.open(resolve_root(args.brain))
        changes = adapter.export_skills(brain, ctx)
        if not changes:
            print("no skills in the brain")
    else:
        changes = adapter.clean_skills(ctx)
        if not changes:
            print("no exported skills to remove")
    return _run(changes, ctx, args.dry_run)


_PAST = {"create": "created", "update": "updated", "delete": "deleted", "unchanged": "unchanged"}


def _run(changes: list[Change], ctx: Context, dry_run: bool) -> int:
    if not dry_run:
        apply(changes, ctx.project)
    for change in changes:
        rel = change.path.relative_to(ctx.project).as_posix()
        if not dry_run:
            print(f"{_PAST[change.action]} {rel}")
            continue
        print(
            f"unchanged {rel}" if change.action == "unchanged" else f"would {change.action} {rel}"
        )
        diff = difflib.unified_diff(
            (change.before or "").splitlines(keepends=True),
            (change.after or "").splitlines(keepends=True),
            f"a/{rel}",
            f"b/{rel}",
        )
        sys.stdout.writelines(line if line.endswith("\n") else line + "\n" for line in diff)
    return 0
