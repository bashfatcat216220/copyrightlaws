# Copyright Corpus — PROJECT_STATE

> Status comes from THIS file, read fresh. Do not answer "where are we" from memory.

_Last updated: 2026-08-12._

## Where we are (one breath)

**Phase 0 is COMPLETE.** The KM IP — Statute Browser design is live over a section-level
`provisions` model, with real copyright law from all four Tier-1 source shapes ingested,
searchable, and cited at the provision level. Migration applied to `corpus.db`; branch pushed.

- **Corpus (live in `corpus.db`):** **18 instruments · 12,857 provisions · 4,516 versions**,
  every version SHA-256'd with `source_url` + `retrieved_at`. **Phase 2 breadth: Tier-1 (4) +
  all 14 Tier-2 countries DONE.**
  | Jur | Instrument | Source | Provisions | Lang |
  |---|---|---|---|---|
  | US | 17 U.S.C. | USLM XML | 153 sections (4 deep) | official |
  | GB | CDPA 1988 | CLML XML | 436 sections + 349 schedule paras | official |
  | EU | Directive 2001/29 (InfoSoc) | Formex + OJ HTML | 15 articles + 61 recitals | official |
  | INT | Berne Convention | WIPO Lex HTML | 53 articles (bis/ter + Appendix) | official |
  | DE | UrhG | gesetze-im-internet.de | 252 sections | translation |
  | CA | Copyright Act (C-42) | Justice Laws XML | 277 sections + 11 parts | official |
  | AU | Copyright Act 1968 | legislation.gov.au | 670 sections | official |
  | NL | Auteurswet | IViR PDF | 138 articles | translation |
  | IN | Copyright Act 1957 | India Code PDF | 105 sections | official |
  | SG | Copyright Act 2021 | SSO HTML | 541 sections | official |
  | FR | CPI (Part I) | WIPO Lex PDF | 183 articles | translation |
  | ES | TRLPI (RDL 1/1996) | WIPO Lex PDF | 170 articles | translation |
  | IT | Law 633/1941 (LDA) | WIPO Lex PDF | 252 articles (bis/ter/quater) | translation |
  | JP | Copyright Act (1970) | japaneselawtranslation.go.jp | 183 articles | translation |
  | CN | Copyright Law (2020) | WIPO Lex (verbatim, Wikisource-checked) | 67 articles | translation |
  | KR | Copyright Act | KLRI elaw | 180 articles | translation |
  | BR | Law 9.610/1998 | WIPO Lex PDF | 122 articles | translation |
  | MX | LFDA | WIPO Lex text-view | 238 articles | translation |
- **Live server:** `uvicorn src.app:app` on `corpus.db`, http://127.0.0.1:8021 — the section
  reader shows real law across all 18; search grounded (`fair use`→§107, `fair dealing`→CA
  s.29 / AU s.40, `parody`→InfoSoc Art.5(3)(k) / FR L122-5, moral rights across every act).
- **Git:** `main` pushed to `origin` (github.com/bashfatcat216220/copyrightlaws.git). `pytest` 6/6.
- **Environment:** repo at `~/TIngey/copyright-corpus`; run python via
  `~/Julie/ai-law-portal/.venv/bin/python` (fastapi/uvicorn/jinja2). No `sqlite3` CLI on this
  box — use Python's `sqlite3`. `~/TIngey/copyright-news-site` is a SEPARATE project — never
  conflate. `db/corpus.db` + `db/corpus-demo.db` + `spike/` are gitignored (rebuildable/local).

## What's built (this session)

1. **UI reskin** → the design handoff's system (`~/Downloads/IP Professionals Legal
   Platform(1).zip`). `templates/*`: Source Serif 4 (reading) / IBM Plex Sans (interface) /
   IBM Plex Mono (identifiers); Navy = links/position only, Rust = adverse only; square
   corners, no shadows, no chips. Dark top bar + breadcrumb (live counts) + the standing
   finding-aid caveat on every page. NOTHING from the mockup's fake prose/cases/"VERIFIED"
   line was copied (prime rule 1).
2. **Provisions schema** — `db/migrations/001_provisions_rebuild.sql`, **APPLIED to
   `corpus.db`** (Bing signed off 2026-08-12). Adds `provisions` (the section tree),
   `case_treatment`, `provisions_fts`; rebuilt `versions` to hang off `provision_id`. See
   "Key decisions" for the shape.
3. **Four re-runnable, idempotent ingests** in `src/store/` (each refuses `corpus.db` without
   `--allow-corpus`; keyed on stable `citation` so re-parses never duplicate):
   `ingest_uslm.py` (US), `ingest_clml.py` (UK), `ingest_formex.py` (EU articles + recitals),
   `ingest_berne.py` (treaty HTML). They read retained source artifacts from `spike/artifacts/`.
4. **Section-level reader** — `src/app.py` `_section_reader`: chapter-grouped rail of leaf
   provisions (`kind IN ('section','article','schedule_para','recital')`) + reading column +
   Cases/History practice panel. Guarded — falls back to whole-instrument view when an
   instrument has no provisions, so an empty DB still renders.

## Key decisions & findings (durable — the "why")

- **Provisions model.** One generic tree serves every jurisdiction (US section, UK section
  **and** schedule paragraph, EU article, treaty article — all provisions). `versions` hang
  off a provision → per-provision text, diff (`content_sha256`), and pinpoint citation.
- **`role` enum, not an `operative` boolean.** `enacting` / `schedule` (both operative,
  counted & diffed) / `recital` (interpretive — addressable + searchable, never counted) /
  `quoted` (other instruments' words — never surfaced). A boolean was too coarse: recitals
  and quoted-amendment text are both "non-operative" but must behave differently.
- **Ordinal = `(sort_int, sort_suffix COLLATE BINARY)`**, never a bare integer. Handles
  inserted/suffixed provisions across all shapes: US §106A (between 106/107), UK §296ZA,
  Berne Art. 6bis. Collation is PINNED (296Z<296ZA<296ZEA sorts right only under binary).
- **Non-operative axis = QUOTED/AMENDING text, NOT Body-vs-Schedule.** UK Schedules are
  operative law (Sch 1 transitional term, Sch 2 permitted acts) → `kind='schedule_para'`,
  separate numbering class. Only `quotedContent`/`BlockAmendment`/`Quotation` (reproducing
  OTHER acts) are skipped.
- **`is_authentic` earns its place.** EU consolidated articles are `is_authentic=0`; EU
  recitals (from the original OJ) and Berne treaty text are `is_authentic=1`. InfoSoc proves
  the split WITHIN one instrument: authentic recitals alongside non-authentic consolidated
  articles, each with its own `source_url`.
- **Labels are source-given per node**, never inferred from a jurisdiction switch — that's
  what keeps it one design across US/UK/EU/INT.
- **Nav hierarchy has 4 tiers, do NOT collapse:** Jurisdiction rail → Instrument →
  Provision d1 (chapters) → Provision d2 (sections/articles) → deeper addressable pinpoints.
- **Drafting each ingest caught real schema/parse bugs before they bit** — that's the point:
  versions UNIQUE needed `provision_id`; `kind` CHECK needed USLM's deep levels; CDPA
  Schedule-1 Parts had to preserve schedule context; InfoSoc recitals live in the original OJ
  (the `legal-content/…/XML` endpoint returns a CELLAR *notice*, not the act — use `…fmx4`).

### Applied schema (migration 001)
```
provisions(id, instrument_id, parent_id, sort_int, sort_suffix COLLATE BINARY, label,
           heading, kind, role DEFAULT 'enacting', citation, status, UNIQUE(instrument_id,citation))
versions   + provision_id  (NULL = whole-instrument version); content_sha256 = per-provision change key
case_treatment(id, provision_id, case_instrument, treatment, holding, source_url, retrieved_at)  -- Cases tab (empty today)
provisions_fts(citation, heading, body)  -- provision-scoped search
```

### Source plan (endpoints PROVEN in the spike — keyless)
| Source | Fetch | Shape | Change feed |
|---|---|---|---|
| US 17 U.S.C. | `uscode.house.gov/download/releasepoints/us/pl/<cong>/<pt>/xml_usc17@<cong>-<pt>.zip` | USLM | OLRC release points |
| UK CDPA 1988 | `legislation.gov.uk/ukpga/1988/48/data.xml` | CLML | Publication Log Atom |
| EU directives | `publications.europa.eu/resource/celex/<CELEX>.ENG.fmx4` (act) + `eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:<id>` (OJ recitals) | Formex/HTML | CELLAR |
| Treaties | WIPO Lex `text/<id>` HTML (e.g. Berne = 283698) | HTML | none (manual) |

Ingests currently read RETAINED artifacts; a real **connector** (`discover`+`fetch`) that
pulls these live is not yet built — that's the automation step for change-monitoring.

## Known refinements (small, non-blocking)

- **CDPA schedule-paragraph pinpoints** — some collide (schedule sub-structure the citation
  doesn't yet capture); guarded by a deterministic `#n` suffix so nothing is overwritten.
  Real fix: full schedule-Part pinpointing in the CLML citation.
- **Rail display depth** — we store 4 levels, rail 2 (chapter→section/article). Whether a
  long section's rail should expand to subsections is unspecified by the mockup (a design Q).
- **Treaty/article rail group label** — ungrouped provisions (Berne articles) render under a
  generic header; could label per instrument type.

## Next steps — roadmap

**Sequencing decision (Bing, 2026-08-12): breadth before depth.** Phase 2 = fill the corpus
with jurisdictions (full text), THEN add the depth layers. The reader already mixes shallow
and deep instruments (whole-instrument fallback when an instrument has no provisions), so
breadth can land incrementally.

**▶ Phase 2 — jurisdiction breadth (full text, ~18 jurisdictions). IN PROGRESS.**
Finish Tier-1, then add the 14 Tier-2 countries with real provision text. No Tier-3 long
tail / WIPO-Lex metadata index yet (that's a later, shallower pass).
- **Finish Tier-1:**
  - **US 37 C.F.R.** (Copyright Office regs, parts 201–212) — eCFR API, keyless. New shape → new ingest.
  - **EU directives** — DSM 2019/790, Software 2009/24, Database 96/9, Term 2006/116,
    Rental/Lending 2006/115, Orphan Works 2012/28, Enforcement 2004/48. **Reuse
    `ingest_formex.py`** — needs a small generalization: the instrument identity (CELEX/title)
    is currently hardcoded to InfoSoc; parameterize it, then it's fetch-CELEX-and-run.
  - **Core treaties** — TRIPS (WTO), WCT, WPPT, Rome, Beijing, Marrakesh. Reuse the
    `ingest_berne.py` WIPO-Lex HTML pattern (TRIPS is WTO-hosted).
- **Tier-2 countries (the jurisdiction fill):** DE ✅, then FR, ES, IT, NL, CA, AU, JP, CN,
  KR, IN, BR, MX, SG. **Reality check (from the DE proof):** Tier-2 is HETEROGENEOUS — no
  single reusable parser. Sources differ (WIPO Lex is PDF-only for DE; the clean text was the
  national portal gesetze-im-internet.de), structures differ (DE §-Sections in Divisions; FR
  Articles L111-1…; etc.), and most are UNOFFICIAL translations → `is_official_language=0`
  (flagged). So each country = its own source hunt + bespoke parser, but the DB-writer +
  provision model are identical.
  - **ALL 14 DONE (2 waves of parallel agents):** DE, CA, AU, NL, IN, SG, FR (wave 1) + ES,
    IT, JP, CN, KR, BR, MX (wave 2). Each `src/store/ingest_<cc>.py` built on `_common` (see
    the corpus table for source/counts/lang). Official English where published (CA/AU/IN/SG),
    else translations flagged `is_official_language=0`. All idempotent, grounded, scratch-
    validated before loading. Each agent wrote only its ingest + artifact (no corpus.db /
    shared-file / git touch); the orchestrator validated + loaded centrally.
  - **Sourcing notes worth keeping:** WIPO Lex PDFs sit behind CloudFront presigned URLs (grab
    the signed link off the details page; bare paths 301/403). MX has no English PDF anymore →
    used WIPO's text-view HTML. CN's CDN 403s scripted fetch → verbatim text via a reader proxy,
    cross-checked against Wikisource. NL used the IViR academic translation (WIPO PDF dead).
  - **Tier-1 completions still open (Phase-2 tail):** EU directives (DSM 2019/790 + others) via
    the Formex pattern (needs `ingest_formex.py` generalized off the hardcoded InfoSoc identity),
    core treaties (TRIPS/WCT/WPPT/Rome/Beijing/Marrakesh) via the Berne HTML pattern, US 37 C.F.R.
    via eCFR. These round out US/EU/INT depth; no NEW jurisdictions.
  - **`_common.py` extracted (`ef8ecdc`)** — a new country ingest is now just `parse()` + an
    INSTRUMENT dict + a thin `main()`; agents copy `ingest_de_urhg.py` as the template.
  - **Sourcing reality (confirmed across wave 1):** heterogeneous — official HTML/XML (CA/AU/
    SG), official PDF (IN), academic/WIPO PDF translations (NL/FR), national portal (DE). Some
    ingests read a `pdftotext` .txt via the `--html` flag. Minor per-source parse notes (e.g.
    IN footnote fragments, FR duplicated headers collapsed) are logged in each ingest's report.

**Phase 3+ — the depth layers (deferred until breadth lands):**
- **Change monitoring** — re-fetch → per-provision `content_sha256` diff → `alerts` → redline/
  digest (`src/monitor/`), paired with real `discover`/`fetch` connectors so re-fetch is automated.
- **Cases tab → real data** (`case_treatment`, per-provision treatment; rust = adverse).
- **Deep-linkable provision URLs** (`/instrument/{id}/{citation}`; today `?sec=<id>`).
- **Comparative matrix** — point `matrix_cells.source_version` at a provision-scoped version;
  human-gated.
- **Tier-3 metadata index** (WIPO Lex, ~190 jurisdictions, link-only, "not maintained").
- **Own venv + hosting** (still borrowing `~/Julie/ai-law-portal/.venv`; local vs Render).

## Decisions still pending (from CLAUDE.md)
- Hosting (local vs Render); own venv vs. borrowing ai-law-portal's.
- **Copyright-only vs IP-wide** — the product name says IP, the corpus is copyright. If patent
  (Title 35) / trademark (Lanham) / trade secret (DTSA) are coming, the top nav needs a
  body-of-law row above the material-type row. Deliberately unresolved.
- Recitals-as-provisions: RESOLVED and shipped (kind='recital', role='recital'). Sub-call
  still open: whether CDPA consequential-amendment/repeal schedules (Sch 7/8) are operative-here.
