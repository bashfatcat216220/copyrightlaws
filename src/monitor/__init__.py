"""Change monitor: detect when a stored instrument's text changed, emit a redline + alert.

Phase 2. The store layer already versions on content_sha256 change, so the monitor's job is
(a) find instruments whose newest version differs from the prior one, (b) produce a redline
(plain difflib to start; an AI plain-language summary of the change, grounded on the two
texts, is a labeled add-on), and (c) write an `alerts` row for the digest.

Free change FEEDS (cheaper than diffing everything): legislation.gov.uk Publication Log Atom;
EUR-Lex/CELLAR update packages. Use those to know WHAT to re-fetch, then diff.
"""
from __future__ import annotations

import difflib
import sqlite3


def redline(old_text: str, new_text: str) -> str:
    """Unified diff between two version texts (the raw redline; AI summary is a separate step)."""
    return "\n".join(difflib.unified_diff(
        old_text.splitlines(), new_text.splitlines(), lineterm="", n=2))


def pending_changes(conn: sqlite3.Connection) -> list[dict]:
    raise NotImplementedError("Phase 2: compare newest two versions per instrument, emit alerts")
