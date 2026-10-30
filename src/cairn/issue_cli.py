"""``cairn issue ...``: the hot-issues board on the command line, plus a Claude Code hook mode."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date

from . import issues
from .brain import Brain, CairnError, resolve_root
from .model import Entry

# A tool result counts as a failure only if one of these says so (see ``hook_error_text``).
_FAILURE_KEYS = ("error", "stderr")
_EXIT_KEYS = ("exit_code", "exitCode", "returncode", "return_code")
_ERROR_FLAGS = ("is_error", "isError", "interrupted")


def register(sub: argparse._SubParsersAction, common: argparse.ArgumentParser) -> None:
    issue = sub.add_parser("issue", help="hot-issues board: record, match, list, resolve, prune")
    isub = issue.add_subparsers(dest="issue_command", required=True, metavar="ACTION")

    p = isub.add_parser("record", parents=[common], help="record a failure (new or +1)")
    p.add_argument("--tool", required=True, help="tool or command that failed, e.g. rg")
    p.add_argument("--error", required=True, help="error text; '-' reads stdin")
    p.add_argument("--workaround", default="", help="one-line workaround, if known")
    p.add_argument("--session", default="", help="session id, to count distinct sessions")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_record)

    p = isub.add_parser("match", parents=[common], help="find the known issue for an error")
    p.add_argument("--error", help="error text; '-' reads stdin (not used with claude-hook)")
    p.add_argument("--format", choices=("text", "json", "claude-hook"), default="text")
    p.add_argument("--json", action="store_const", const="json", dest="format")
    p.set_defaults(func=cmd_match)

    p = isub.add_parser("list", parents=[common], help="the board, hottest first")
    p.add_argument("--since", help="only issues seen within this window, e.g. 7d or 2w")
    p.add_argument(
        "--state",
        action="append",
        choices=(*issues.STATES, "stale"),
        help="repeatable (default: active issues that are not fixed)",
    )
    p.add_argument("--tool", action="append", default=[], help="repeatable")
    p.add_argument("--all", action="store_true", help="include fixed and stale issues")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_list)

    p = isub.add_parser("resolve", parents=[common], help="attach a workaround or a fix")
    p.add_argument("id")
    what = p.add_mutually_exclusive_group(required=True)
    what.add_argument("--workaround", help="sets state to 'workaround'")
    what.add_argument("--fix", help="root-cause fix; sets state to 'fixed'")
    p.set_defaults(func=cmd_resolve)

    p = isub.add_parser("prune", parents=[common], help="mark issues that stopped recurring stale")
    p.add_argument("--older-than", required=True, help="not seen within this window, e.g. 30d")
    p.add_argument("--dry-run", action="store_true", help="list them without changing files")
    p.set_defaults(func=cmd_prune)


def _open(args: argparse.Namespace) -> Brain:
    return Brain.open(resolve_root(args.brain))


def _read_error(value: str | None) -> str:
    if value is None:
        raise CairnError("--error is required")
    text = sys.stdin.read() if value == "-" else value
    if not text.strip():
        raise CairnError("the error text is empty")
    return text


def _emit(payload: dict) -> None:
    from .cli import JSON_SCHEMA_VERSION

    print(json.dumps({"version": JSON_SCHEMA_VERSION, **payload}, indent=2))


def issue_to_dict(brain: Brain, entry: Entry, today: date | None = None) -> dict:
    from .cli import entry_to_dict

    return {
        **entry_to_dict(brain, entry),
        "tool": issues.tool(entry),
        "state": issues.state(entry),
        "occurrences": issues.occurrences(entry),
        "sessions": len(issues.sessions(entry)),
        "first_seen": issues.first_seen(entry),
        "last_seen": str(issues.last_seen(entry) or ""),
        "hot": round(issues.hot_score(entry, today), 4),
        "fingerprints": issues.fingerprints(entry),
        "workaround": issues.workaround(entry),
        "fix": issues.fix(entry),
    }


def cmd_record(args: argparse.Namespace) -> int:
    brain = _open(args)
    text = _read_error(args.error)
    rec = issues.record(
        brain, args.tool, text, workaround_text=args.workaround, session=args.session
    )
    if args.json:
        _emit(
            {
                "created": rec.created,
                "method": rec.method,
                "fingerprint": rec.fingerprint,
                "issue": issue_to_dict(brain, rec.entry),
            }
        )
        return 0
    entry = rec.entry
    if rec.created:
        print(f"recorded new issue {entry.id} ({brain.relpath(entry.path)})")
    else:
        print(f"recorded {entry.id}: seen {issues.occurrences(entry)}x (matched by {rec.method})")
    wa = issues.workaround(entry)
    if wa and not rec.created:
        print(f"workaround: {wa}")
    return 0


def cmd_match(args: argparse.Namespace) -> int:
    if args.format == "claude-hook":
        return _match_hook(args)
    brain = _open(args)
    text = _read_error(args.error)
    found = issues.match(brain, text)
    if args.format == "json":
        result = None
        if found:
            result = {
                **issue_to_dict(brain, found.entry),
                "method": found.method,
                "confidence": found.confidence,
            }
        _emit({"fingerprint": issues.fingerprint(text), "match": result})
        return 0 if found else 1
    if found is None:
        return 1
    entry = found.entry
    print(f"{entry.id}  (matched by {found.method}, {found.confidence:.2f})")
    print(f"  {entry.title}")
    print(f"  state: {issues.state(entry)}, seen {issues.occurrences(entry)}x")
    if issues.fix(entry):
        print(f"  fix: {issues.fix(entry)}")
    wa = issues.workaround(entry)
    if wa:
        print("  workaround:")
        for line in wa.splitlines():
            print(f"    {line}" if line.strip() else "")
    return 0


def _match_hook(args: argparse.Namespace) -> int:
    """Claude Code hook mode. Never fails the tool call: silent with exit 0 on anything odd."""
    try:
        payload = json.loads(sys.stdin.read())
        text = hook_error_text(payload)
        if not text:
            return 0
        brain = Brain.open(resolve_root(args.brain))
        found = issues.match(brain, text)
        if found is None:
            return 0
        event = payload.get("hook_event_name") or "PostToolUse"
        output = {
            "hookSpecificOutput": {
                "hookEventName": event,
                "additionalContext": hook_context(found),
            }
        }
        print(json.dumps(output))
    except Exception:  # a hook must never break the agent's turn
        return 0
    return 0


def hook_error_text(payload: dict) -> str:
    """The error text of a failed tool call in a hook payload, or ``""`` if it did not fail."""
    if not isinstance(payload, dict):
        return ""
    if payload.get("hook_event_name") == "PostToolUseFailure":
        error = payload.get("error")
        return error if isinstance(error, str) else json.dumps(error or "")
    response = payload.get("tool_response")
    if isinstance(response, str):
        return response if issues.ERRORISH_RE.search(response) else ""
    if not isinstance(response, dict):
        return ""
    failed = any(response.get(k) for k in _ERROR_FLAGS) or any(
        isinstance(response.get(k), int) and response.get(k) != 0 for k in _EXIT_KEYS
    )
    for key in _FAILURE_KEYS:
        value = response.get(key)
        if (
            isinstance(value, str)
            and value.strip()
            and (failed or key == "error" or issues.ERRORISH_RE.search(value))
        ):
            return value
    stdout = response.get("stdout")
    if failed and isinstance(stdout, str):
        return stdout
    return ""


def hook_context(found: issues.Match) -> str:
    entry = found.entry
    lines = [
        f"cairn hot-issues board: this failure matches known issue '{entry.id}' "
        f"({entry.title}; seen {issues.occurrences(entry)}x, state {issues.state(entry)}).",
    ]
    if issues.fix(entry):
        lines.append(f"Fix: {issues.fix(entry)}")
    wa = issues.workaround(entry)
    lines.append(f"Workaround: {wa}" if wa else "No workaround recorded yet.")
    lines.append(f"Details: cairn show {entry.id}")
    return "\n".join(lines)


def cmd_list(args: argparse.Namespace) -> int:
    brain = _open(args)
    since = issues.parse_duration(args.since) if args.since else None
    today = date.today()
    entries = issues.board(
        brain,
        since_days=since,
        states=args.state,
        tools=args.tool,
        include_all=args.all,
        today=today,
    )
    if args.json:
        _emit({"issues": [issue_to_dict(brain, e, today) for e in entries]})
        return 0
    if not entries:
        print("no issues on the board")
        return 0
    print(f"{'HOT':>6}  {'SEEN':>4}  {'LAST SEEN':<10}  {'STATE':<10}  {'TOOL':<10}  ID")
    for e in entries:
        flag = " [stale]" if e.status == "stale" else ""
        print(
            f"{issues.hot_score(e, today):6.2f}  {issues.occurrences(e):>4}  "
            f"{(issues.last_seen(e) or '-')!s:<10}  {issues.state(e):<10}  "
            f"{(issues.tool(e) or '-'):<10}  {e.id}{flag}"
        )
    return 0


def cmd_resolve(args: argparse.Namespace) -> int:
    brain = _open(args)
    entry = issues.resolve(
        brain, args.id, workaround_text=args.workaround or "", fix_text=args.fix or ""
    )
    print(f"{entry.id}: state {issues.state(entry)}")
    return 0


def cmd_prune(args: argparse.Namespace) -> int:
    brain = _open(args)
    days = issues.parse_duration(args.older_than)
    stale = issues.prune(brain, days, dry_run=args.dry_run)
    verb = "would mark" if args.dry_run else "marked"
    for entry in stale:
        print(f"{verb} stale: {entry.id} (last seen {issues.last_seen(entry)})")
    print(f"{len(stale)} issue(s) {verb} stale")
    return 0
