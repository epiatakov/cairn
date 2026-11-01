"""Recall: turn a task prompt into a few high-precision pointers into the brain.

This is what the recall hook runs before every prompt, so it has to be cheap, quiet on
trivial turns ("thanks", "go on") and conservative: a short list of strong hits is read,
a long noisy one is skipped (see "Lessons" in ``docs/design.md``).
"""

from __future__ import annotations

from .brain import Brain
from .search import Hit, tokenize

DEFAULT_LIMIT = 3
DEFAULT_MIN_SCORE = 1.5
# No-answer gate: a pointer must share at least two distinct words with the prompt (all of
# them for a one-word prompt). One shared word is the usual shape of a false positive, e.g.
# "terraform state lock could not be acquired" reaching an npm lockfile entry through
# "lock" alone.
DEFAULT_MIN_TERMS = 2
DEFAULT_MIN_WORDS = 2
# Long prompts (pasted logs, whole files) are cut before searching: every extra term adds
# noise and scoring cost, and the task is usually stated up front.
MAX_QUERY_CHARS = 2000

CHITCHAT = frozenset(
    """
    ahead all approve approved awesome bye cheer cheers cool correct done fine go good great
    hello hey hi k keep lgtm looks lol much nice no nope ok okay on perfect please proceed
    right sound sounds sure thank thanks thx ty very well wow ya yeah yep yes yup
    """.split()  # noqa: SIM905
)


def is_trivial(prompt: str, min_words: int = DEFAULT_MIN_WORDS) -> bool:
    """True for prompts not worth a search: too few content words, or only chit-chat.

    ``min_words <= 0`` turns the filter off.
    """
    if min_words <= 0:
        return False
    words = tokenize(prompt[:MAX_QUERY_CHARS])
    return len(words) < min_words or all(w in CHITCHAT for w in words)


def recall(
    brain: Brain,
    prompt: str,
    *,
    limit: int = DEFAULT_LIMIT,
    min_score: float = DEFAULT_MIN_SCORE,
    min_terms: int = DEFAULT_MIN_TERMS,
) -> list[Hit]:
    """The top ``limit`` hits that pass the no-answer gate. Archived entries are skipped.

    A hit must score at least ``min_score`` and share ``min_terms`` distinct words with the
    prompt (see :meth:`cairn.search.Index.search`). An empty list means "nothing relevant".
    """
    return brain.search(
        prompt[:MAX_QUERY_CHARS], limit=limit, min_score=min_score, min_terms=min_terms
    )


def render_text(brain: Brain, hits: list[Hit]) -> str:
    """A short pointer block: id, type, title, one-line snippet and the file to open."""
    if not hits:
        return ""
    lines = ["Relevant entries from the cairn brain (read the file, or `cairn show <id>`):"]
    for h in hits:
        flag = "" if h.entry.status == "active" else f", {h.entry.status}"
        lines.append(f"- {h.entry.id} ({h.entry.type}{flag}): {h.entry.title}")
        if h.snippet:
            lines.append(f"  {h.snippet}")
        lines.append(f"  {brain_path(brain, h)}")
    return "\n".join(lines) + "\n"


def brain_path(brain: Brain, hit: Hit) -> str:
    """The entry's path including the brain folder, so an agent can open it directly."""
    return (brain.root / brain.relpath(hit.entry.path)).as_posix()


def claude_hook_output(context: str) -> dict:
    """The Claude Code ``UserPromptSubmit`` hook output that adds ``context`` to the prompt."""
    return {
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": context,
        }
    }
