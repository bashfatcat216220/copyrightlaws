"""US — 17 U.S.C. (Copyright) via GovInfo bulk USLM XML (OLRC).

GovInfo publishes the US Code as USLM XML. Title 17 is the copyright statute.
  - Bulk: https://www.govinfo.gov/bulkdata/USCODE  (per-title USLM XML)
  - API:  https://api.govinfo.gov  (GOVINFO_API_KEY from api.data.gov)
CURRENT text is straightforward; POINT-IN-TIME history is assembled from Public Laws
(harder — Phase 1+). The Copyright Office's "Circular 92 / Copyright Law of the United
States" (copyright.gov) is a useful consolidated cross-check, hand-loaded.

STATUS: stub. Phase 0 fetches the current Title-17 USLM, maps sections -> FetchedVersion
(is_authentic=True). Point-in-time versions deferred.
"""
from __future__ import annotations

import os
from typing import Iterable, Optional

from .base import FetchedVersion

name = "govinfo_us"
jurisdiction = "US"
ENV_KEY = "GOVINFO_API_KEY"
TITLE_17_BULK = "https://www.govinfo.gov/bulkdata/USCODE/title17"


def discover(since: Optional[str] = None) -> Iterable[str]:
    if not os.environ.get(ENV_KEY):
        return []
    raise NotImplementedError("Phase 0: list Title-17 USLM package(s) from GovInfo bulk/API")


def fetch(ref: str) -> Optional[FetchedVersion]:
    raise NotImplementedError("Phase 0: GET USLM XML, parse sections -> FetchedVersion")
