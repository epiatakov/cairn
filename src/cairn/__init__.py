"""cairn: one second brain for every coding agent.

The public API is small on purpose, so adapters and an MCP server can build on it::

    from cairn import Brain

    brain = Brain.open("brain")
    for hit in brain.search("windows glob", limit=3):
        print(hit.entry.id, hit.score)
"""

from .brain import Brain, CairnError, DuplicateError, Problem, resolve_root
from .model import STATUSES, TYPES, Entry, EntryError
from .search import Hit, Index, search

__version__ = "0.1.0"

__all__ = [
    "STATUSES",
    "TYPES",
    "Brain",
    "CairnError",
    "DuplicateError",
    "Entry",
    "EntryError",
    "Hit",
    "Index",
    "Problem",
    "__version__",
    "resolve_root",
    "search",
]
