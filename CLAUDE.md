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
> Reordered in execution (Bing, 2026-08): **breadth before depth** — fill jurisdictions first,
> then monitoring/cases. Live status + the exact ordered backlog live in `PROJECT_STATE.md`
> (read it fresh); this is the durable shape.
- **Phase 0 — DONE.** One vertical slice end-to-end (fetch → provisions → version → reader →
  search), then the `provisions` migration signed off + applied. Schema proven on 4 source
  shapes (USLM / CLML / Formex / WIPO HTML).
- **Breadth — DONE (Tier-2, 14 countries) · Tier-1 completions IN PROGRESS.** 18 instruments
  loaded (US/UK/EU/INT + DE/CA/AU/NL/IN/SG/FR/ES/IT/JP/CN/KR/BR/MX). Tier-1 completions
  (37 C.F.R. + the rest of the EU directives + the core treaties) DONE → 32 instruments.
- **Depth layers — IN PROGRESS.** DONE: change monitoring (hash-diff → redline → `/alerts`
  digest + daily `src/monitor/refresh.py` cron, UK+US) · real Cases data (`case_treatment`,
  CourtListener opinions citing a section). TODO: per-subsection text; deep-linkable provision
  URLs (`/instrument/{id}/{citation}`); the comparative matrix (human-gated). Live status +
  the ordered backlog live in `PROJECT_STATE.md` — read it fresh.
- **Validity audits (recurring).** Read-only agents check stored law against official sources
  per jurisdiction; findings + fixes are logged in `PROJECT_STATE.md` ("Audit & remediation").
  Parsers are hardened to NEVER mint pinpoints from body cross-refs (treaty: paragraph number
  must be 1–20) and to strip scraped `<script>`/`<style>` before storing text — both are
  prime-rule-1 (no fake law) guards; keep them when touching the ingests.
- **Pipeline tracker — TODO:** Congress + LegiScan 50-state + EUR-Lex prep acts + FR NOIs.
- **Tier-3 — TODO:** metadata index from WIPO Lex, link-only, "not maintained".

## How to run
- Python: `~/Julie/ai-law-portal/.venv/bin/python` (fastapi/uvicorn/jinja2). No `sqlite3` CLI.
- Init DB:  `python src/db.py`  · apply the provisions migration: run
  `db/migrations/001_provisions_rebuild.sql` (already applied to `corpus.db`).
- Web:  `uvicorn src.app:app` (we run `--port 8021`) -> the reader/search over the live corpus.
- Ingest a source: `python src/store/ingest_<x>.py --db db/corpus.db --allow-corpus --html/--xml <artifact> --source-url <url>`. `store/_common.py` = shared writer (idempotent BY CONTENT — re-fetch of unchanged text adds no version).
- Change monitor: `python src/monitor/monitor.py --db db/corpus.db [--instrument N]` (diffs version history → `alerts`); `src/monitor/refresh.py` = fetch → re-ingest → monitor (cron). Matrix still a stub.
- corpus.db + corpus-demo.db + spike/ are gitignored (rebuildable from the ingests).

## Decisions pending
- Hosting (local vs Render, mirroring ai-law-portal).
- Own venv vs. reuse `~/ai-law-portal/.venv` (has fastapi/uvicorn/jinja2/requests/anthropic).
- Confirm the Phase-0 first-slice instruments (CDPA 1988 / 17 U.S.C. / DSM+InfoSoc / Berne).

## Update rule
End each session: update the roadmap + a PROJECT_STATE.md (create when Phase 0 starts) so
the next session starts oriented from disk, not memory.
