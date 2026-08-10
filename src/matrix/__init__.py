"""Comparative attribute matrix — the product.

One row per (jurisdiction, attribute). The value is DRAFTED by the model from a cited source
version, then HUMAN-VERIFIED before it is shown as authority (verified_by gates it — a schema
trigger refuses to verify a cell with no source_version). Same gate as ai-law-portal's
privilege labels: draft -> review -> publish.

Phase 4. The canonical attribute set (columns) below is the partner-facing question list.
"""
from __future__ import annotations

# The columns partners actually ask about (not the raw corpus).
ATTRIBUTES = [
    "term_individual",          # life + N years
    "term_corporate",           # works made for hire / corporate authorship
    "term_anonymous",
    "registration_required",    # formalities
    "moral_rights_scope",
    "moral_rights_waivable",
    "moral_rights_duration",
    "tdm_exception",            # text-and-data-mining exception exists?
    "tdm_commercial",           # ...and does it cover COMMERCIAL AI training?
    "fair_use_vs_closed_list",  # open standard vs enumerated exceptions
    "safe_harbor_regime",       # notice-and-takedown
    "orphan_works_mechanism",
    "private_copying_levy",
    "statutory_damages",
    "termination_reversion",    # termination / reversion rights
]


def draft_cell(jurisdiction: str, attribute: str, source_text: str) -> dict:
    raise NotImplementedError(
        "Phase 4: claude-opus-4-8 drafts the answer from source_text ONLY, cites the section; "
        "stored with verified_by=NULL until a human signs off")
