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
3a. **Authority is its own axis, NOT a function of `type` or publisher** (migration 002).
   The U.S. Copyright Office produces BOTH binding legislative rules (37 C.F.R., notice-and-
   comment under delegated authority — force of law) AND non-binding guidance (the Compendium,
   circulars) — same author, different legal status by PROCESS. So `instruments.authority` =
   `binding` | `persuasive` | `precedent` is set by process, never inferred from `type`.
   Also per-instrument: `positive_law` (Title 17 is enacted into positive law → its Code text
   is *legal evidence of the law*, not merely prima facie; varies by title/jurisdiction);
   `source_edition` (eCFR & OLRC-online are government *finding aids*, NOT the official legal
   edition — the GPO annual CFR + Federal Register / the printed U.S. Code control). Caselaw is
   a FOURTH category (`type='case'`, `authority='precedent'`, `court_level`): binding vs
   persuasive is CONTEXTUAL to the reader's court — compute it, never flatten it into guidance.
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
- **Validity audits (recurring).** Read-only `fable` agents check stored law against the SOURCE
  ARTIFACT (not just the DB) per jurisdiction. The full 18-jurisdiction sweep (2026-08-14) is in
  `AUDIT-FINDINGS-2026-08-14.md` with per-finding fix status; live status in `PROJECT_STATE.md`.
  Waves 1–3 done (fabricated treaty pinpoints purged + root fixes; CDPA repeal notices + `status`;
  SG/CA/AU structural excisions). Waves 4–6 on the docket (PDF footnote purges ES/NL/IN/IT incl.
  ES Art.28; missing content IT 182 / ES back-matter / CDPA Sch.5A / MX transitory / treaty Agreed
  Statements; currency-vintage UI flags FR ~2006 & ES ~2012, CN citations, KR `¡?`, eCFR headings).
- **Pipeline tracker — TODO:** Congress + LegiScan 50-state + EUR-Lex prep acts + FR NOIs.
- **Tier-3 — TODO:** metadata index from WIPO Lex, link-only, "not maintained".

## Ingest correctness rules (audit-hardened — keep these when touching `src/store/`)
Learned from the 2026-08-14 audit; these are prime-rule-1 (no fake law) corollaries.
1. **No fabricated pinpoints — sequential numbering only.** A numbered-paragraph child `(N)` is
   real ONLY as part of a contiguous run `(1),(2),(3)…`. A lone/out-of-sequence `(N)` is a
   footnote marker ("other use (7)"), a cross-reference ("Article 7(1) of…"), a year ("(1971)"),
   or a duplicate — NEVER mint a provision for it. Enforced in `ingest_treaty`/`ingest_berne`
   (`expected`-counter). The old "1–20 range" guard was insufficient. Also: never let the
   `RecordSet` `#N` collision-uniquifier create pinpoint citations (e.g. `Art. 30(2) #2`).
2. **Repeal notices, not blanks.** A repealed/deleted/omitted/vetoed/reserved provision shows the
   SOURCE's own notice verbatim (e.g. "S. 265 repealed (9.12.2001) by S.I. 2001/3949…", "[Deleted]",
   "(abrogé)") + `status='repealed'`. Never blank, never a fabricated pre-repeal text (that text is
   usually not in the source). `_common.is_repealed()` auto-detects the tombstone → sets `status`;
   `ingest_clml` mines the `<Commentary>` for CDPA's empty `<Text/>` stubs. Reader shows a rust
   "Repealed" badge. Where no heading/text exists at all, show the "read at source" placeholder.
   Textual-notice detection alone is NOT enough for CLML — the structural dotted-leader / `Status`
   signals are handled by `ingest_clml.is_tombstone`/`_heading` (see rule 11).
3. **Segmentation stops at structural boundaries.** An article/section body must NOT run to
   "next Article" or end-of-file — cut at the annex/appendix/footnote/endnote block, the trailing
   table-of-contents, the amending-act "RELATED PROVISIONS" appendix, or the schedule. The
   classic bug is the LAST element swallowing everything after it (TRIPS Art.73 ate the Annex;
   AU s.249 ate 68 KB of endnotes; SG re-parsed a trailing TOC into 111 ghost containers; CA
   ingested amending-act sections as fake C-42 pinpoints).
4. **PDF-extracted sources (`*.txt` from `pdftotext`) leak footnotes.** Strip superscript markers
   glued to words (`3[sound recording]`, "authors.6,7") and footnote BODIES absorbed at an
   article's tail — and beware a footnote digit fused into an article NUMBER (IT "Article 182" +
   fn "8" → "1828", which dropped Art. 182 entirely). Verify article NUMBERING is complete.
5. **Strip scraped junk before storing.** Remove `<script>`/`<style>` blocks BEFORE tag-stripping
   (else inner JS survives as text); drop dangling unclosed tags at end-of-fragment (`<div`);
   strip EUR-Lex consolidation markers `▼B/▼M1/►M1◄` as a unit; normalize known mojibake.
6. **Cross-manifestation ≠ amendment.** Re-basing an instrument onto a different source shape
   (EU original→consolidated; 2017→2019 Formex) is NOT an observed amendment — do NOT run the
   change monitor for it (a cross-source text diff is formatting noise that would fire false
   "changed" alerts). The monitor is only meaningful across SAME-source point-in-time versions.
7. **Don't full-re-ingest a point-in-time-monitored instrument** (CDPA carries pit versions +
   fired `alerts` + the s.205B merge). Apply targeted/surgical fixes to the current version to
   avoid disrupting monitoring history; fix the ingest for durability + verify on a scratch clone.
8. **Flag stale sources.** Some hand-loaded translations are years behind (FR CPI ~2006, ES TRLPI
   ~2012). The text is faithful-as-of-its-vintage but silently stale → surface a "source vintage"
   caveat in the UI on those instruments (Bing-approved 2026-08-14). Documented R-article / scope
   exclusions (e.g. FR regulatory articles) belong in the instrument note too.
9. **Verify against the SOURCE artifact, not the DB.** The DB can look complete while the parser
   dropped, blanked, or misattributed content — always diff stored provisions against the fetched
   artifact. Scratch-clone with the sqlite backup API (a bare `cp` misses the WAL).
10. **Back-matter is operative law — capture it, model it as a schedule (2f/2g audit, 2026-08-16).**
   Appendices, annexes, schedules, addenda (KR 부칙), supplementary/transitional provisions (JP 附則,
   US Pub. L. 94-553 §§102–115) are OPERATIVE and must be ingested, not dropped at the tail. The
   parser-class bug is a `parse()` that stops at the last numbered section/article. Model them with
   EXISTING kinds — `kind='schedule'` container + `kind='schedule_para'` sub-items, `role='schedule'`
   (the TRIPS-annex precedent in `ingest_treaty.py`; the `kind` CHECK has no `annex`, so DON'T add one).
   Repeal tombstones (CA Sch II/III `[Repealed…]`) keep the source notice verbatim + `status='repealed'`
   (rule 2). Scope surgically: capture ONLY genuine back-matter, never the amending-act "RELATED
   PROVISIONS"/"AMENDMENTS NOT IN FORCE" appendices (excluded) or ~625 editorial statutory notes.
   Reader caveat: a `kind='schedule'` container that holds body but has NO `schedule_para` children does
   NOT yet rail in the reader (reachable only via search / deep-link) — a known surfacing gap (Wave E).
   **Adding back-matter improves COMPLETENESS, not AUTHORITY — the tool stays a finding aid (prime rule 2).**
11. **Repeal signals are STRUCTURAL, not just textual (legislation.gov.uk dotted-leader convention, 2026-08-17).**
   CLML marks a fully-repealed provision three ways the textual-notice detector (rule 2) missed: (a) the whole
   body is a pure dotted leader (`5 . . . .`) with no words; (b) a `Status="Repealed"` attribute on the element
   (sometimes with no keyed `<Commentary>`); (c) the dotted "no heading" marker lands in `<Title>` while the real
   repeal notice sits in the BODY (s.265 → "S. 265 repealed (9.12.2001) by S.I. 2001/3949…"). `ingest_clml.is_tombstone`
   reads (a)+(b) → `status='repealed'`, keeping the dotted text VERBATIM (prime rule 1 — never blank, never
   fabricate pre-repeal text); `ingest_clml._heading` NULLs a dots-only `<Title>` so the reader rails the body's
   notice, not a wall of dots. Reader `_fill_incipits` shows a muted `[Repealed]` label ONLY when `status='repealed'`
   AND the body is a pure dotted leader — a notice body keeps its informative incipit. Do NOT flag a PARTIAL
   omission (real text with an embedded `. . .`, e.g. s.29/s.72, or a trailing omitted-words marker in a real
   heading like s.14 "…broadcasts . . . .") — the body test is a `fullmatch`, never a substring. `status`/`heading`
   corrections are metadata-only (no content/sha writes) → monitor-safe; apply surgically (rule 7) via a migration
   (`004_cdpa_repealed_tombstones.py`, `005_cdpa_dotted_headings.py`) AND make them durable in the ingest.

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
