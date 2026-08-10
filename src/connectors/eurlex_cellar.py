"""EU — copyright directives via EUR-Lex CELLAR (SPARQL + REST).

Reuse the ai-law-portal EUR-Lex connector shape. Phase-0 scope = the copyright acquis:
  - InfoSoc      2001/29/EC   (CELEX 32001L0029)
  - DSM          2019/790     (CELEX 32019L0790)
  - Software     2009/24/EC   (CELEX 32009L0024)
  - Database     96/9/EC      (CELEX 31996L0009)
  - Term         2006/116/EC  (+ 2011/77 amend)  (CELEX 32006L0116)
  - Enforcement  2004/48/EC   (CELEX 32004L0048)
Endpoints:
  - SPARQL: http://publications.europa.eu/webapi/rdf/sparql
  - Cellar REST: content-negotiated CELEX documents (application/xhtml+xml)

IMPORTANT: EUR-Lex CONSOLIDATED versions are explicitly NOT AUTHENTIC — set
is_authentic=False so the UI flags every consolidated version.

STATUS: stub. Phase 0 fetches the six CELEX acts -> FetchedVersion (is_authentic per doc).
"""
from __future__ import annotations

from typing import Iterable, Optional

from .base import FetchedVersion

name = "eurlex_cellar"
jurisdiction = "EU"
SPARQL = "http://publications.europa.eu/webapi/rdf/sparql"
CELEX_SCOPE = ["32001L0029", "32019L0790", "32009L0024", "31996L0009", "32006L0116", "32004L0048"]


def discover(since: Optional[str] = None) -> Iterable[str]:
    return list(CELEX_SCOPE)


def fetch(ref: str) -> Optional[FetchedVersion]:
    raise NotImplementedError("Phase 0: Cellar content-negotiate CELEX -> FetchedVersion (is_authentic=False for consolidated)")
