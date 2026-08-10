"""Connectors package. Register live connectors here as they land (Phase 0+)."""
from .base import Connector, FetchedVersion  # noqa: F401

# REGISTRY grows as connectors are implemented. Each entry: (module, env_key_or_None).
# Kept explicit (the ai-law-portal pattern) so update.py + staleness read one source of truth.
REGISTRY: list[tuple[str, str | None]] = [
    # ("legislation_uk", None),        # GB — CDPA 1988 (Phase 0)
    # ("govinfo_us",      "GOVINFO_API_KEY"),   # US — 17 U.S.C. (Phase 0)
    # ("ecfr_us",         None),        # US — 37 C.F.R. (Phase 0)
    # ("eurlex_cellar",   None),        # EU — DSM + InfoSoc (Phase 0)
    # ("treaties",        None),        # INT — hand-loaded (Phase 0)
    # ("legiscan",        "LEGISCAN_API_KEY"),  # US-states pipeline (Phase 3)
    # ("congress_gov",    "CONGRESS_GOV_API_KEY"),  # federal pipeline (Phase 3)
    # ("federal_register",None),        # US Copyright Office NOIs (Phase 3)
    # ("wipo_lex",        None),        # Tier 3 metadata, link-only (Phase 5)
]
