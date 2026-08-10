"""US — 37 C.F.R. (Copyright Office regulations) via the eCFR API.

eCFR exposes structured, versioned regulation text, keyless:
  - https://www.ecfr.gov/api/  (versioner + full-text endpoints)
  - Title 37, Chapter II = the Copyright Office regs.
eCFR gives per-date snapshots, so point-in-time is more tractable than the USC.

STATUS: stub. Phase 0 fetches current Title-37/Chapter-II -> FetchedVersion (is_authentic=True).
"""
from __future__ import annotations

from typing import Iterable, Optional

from .base import FetchedVersion

name = "ecfr_us"
jurisdiction = "US"
API = "https://www.ecfr.gov/api"


def discover(since: Optional[str] = None) -> Iterable[str]:
    raise NotImplementedError("Phase 0: eCFR versioner for Title 37, Chapter II")


def fetch(ref: str) -> Optional[FetchedVersion]:
    raise NotImplementedError("Phase 0: GET eCFR full-text for the ref date -> FetchedVersion")
