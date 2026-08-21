"""Claude drafting for the comparative matrix — wired straight to claude-opus-4-8 (prime rule 5).

Given a jurisdiction, an attribute, and the FETCHED text of a cited provision, ask the model for a
short comparative value grounded ONLY in that text (prime rule 1 — never originate law). Offline-safe:
with no ANTHROPIC_API_KEY it raises RuntimeError so callers skip rather than invent data. No provider
abstraction, no LangChain.

This is the UNATTENDED path (a future cron/batch once a key is in .env). The current seed
(`seed_cells.py`) was drafted interactively by claude-opus-4-8 under the same discipline.
"""
from __future__ import annotations

import os

MODEL = "claude-opus-4-8"

_PROMPT = """You are drafting one cell of a cross-jurisdiction copyright comparison, for the \
attribute "{attribute}" in jurisdiction {jurisdiction}.

Use ONLY the statutory text provided below — do not use outside knowledge, and do not state anything \
the text does not support. If the text does not address the attribute, answer exactly: "Not addressed \
in the cited provision." Otherwise give ONE concise sentence (<= 40 words) stating the rule, and cite \
the section/article inline.

SOURCE TEXT ({citation}):
\"\"\"
{source_text}
\"\"\"
"""


def _client():
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY not set — matrix drafting is offline. Add it to .env to run the "
            "unattended draft batch; until then cells are drafted interactively (see seed_cells.py).")
    import anthropic                                        # imported lazily so the app runs keyless
    return anthropic.Anthropic(api_key=key)


def draft_cell(jurisdiction: str, attribute: str, source_text: str, citation: str = "") -> dict:
    """Return {value, drafted_by, model}. Raises RuntimeError offline (no key). Grounded ONLY in
    source_text; stored by the caller with verified_by=NULL until a human signs off."""
    client = _client()
    msg = client.messages.create(
        model=MODEL,
        max_tokens=200,
        messages=[{"role": "user", "content": _PROMPT.format(
            attribute=attribute, jurisdiction=jurisdiction, citation=citation or "—",
            source_text=source_text[:6000])}],
    )
    value = "".join(b.text for b in msg.content if getattr(b, "type", None) == "text").strip()
    return {"value": value, "drafted_by": f"model:{MODEL}", "model": MODEL}
