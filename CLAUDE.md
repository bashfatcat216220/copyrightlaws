# Copyright Corpus — Orientation for Incoming Code Agents

A private, source-grounded reference + change-monitor for copyright law across
jurisdictions. A **finding aid, never a citation**. Retrieval-first: connectors fetch
official text; the model only classifies / summarizes / redlines what was fetched.

Sibling project `~/ai-law-portal/` is the architectural template — same shapes
(connectors, SQLite+FTS5, per-source watermarks, staleness monitor, no-fake-data,
`source_url` + `retrieved_at` provenance, FastAPI+Jinja+HTMX). Lift patterns from it;
do NOT remix its data or "sync" the two — they are different corpora.

## Prime rules (apply everywhere)
1. **No fake law.** Never assert a law, citation, date, or version exists unless it came
   from a fetched source row. Not in the source → the field is NULL. The model summarizes
   and redlines fetched text; it never originates it.
2. **Finding aid, not authority.** Every screen shows `source_url` + `retrieved_at`. The
   standing caveat renders on EVERY page, not in an About screen:
   *"Internal research aid. Not verified for currency. Confirm against the official source
   before relying on it in client work."*
3. **Flag the caveats per source.** Unofficial translation → `is_official_language=0`
   (label it). EU consolidated → `is_authentic=0` ("not authentic"). UK consolidated may
   carry `has_unapplied_effects=1`. Surface these in the UI, never silently.
4. **The matrix is human-gated.** Comparative-matrix cells are model-DRAFTED from a cited
   source version but shown as authority ONLY when `verified_by` is set. Same discipline as
   ai-law-portal's privilege labels: draft → human sign-off → publish.
5. **Claude-only reasoning.** Wire model calls straight to `claude-opus-4-8` (drafting the
   matrix, plain-language summaries, redline explanations, copyright-relevance screening).
   No provider abstraction, no LangChain. Offline-safe stub without a key.

## Data model (db/schema.sql — read it first)
- `instruments` — a law/reg/treaty/directive/bill as an IDENTITY (title, citation, ELI/
  CELEX/WIPO/USC id, status, dates). Unique on (jurisdiction, ext_id_scheme, ext_id).
- `versions` — **the load-bearing table**: the consolidated text AS IN FORCE at a
  `point_in_time`, with `content_sha256` (the change key), `source_url`, `retrieved_at`,
  and the authenticity/translation flags. One `is_current` per instrument.
- `amendments` — amending → amended, sections + effect.
- `bills` — pipeline items, linked to the instrument they'd become/amend.
- `alerts` — a fired change-monitor rule (a version diff).
- `matrix_cells` — the product: one row per (jurisdiction, attribute); `verified_by`
  gates authority.
- `versions_fts` — FTS5 over version text (synced by the store layer).
- Triggers enforce: a version with text must carry a sha256; a verified matrix cell must
  cite a source version.

## Connector contract (`src/connectors/base.py`)
One module per source, uniform interface. A connector `discover(since)` -> refs and
`fetch(ref)` -> a `FetchedVersion` (official text + provenance). Connectors NEVER write the
DB directly and NEVER originate text — the `store/` layer canonicalizes, computes the
sha256, versions, and syncs FTS.

## Source-of-truth table (Tier 1 first)
| Jurisdiction | Instrument(s) | Source | API? | Key |
|---|---|---|---|---|
| GB | CDPA 1988 | legislation.gov.uk (`/data.xml`, Publication Log Atom = free change feed) | yes | none |
| US | 17 U.S.C. | GovInfo bulk USLM XML (OLRC) | yes | GOVINFO_API_KEY |
| US | 37 C.F.R. | eCFR API | yes | none |
| US | Copyright Office Compendium / Circular 92 | copyright.gov | no | — (hand-load) |
| EU | InfoSoc 2001/29, DSM 2019/790, Software/Database/Term/Enforcement | EUR-Lex CELLAR (SPARQL + REST); consolidated = NOT authentic | yes | none |
| INT | Berne, TRIPS, WCT, WPPT, Rome, Beijing, Marrakesh | hand-loaded treaty texts | no | — |
| US-states | copyright-adjacent bills (TDM, digital replica, right of publicity) | LegiScan | yes | LEGISCAN_API_KEY |
| US | Copyright Office NOIs / rulemakings | Federal Register API | yes | none |
| pipeline | copyright-tagged bills | Congress.gov | yes | CONGRESS_GOV_API_KEY |
| Tier 3 (~170) | metadata + link only | WIPO Lex (NO API — scrape carefully, email WIPO on reuse; label "not maintained") | no | — |

## Phased roadmap
- **Phase 0** — one vertical slice END-TO-END (fetch → version → store → search page →
  change monitor). Proves the versioning schema before a second source is touched.
  (First slice per user: US + UK + EU + core treaties together.)
- **Phase 1** — the rest of Tier-1 corpus; three source shapes stress-test the schema.
- **Phase 2** — change monitoring (hash-diff → redline → digest). Where partners start caring.
- **Phase 3** — pipeline tracker (Congress + LegiScan 50-state + EUR-Lex prep acts + FR NOIs).
- **Phase 4** — Tier 2 jurisdictions + the comparative matrix.
- **Phase 5** — Tier 3 metadata index from WIPO Lex, link-only, "not maintained".

## How to run
- Init DB:  `python src/db.py`
- Web:      `uvicorn src.app:app`  -> http://localhost:8000
- (connectors/monitor/matrix are stubs until Phase 0 — see the module docstrings)

## Decisions pending
- Hosting (local vs Render, mirroring ai-law-portal).
- Own venv vs. reuse `~/ai-law-portal/.venv` (has fastapi/uvicorn/jinja2/requests/anthropic).
- Confirm the Phase-0 first-slice instruments (CDPA 1988 / 17 U.S.C. / DSM+InfoSoc / Berne).

## Update rule
End each session: update the roadmap + a PROJECT_STATE.md (create when Phase 0 starts) so
the next session starts oriented from disk, not memory.
