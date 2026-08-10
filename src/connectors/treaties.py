"""INT — core copyright treaties, HAND-LOADED (no clean API).

The Phase-0 treaty set (authoritative texts hand-curated from WIPO/official depositaries):
  Berne, TRIPS, WCT, WPPT, Rome, Beijing (AV Performances), Marrakesh.
Each is loaded once from its official text; accessions/ratifications are metadata that
accrete over time (WIPO Lex / treaty-body notifications) — Tier-3 style, link-first.

STATUS: stub. Phase 0 loads the treaty texts from a curated manifest (title, official_url,
in-force date) -> FetchedVersion (jurisdiction='INT', is_authentic=True where the loaded
text is an official language version; flag unofficial translations).
"""
from __future__ import annotations

from typing import Iterable, Optional

from .base import FetchedVersion

name = "treaties"
jurisdiction = "INT"

# Curated manifest — official source URLs; texts hand-loaded (never scraped-and-guessed).
MANIFEST = {
    "berne":     "https://www.wipo.int/wipolex/en/treaties/textdetails/12214",
    "trips":     "https://www.wto.org/english/docs_e/legal_e/27-trips_01_e.htm",
    "wct":       "https://www.wipo.int/wipolex/en/treaties/textdetails/12740",
    "wppt":      "https://www.wipo.int/wipolex/en/treaties/textdetails/12743",
    "rome":      "https://www.wipo.int/wipolex/en/treaties/textdetails/12656",
    "beijing":   "https://www.wipo.int/wipolex/en/treaties/textdetails/12213",
    "marrakesh": "https://www.wipo.int/wipolex/en/treaties/textdetails/13169",
}


def discover(since: Optional[str] = None) -> Iterable[str]:
    return list(MANIFEST)


def fetch(ref: str) -> Optional[FetchedVersion]:
    raise NotImplementedError("Phase 0: load the curated treaty text for `ref` -> FetchedVersion")
