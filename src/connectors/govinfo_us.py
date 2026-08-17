"""US — 17 U.S.C. (Copyright): OLRC release-point USLM XML (+ GPO package cross-ref).

There is NO GovInfo `bulkdata/USCODE` collection — the old URL here returned a soft-200
"Bulkdata Service Error" page (2026-08-16 audit, 2f LOW). Current Title-17 USLM comes from
the OLRC release points (the URL shape `monitor/refresh.py` actually fetches):
  https://uscode.house.gov/download/releasepoints/us/pl/<cong>/<law>/xml_usc17@<cong>-<law>.zip
The OLRC online text is a government FINDING AID (`source_edition`); the AUTHORITATIVE
manifestation cross-ref is the GPO annual U.S. Code package, one per edition year:
  https://www.govinfo.gov/app/details/USCODE-<year>-title17   (verified live 2026-08-16)
Title 17 is positive law, so the Code text is legal evidence of the law either way
(CLAUDE prime rule 3a). API: https://api.govinfo.gov (GOVINFO_API_KEY from api.data.gov).
POINT-IN-TIME history is assembled from Public Laws (harder — Phase 1+). The Copyright
Office's "Circular 92 / Copyright Law of the United States" (copyright.gov) is a useful
consolidated cross-check, hand-loaded.

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
# OLRC release-point download (fill in congress/law, e.g. 119/102):
TITLE_17_OLRC_RP = ("https://uscode.house.gov/download/releasepoints/us/pl/"
                    "{congress}/{law}/xml_usc17@{congress}-{law}.zip")
# Authoritative-manifestation cross-ref: the GPO annual U.S. Code edition package.
TITLE_17_GPO_PACKAGE = "https://www.govinfo.gov/app/details/USCODE-{year}-title17"


def discover(since: Optional[str] = None) -> Iterable[str]:
    if not os.environ.get(ENV_KEY):
        return []
    raise NotImplementedError("Phase 0: list Title-17 USLM package(s) from GovInfo bulk/API")


def fetch(ref: str) -> Optional[FetchedVersion]:
    raise NotImplementedError("Phase 0: GET USLM XML, parse sections -> FetchedVersion")
