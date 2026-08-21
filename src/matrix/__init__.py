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


# draft_cell is wired to claude-opus-4-8 in draft.py (offline-safe: raises without a key). The
# interactive seed in seed_cells.py was drafted under the same discipline; load_cells.py stores it,
# verify.py gates it. Imported lazily so the web app never imports anthropic.
def draft_cell(jurisdiction: str, attribute: str, source_text: str, citation: str = "") -> dict:
    from .draft import draft_cell as _draft
    return _draft(jurisdiction, attribute, source_text, citation)
