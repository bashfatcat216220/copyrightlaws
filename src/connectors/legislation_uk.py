"""GB — legislation.gov.uk (CDPA 1988 and other UK copyright instruments).

The best-designed legal API in existence, and the reason UK is the Phase-0 exemplar:
  - Append `/data.xml` (CLML) or `/data.rdf` to any legislation URL for structured text.
  - Point-in-time: `.../YYYY-MM-DD/data.xml` returns the text AS IN FORCE on that date.
  - The Publication Log Atom feed is a FREE change monitor:
        https://www.legislation.gov.uk/new/data.feed  (+ per-item republication/withdrawal)
  - Consolidated text can carry UNAPPLIED EFFECTS -> set has_unapplied_effects and FLAG it.

CDPA 1988: https://www.legislation.gov.uk/ukpga/1988/48

STATUS: stub. Phase 0 implements discover() over the Publication Log + fetch() of the
point-in-time CLML, mapped to FetchedVersion (is_authentic=True, official language).
"""
from __future__ import annotations

from typing import Iterable, Optional

from .base import FetchedVersion

name = "legislation_uk"
jurisdiction = "GB"
BASE = "https://www.legislation.gov.uk"
CDPA = f"{BASE}/ukpga/1988/48"


def discover(since: Optional[str] = None) -> Iterable[str]:
    raise NotImplementedError("Phase 0: page the Publication Log Atom feed for changed copyright items")


def fetch(ref: str) -> Optional[FetchedVersion]:
    raise NotImplementedError("Phase 0: GET <ref>/data.xml, map CLML -> FetchedVersion")
