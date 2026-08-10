"""Uniform connector interface.

One module per source. A connector DISCOVERS refs in scope and FETCHES each into a
`FetchedVersion` — official text + provenance ONLY. Connectors never write the DB and
never originate text; `src/store` canonicalizes, hashes, versions, and syncs FTS.

The contract is deliberately tiny so a new source is one module implementing two methods.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Optional, Protocol, runtime_checkable


@dataclass
class FetchedVersion:
    """The canonical unit every connector yields. Mirrors db.versions + its instrument."""
    jurisdiction: str                        # 'US' | 'GB' | 'EU' | 'INT' | ...
    instrument_type: str                     # statute | regulation | treaty | directive | bill
    title: str
    source_url: str                          # REQUIRED — the official source page
    official_citation: Optional[str] = None  # '17 U.S.C.' | 'CDPA 1988' | 'Directive (EU) 2019/790'
    ext_id: Optional[str] = None             # ELI | CELEX | WIPO id | USC title | CFR part
    ext_id_scheme: Optional[str] = None      # 'ELI' | 'CELEX' | 'WIPO' | 'USC' | 'CFR' | 'TREATY'
    version_label: Optional[str] = None      # source's own version label
    point_in_time: Optional[str] = None      # ISO8601 in-force-from date
    content: Optional[str] = None            # official full text (None => metadata-only Tier 3)
    language: str = "en"
    is_official_language: bool = True         # False => unofficial translation (UI flags it)
    is_consolidated: bool = True
    is_authentic: bool = True                 # EU consolidated => False (UI flags "not authentic")
    has_unapplied_effects: bool = False       # UK consolidated may carry these (UI flags)
    status: str = "in_force"
    enacted_date: Optional[str] = None
    in_force_date: Optional[str] = None
    meta: dict = field(default_factory=dict)  # source-native extras (change_hash, ELI graph, ...)


@runtime_checkable
class Connector(Protocol):
    name: str
    jurisdiction: str

    def discover(self, since: Optional[str] = None) -> Iterable[str]:
        """Yield in-scope refs (ids/URLs). `since` narrows to recently-changed where supported."""
        ...

    def fetch(self, ref: str) -> Optional[FetchedVersion]:
        """Fetch one ref into a FetchedVersion, or None if it drops out of scope. Fetch failure
        must fail CLOSED (return None + log) — never fabricate a placeholder record."""
        ...
