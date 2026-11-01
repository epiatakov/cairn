"""The hot-issues board: known tool failures, fingerprinted, counted and matched.

An issue is an ordinary ``issue`` entry with extra frontmatter fields (see ``ISSUE_FIELDS``).
Recording the same failure twice increments the existing entry instead of adding a new one, so
the board stays a cache of fixes rather than a log of every failure.

Matching first compares fingerprints (a hash of the error text with paths, numbers, ids and
timestamps stripped). If no fingerprint matches, it falls back to BM25 over issue entries and
accepts the best hit only when it covers enough of the error's distinctive words.
"""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from .brain import Brain, CairnError
from .model import Entry, normalize_tags, slugify
from .search import Index, tokenize

STATES = ("open", "workaround", "fixed")
ISSUE_FIELDS = (
    "tool",
    "fingerprint",
    "state",
    "occurrences",
    "sessions",
    "first_seen",
    "last_seen",
    "workaround",
    "fix",
)
MAX_SESSIONS = 10
HOT_HALF_LIFE_DAYS = 7.0
MATCH_MIN_CONFIDENCE = 0.6
MIN_SHARED_TERMS = 3
RECORD_MIN_CONFIDENCE = 0.75
MAX_SIGNATURE_LINES = 2
MAX_LINE_CHARS = 300
MAX_EXCERPT_LINES = 12

FINGERPRINT_RE = re.compile(r"[0-9a-f]{12}")
_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
_DURATION_RE = re.compile(r"(\d+)([dw])")

# Applied in order. Each pattern replaces a volatile part of an error with a placeholder, so
# the same failure on another machine, in another folder or at another time looks the same.
_REDACTIONS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\x1b\[[0-9;]*[A-Za-z]"), ""),
    (re.compile(r"\b[a-z][a-z0-9+.-]*://\S+", re.I), "{url}"),
    (
        re.compile(
            r"\b\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2}(?:[.,]\d+)?)?"
            r"(?:Z|[+-]\d{2}:?\d{2})?)?",
            re.I,
        ),
        "{time}",
    ),
    (re.compile(r"\b\d{1,2}:\d{2}:\d{2}(?:[.,]\d+)?\b"), "{time}"),
    (
        re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I),
        "{id}",
    ),
    # Windows drive and UNC paths, then POSIX absolute and relative paths.
    (re.compile(r"(?<![\w])[a-z]:[\\/][^\s'\"`<>|,;:()]*", re.I), "{path}"),
    (re.compile(r"\\\\[^\s'\"`<>|,;:()]+"), "{path}"),
    (re.compile(r"(?<![\w}])(?:~|\.{1,2})?/[^\s'\"`<>|,;:()]+"), "{path}"),
    (re.compile(r"\b[\w.-]+(?:/[\w.*@+-]+)+/?"), "{path}"),
    (re.compile(r"\btmp[\w.-]*|\btemp[_.-][\w.-]*|\b[\w-]+\.tmp\b", re.I), "{tmp}"),
    (re.compile(r"\b0x[0-9a-f]+\b", re.I), "{hex}"),
    (re.compile(r"\b(?=[0-9a-f]*\d)(?=[0-9a-f]*[a-f])[0-9a-f]{7,}\b", re.I), "{hex}"),
]
_NUMBER_RE = re.compile(r"(?<![\w.{])\d+(?:\.\d+)*(?![\w}])")
# Numbers right after these words identify the failure (exit status, HTTP status, OS error).
_KEEP_NUMBER_RE = re.compile(
    r"(?:\b(?:code|status|errno|exit|http|signal)\s*[:=]?\s*|\berror\s+)$", re.I
)
_REPEATED_PLACEHOLDER_RE = re.compile(r"(\{\w+\})(?:[\s:]+\1)+")
_TRAILING_PUNCT_RE = re.compile(r"[.,;!?]+(?=\s|$)")
_WORD_RE = re.compile(r"[A-Za-z]{2,}")
_QUOTES_RE = re.compile("[\"'`\u2018\u2019\u201c\u201d]")
_PLACEHOLDER_RE = re.compile(r"\{(?:url|time|id|path|tmp|hex|n)\}")
ERRORISH_RE = re.compile(
    r"error|exception|fatal|fail|denied|not found|no such|cannot|can't|could not|unable|"
    r"invalid|incorrect|refused|timed? ?out|unknown|unrecognized|not recognized|missing|"
    r"panic|abort|bad |segmentation|\berr\b",
    re.I,
)
_WORKAROUND_RE = re.compile(
    r"\*\*Workaround:\*\*\s*(.*?)(?=\n\s*\*\*[A-Z][^*\n]*:\*\*|\Z)", re.DOTALL
)


# -- fingerprinting ------------------------------------------------------


def redact(text: str) -> str:
    """Replace paths, urls, ids, hex, timestamps, temp names and loose numbers with placeholders.

    Case and quotes are kept, so the result is readable and safe to store in an entry.
    """
    for pattern, placeholder in _REDACTIONS:
        text = pattern.sub(placeholder, text)

    def number(match: re.Match[str]) -> str:
        before = match.string[max(0, match.start() - 20) : match.start()]
        return match.group(0) if _KEEP_NUMBER_RE.search(before) else "{n}"

    return _REPEATED_PLACEHOLDER_RE.sub(r"\1", _NUMBER_RE.sub(number, text))


def error_lines(text: str) -> list[str]:
    """The lines that carry the failure: the first error-looking ones, else the first line."""
    lines = [line.strip()[:MAX_LINE_CHARS] for line in text.replace("\r", "\n").split("\n")]
    lines = [line for line in lines if line]
    wordy = [line for line in lines if len(_WORD_RE.findall(line)) >= 3] or lines
    errorish = [line for line in wordy if ERRORISH_RE.search(line)]
    return (errorish or wordy)[:MAX_SIGNATURE_LINES]


def signature(text: str) -> str:
    """A normalized, human-readable form of an error: the input to :func:`fingerprint`."""
    lines = []
    for line in error_lines(text):
        line = _QUOTES_RE.sub("", redact(line)).lower()
        line = _TRAILING_PUNCT_RE.sub("", line)
        line = re.sub(r"\s+", " ", line).strip().rstrip(":")
        if line:
            lines.append(line)
    return " | ".join(lines)


def fingerprint(text: str) -> str:
    """A 12-hex-digit hash of :func:`signature`. Empty if the text has no usable content."""
    sig = signature(text)
    return hashlib.sha1(sig.encode("utf-8")).hexdigest()[:12] if sig else ""


# -- reading issue fields ------------------------------------------------


def _field(entry: Entry, key: str) -> str:
    value = entry.extra.get(key, "")
    return value if isinstance(value, str) else ""


def _list_field(entry: Entry, key: str) -> list[str]:
    value = entry.extra.get(key, [])
    if isinstance(value, str):
        return [value] if value else []
    return list(value)


def fingerprints(entry: Entry) -> list[str]:
    return _list_field(entry, "fingerprint")


def sessions(entry: Entry) -> list[str]:
    return _list_field(entry, "sessions")


def tool(entry: Entry) -> str:
    return _field(entry, "tool")


def occurrences(entry: Entry) -> int:
    """How often the failure was recorded. Hand-written issues without the field count once."""
    raw = _field(entry, "occurrences")
    return int(raw) if raw.isdigit() else 1


def workaround(entry: Entry) -> str:
    """The ``workaround`` field, else the body's ``**Workaround:**`` section."""
    value = _field(entry, "workaround")
    if value:
        return value
    match = _WORKAROUND_RE.search(entry.body)
    return match.group(1).strip() if match else ""


def fix(entry: Entry) -> str:
    return _field(entry, "fix")


def state(entry: Entry) -> str:
    value = _field(entry, "state")
    if value in STATES:
        return value
    return "workaround" if workaround(entry) else "open"


def _date(value: str) -> date | None:
    try:
        return date.fromisoformat(value) if _DATE_RE.fullmatch(value) else None
    except ValueError:
        return None


def first_seen(entry: Entry) -> str:
    return _field(entry, "first_seen")


def last_seen(entry: Entry) -> date | None:
    return _date(_field(entry, "last_seen")) or _date(entry.updated)


def hot_score(entry: Entry, today: date | None = None) -> float:
    """Occurrences, halved for every ``HOT_HALF_LIFE_DAYS`` since the issue was last seen."""
    seen = last_seen(entry)
    age = max(0, ((today or date.today()) - seen).days) if seen else 365
    return occurrences(entry) * 0.5 ** (age / HOT_HALF_LIFE_DAYS)


def check_fields(entry: Entry) -> list[str]:
    """Problems with the hot-issues fields of an entry. Absent fields are fine."""
    extra, problems = entry.extra, []
    for key in ("tool", "state", "occurrences", "first_seen", "last_seen", "workaround", "fix"):
        if isinstance(extra.get(key), list):
            problems.append(f"'{key}' must be a single value, not a list")
    bad = [fp for fp in fingerprints(entry) if not FINGERPRINT_RE.fullmatch(fp)]
    if bad:
        problems.append(f"invalid fingerprint '{bad[0]}': expected 12 lowercase hex digits")
    raw_state = extra.get("state")
    if isinstance(raw_state, str) and raw_state not in STATES:
        problems.append(f"invalid state '{raw_state}': expected one of {', '.join(STATES)}")
    raw_occ = extra.get("occurrences")
    if isinstance(raw_occ, str) and not raw_occ.isdigit():
        problems.append(f"invalid occurrences '{raw_occ}': expected a whole number")
    seen = {}
    for key in ("first_seen", "last_seen"):
        raw = extra.get(key)
        if isinstance(raw, str):
            seen[key] = _date(raw)
            if seen[key] is None:
                problems.append(f"invalid {key} date '{raw}': expected YYYY-MM-DD")
    if seen.get("first_seen") and seen.get("last_seen") and seen["last_seen"] < seen["first_seen"]:
        problems.append("'last_seen' is earlier than 'first_seen'")
    if raw_state == "fixed" and not fix(entry):
        problems.append("state is 'fixed' but no 'fix' is recorded")
    if raw_state == "workaround" and not workaround(entry):
        problems.append("state is 'workaround' but no workaround is recorded")
    return problems


# -- matching ------------------------------------------------------------


@dataclass(frozen=True)
class Match:
    entry: Entry
    method: str  # "fingerprint" | "similarity"
    confidence: float


def live_issues(brain: Brain) -> list[Entry]:
    return [e for e in brain.filter(type="issue") if e.status != "archived"]


def _query(text: str) -> str:
    return _PLACEHOLDER_RE.sub(" ", redact(" ".join(error_lines(text))))


def match(brain: Brain, text: str, *, min_confidence: float = MATCH_MIN_CONFIDENCE) -> Match | None:
    """The known issue for an error text: an exact fingerprint, else the best BM25 hit."""
    issues = live_issues(brain)
    fp = fingerprint(text)
    if not fp or not issues:
        return None
    exact = [e for e in issues if fp in fingerprints(e)]
    if exact:
        best = max(exact, key=lambda e: (occurrences(e), e.id))
        return Match(best, "fingerprint", 1.0)

    # Pure numbers are weak evidence; the error's words carry the match.
    terms = {t for t in tokenize(_query(text)) if not t.isdigit()}
    if not terms:
        return None
    docs = {e.id: _tokens(e) for e in issues}
    corpus = [docs.get(e.id) or _tokens(e) for e in brain.entries if e.status != "archived"]
    n = len(corpus)

    def weight(term: str) -> float:
        # Words no entry contains weigh like the rarest known word, not infinitely more.
        df = max(1, sum(term in tokens for tokens in corpus))
        return math.log(1 + (n - df + 0.5) / (df + 0.5))

    weights = {t: weight(t) for t in terms}
    total = sum(weights.values())
    for hit in Index(issues).search(" ".join(sorted(terms)), limit=3):
        shared = [t for t in terms if t in docs[hit.entry.id]]
        confidence = sum(weights[t] for t in shared) / total if total else 0.0
        if confidence >= min_confidence and len(shared) >= min(MIN_SHARED_TERMS, len(terms)):
            return Match(hit.entry, "similarity", round(confidence, 4))
    return None


def _tokens(entry: Entry) -> set[str]:
    return set(tokenize(" ".join([entry.title, *entry.tags, entry.body, workaround(entry)])))


# -- writing -------------------------------------------------------------


def save(brain: Brain, entry: Entry) -> Path:
    """Rewrite an existing entry in place and reload the brain."""
    problems = entry.validate() + check_fields(entry)
    if problems:
        raise CairnError("invalid entry: " + "; ".join(problems))
    if entry.path is None:
        raise CairnError(f"entry '{entry.id}' has no file")
    with entry.path.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(entry.to_markdown())
    brain.reload()
    return entry.path


def _set(entry: Entry, key: str, value: str | list[str]) -> None:
    """Set an issue field, keeping ``ISSUE_FIELDS`` order for fields not yet present."""
    entry.extra[key] = value
    order = {k: i for i, k in enumerate(ISSUE_FIELDS)}
    known = sorted((k for k in entry.extra if k in order), key=order.__getitem__)
    others = [k for k in entry.extra if k not in order]
    entry.extra = {k: entry.extra[k] for k in [*others, *known]}


@dataclass(frozen=True)
class Recorded:
    entry: Entry
    created: bool
    method: str  # "new" | "fingerprint" | "similarity"
    fingerprint: str


def record(
    brain: Brain,
    tool_name: str,
    text: str,
    *,
    workaround_text: str = "",
    session: str = "",
    today: date | None = None,
) -> Recorded:
    """Record one occurrence of a failure: increment the matching issue or add a new one."""
    fp = fingerprint(text)
    if not fp:
        raise CairnError("the error text is empty")
    tools = normalize_tags([tool_name])
    if not tools:
        raise CairnError("--tool must not be empty")
    stamp = (today or date.today()).isoformat()
    found = match(brain, text, min_confidence=RECORD_MIN_CONFIDENCE)

    if found is None:
        first = redact(error_lines(text)[0])
        prefixed = re.match(rf"{re.escape(tools[0])}\b", first, re.I)
        title = _clip(first if prefixed else f"{tools[0]}: {first}", 100)
        # A title with no ASCII letters or digits has no slug; fall back to the fingerprint.
        entry_id = None if slugify(title) else brain.unique_id(f"issue {fp}")
        entry = brain.new_entry(
            "issue", title, _symptom(tools[0], text), tags=tools, entry_id=entry_id, today=today
        )
        _set(entry, "tool", tools[0])
        _set(entry, "fingerprint", [fp])
        _set(entry, "state", "workaround" if workaround_text else "open")
        _set(entry, "occurrences", "1")
        _set(entry, "sessions", [session] if session else [])
        _set(entry, "first_seen", stamp)
        _set(entry, "last_seen", stamp)
        if workaround_text:
            _set(entry, "workaround", workaround_text.strip())
        problems = check_fields(entry)
        if problems:
            raise CairnError("invalid entry: " + "; ".join(problems))
        brain.add(entry, force=True)
        return Recorded(entry, True, "new", fp)

    entry = found.entry
    if fp not in fingerprints(entry):
        _set(entry, "fingerprint", [*fingerprints(entry), fp])
    if not tool(entry):
        _set(entry, "tool", tools[0])
    _set(entry, "occurrences", str(occurrences(entry) + 1))
    if session:
        recent = [s for s in sessions(entry) if s != session] + [session]
        _set(entry, "sessions", recent[-MAX_SESSIONS:])
    if not _date(_field(entry, "first_seen")):
        _set(entry, "first_seen", entry.created)
    _set(entry, "last_seen", stamp)
    if workaround_text and not _field(entry, "workaround"):
        _set(entry, "workaround", workaround_text.strip())
    if state(entry) == "fixed":
        # The fix did not hold: reopen, keeping the fix text for reference.
        _set(entry, "state", "workaround" if workaround(entry) else "open")
    elif "state" not in entry.extra or (workaround_text and state(entry) == "open"):
        _set(entry, "state", "workaround" if workaround(entry) else "open")
    entry.status = "active" if entry.status == "stale" else entry.status
    entry.updated = max(entry.updated, stamp)
    save(brain, entry)
    return Recorded(entry, False, found.method, fp)


def resolve(
    brain: Brain,
    entry_id: str,
    *,
    workaround_text: str = "",
    fix_text: str = "",
    today: date | None = None,
) -> Entry:
    """Attach a workaround (state ``workaround``) or a root-cause fix (state ``fixed``)."""
    entry = brain.get(entry_id)
    if entry is None or entry.type != "issue":
        raise CairnError(f"no issue with id '{entry_id}'")
    if bool(workaround_text.strip()) == bool(fix_text.strip()):
        raise CairnError("pass exactly one of --workaround or --fix")
    if fix_text.strip():
        _set(entry, "fix", fix_text.strip())
        _set(entry, "state", "fixed")
    else:
        _set(entry, "workaround", workaround_text.strip())
        _set(entry, "state", "workaround")
    entry.updated = max(entry.updated, (today or date.today()).isoformat())
    save(brain, entry)
    return entry


def prune(
    brain: Brain, older_than_days: int, *, today: date | None = None, dry_run: bool = False
) -> list[Entry]:
    """Mark active issues not seen for ``older_than_days`` as ``stale``. Returns them."""
    today = today or date.today()
    cutoff = today - timedelta(days=older_than_days)
    stale = []
    for entry in brain.filter(type="issue", status="active"):
        seen = last_seen(entry)
        if seen is not None and seen < cutoff:
            stale.append(entry)
    if not dry_run:
        for entry in stale:
            entry.status = "stale"
            entry.updated = max(entry.updated, today.isoformat())
            save(brain, entry)
    return stale


def board(
    brain: Brain,
    *,
    since_days: int | None = None,
    states: list[str] | None = None,
    tools: list[str] | None = None,
    include_all: bool = False,
    today: date | None = None,
) -> list[Entry]:
    """Issues ranked by hot score. By default only live ones: active and not fixed.

    ``states`` may include ``stale`` (an entry status rather than an issue state).
    """
    today = today or date.today()
    wanted_tools = set(normalize_tags(tools or []))
    result = []
    for entry in live_issues(brain):
        if states:
            label = "stale" if entry.status == "stale" else state(entry)
            if label not in states:
                continue
        elif not include_all and (entry.status != "active" or state(entry) == "fixed"):
            continue
        if wanted_tools and not wanted_tools & {tool(entry).lower(), *entry.tags}:
            continue
        if since_days is not None:
            seen = last_seen(entry)
            if seen is None or (today - seen).days > since_days:
                continue
        result.append(entry)
    result.sort(key=lambda e: (-hot_score(e, today), -(last_seen(e) or date.min).toordinal(), e.id))
    return result


def parse_duration(text: str) -> int:
    """``7d`` or ``2w`` as a number of days."""
    m = _DURATION_RE.fullmatch(text.strip().lower())
    if not m:
        raise CairnError(f"invalid duration '{text}': use days or weeks, e.g. 7d or 2w")
    return int(m.group(1)) * (7 if m.group(2) == "w" else 1)


def _clip(text: str, width: int) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= width else text[: width - 3].rstrip() + "..."


def _symptom(tool_name: str, text: str) -> str:
    """Body for a new issue: the redacted error, so no local paths or ids are stored."""
    lines = [redact(line.rstrip()) for line in text.strip().splitlines()]
    excerpt = "\n".join(line[:MAX_LINE_CHARS] for line in lines[:MAX_EXCERPT_LINES])
    return (
        f"**Symptom:** `{tool_name}` failed with:\n\n```text\n{excerpt}\n```\n\n"
        "**Cause:** not recorded yet.\n\n"
        "Record a workaround with `cairn issue resolve <id> --workaround ...`."
    )
