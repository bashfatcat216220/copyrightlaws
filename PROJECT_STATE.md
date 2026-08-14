# Copyright Corpus — PROJECT_STATE

> Status comes from THIS file, read fresh. Do not answer "where are we" from memory.

_Last updated: 2026-08-14._

## Where we are (one breath)

**Phase 0 done · jurisdiction breadth done · Tier-1 completions done.** **32 instruments ·
14,088 provisions · 5,325 versions** across 18 jurisdictions. US = 17 U.S.C. + 37 C.F.R.;
EU = 8 copyright directives (InfoSoc + DSM/Software/Database/Term/Rental/Orphan/Enforcement);
INT = 7 treaties (Berne + WCT/WPPT/Rome/Beijing/Marrakesh/TRIPS); + all 14 Tier-2 countries
(see the corpus table). The KM IP — Statute Browser design is live over the section-level
`provisions` model — full-width reader, fixed-height shell, internal-scrolling rails, KM
marker-paragraph body, a small italic sources note on the home page, and per-list aligned
section-number columns. **Change-monitoring is live AND auto-refreshing** — `/alerts` lists 90
real UK CDPA amendments (2015→now, incl. the Brexit "EEA State"→"United Kingdom" changes) with
reader redlines, and `src/monitor/refresh.py` re-pulls UK+US on a daily cron → re-ingests →
fires new alerts (**91** after the s.205B merge below). **Cases data is live** — the reader's
Cases tab shows real US opinions citing a section (CourtListener, treatment='cited'). A
**4-agent validity audit (fable, read-only) ran 2026-08-14** across US/EU/INT/UK; the corpus is
substantively grounded (verbatim text, provenance-stamped) and the 3 concrete defects it found
are **fixed** (see "Audit & remediation"). Next depth items: per-subsection text, deep-linkable
URLs, matrix (see "Remaining work"). corpus.db migrated + loaded; branch pushed.

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
- **`status` is coarse (US audit note)** — repealed/renumbered US sections (e.g. 17 U.S.C. §116A
  "[Renumbered]", §601 "[Repealed]") and eCFR "[Reserved]" 37 C.F.R. sections carry
  `status='in_force'`. The *text* is honest (the official bracket-note / NULL), only the status
  metadatum is imprecise. Cheap fix: set `status='repealed'|'renumbered'|'reserved'` on those rows.
- **`point_in_time` NULL on US versions** — 17 U.S.C. / 37 C.F.R. currency is implied by the
  release-point / eCFR-date in `source_url`, not stamped in `point_in_time` (UK versions do carry it).

## Audit & remediation (2026-08-14, 4 fable read-only agents)

Four independent `fable` agents audited law validity against official sources, read-only
(one each: **US, EU, INT, UK**). Overall: the corpus is **substantively trustworthy** — text is
verbatim from fetched artifacts, provenance-stamped (`source_url` + `retrieved_at`), and honest
where NULL. **US verdict: VALID / HIGH confidence** (17 U.S.C. — 15 chapters/153 sections, and
37 C.F.R. Chapter II — both verified against live OLRC release-point 119-102 and the eCFR API;
no fabrication anywhere checked). EU/INT/UK were grounded too (INT even reproduces an OJ typo
verbatim) but surfaced **3 concrete defects — all now FIXED on both `corpus.db` + `corpus-demo.db`:**

1. **TRIPS fabricated pinpoints — FIXED (prime-rule-1 violation).** The treaty paragraph parser
   read cross-references in the body ("Berne Convention (1971)", "(1994)") as paragraph markers,
   minting **29 fake** `TRIPS Art. N(YYYY)`/oversized-parenthetical provisions. They carried **0
   versions** (structure-only) → deleted. Root-cause patched in `ingest_treaty._add_article`: a
   parenthetical is a pinpoint ONLY if it's a plausible paragraph number (1–20); years/oversized
   numbers are skipped. TRIPS paragraphs 175 → **146** (all legitimate). Scratch re-ingest of all
   treaties confirms **0** fakes regenerate.
2. **Treaty footer-JS contamination — FIXED.** Scraped page-footer `<script>` (a `var browser…
   window.print()` blob) had leaked into the body of the LAST article of 4 treaty versions
   (WIPO/WTO HTML segments run to end-of-page). Stripped from stored versions; `ingest_treaty._clean`
   now removes `<script>`/`<style>` blocks BEFORE tag-stripping so it can't recur. Scratch check: 0.
3. **UK CDPA s.205B duplicate — FIXED (+ masked alert recovered).** One point-in-time CLML
   snapshot carried a trailing dot on the section number (`Pnumber` = "205B."), so the reload
   forked s.205B into a parallel `s. 205B.` subtree instead of versioning the existing one — which
   **masked its change-monitor alert** (the current 2026-01-01 text landed on the dup; the canonical
   provision stayed frozen at the stale 2015 snapshot, so no diff ever fired). Merge: moved the
   current text onto canonical `CDPA 1988 s. 205B`, deleted the 13-row dotted subtree, re-ran the
   monitor → **91st alert** fired (Schedule 2 para 19 reference removed). `ingest_clml` now strips
   trailing dots from `Pnumber` (both P1 and sub-levels) so citations are stable across snapshots.

**Deferred (needs Bing's go-ahead — more involved):**
4. **EU consolidation currency.** Audit flagged that a few EU directives (Term / InfoSoc /
   Database) may be pointed at an older EUR-Lex consolidation than the latest. Re-pointing means
   re-fetching CELLAR consolidations + re-ingesting; not a data-corruption issue (text is authentic
   as-of its stated version), so parked until confirmed.

## Remaining work — finish in this order

**Sequencing (Bing): breadth before depth.** Tier-2 jurisdiction breadth is DONE (14 countries,
2 agent waves — see the corpus table above). Work this list top-to-bottom:

**1. Tier-1 completions — DONE (2026-08-13, 3 parallel agents).** Rounded out US/EU/INT depth
   (14 new instruments, 18→32). All grounded, idempotent, scratch-validated before central load.
   - **US 37 C.F.R.** (Copyright Office, Chapter II — Parts 201–212 + the Copyright Claims Board
     parts) — eCFR full-title XML → `src/store/ingest_ecfr.py`. 209 sections.
   - **EU directives** (7) — DSM 2019/790, Software 2009/24, Database 96/9, Term 2006/116,
     Rental 2006/115, Orphan Works 2012/28, Enforcement 2004/48 → `src/store/ingest_eu_directive.py`
     (EUR-Lex original-act HTML: articles + recitals, is_authentic=1; `--all` registry).
     125 articles + 267 recitals.
   - **Core treaties** (6) — WCT, WPPT (WIPO PDF), Rome, Beijing, Marrakesh (WIPO HTML), TRIPS
     (WTO HTML) → `src/store/ingest_treaty.py` (`--treaty all`). 218 articles. Agreed statements
     kept inline for the HTML treaties, skipped for the WCT/WPPT PDFs (noted, minor asymmetry).

**2. Depth layers** (breadth is complete; STARTED here):
   a. **Change monitoring — DONE (engine + UI, 2026-08-13).** `src/monitor/monitor.py` reads
      the per-provision version history and fires `alerts` rows with a word-level redline
      (− removed / + added) + change ratio; idempotent per (old_version, new_version). UI:
      `/alerts` page + nav badge + a rust-keyline redline block in the reader on changed
      provisions. **Proven on real data:** UK CDPA reloaded 2015-04-06 → current (legislation.
      gov.uk point-in-time) → 90 amended sections caught, redlines showing the Brexit changes
      ("an EEA State" → "the United Kingdom").
      **Connector / auto-refresh — DONE.** `src/monitor/refresh.py` re-fetches registered stable
      sources (UK CDPA `data.xml`, US 17 U.S.C. release-point zip) → re-ingests → runs the
      monitor → logs to `logs/refresh.log`. Scheduled via a **user crontab entry (machine-local,
      NOT in the repo — reinstall on a new machine):**
      `0 6 * * * cd <repo> && <venv>/python src/monitor/refresh.py --db db/corpus.db >> logs/refresh.log 2>&1`.
      To make refresh only version genuinely-changed provisions, `_store_version` is now
      **idempotent BY CONTENT** (skip if current text unchanged; on change, update the pit slot
      in place or insert) — applied in `_common` AND the pre-`_common` ingests (`ingest_uslm`,
      `ingest_clml`). REMAINING: add per-source fetchers for the signed-URL / PDF / national-portal
      sources (only UK + US are auto-refreshed today; the rest need a fetcher each).
   b. **Cases tab → real data — DONE (2026-08-14).** `src/store/ingest_cases.py` queries the
      CourtListener v4 API for opinions CITING each of 22 most-litigated 17 U.S.C. sections and
      writes `case_treatment` rows (treatment='cited' — a FACT; editorial followed/distinguished
      is NOT asserted, we can't source it freely). Each cited case is its own `type='case'`
      instrument with provenance. Reader Cases tab renders them; case instruments are excluded
      from all corpus counts/rails. (Live: e.g. §107 shows 5 citing opinions.)
   c. **Per-subsection text storage** — replace the reader's display-heuristic paragraph split
      (`_format_body`, reconstructs (a)/(1) paragraphs from a flat blob) with real
      per-subsection versions; gives clean, robust pinpoint text.
   d. **Deep-linkable provision URLs** — `/instrument/{id}/{citation}` (today `?sec=<id>`);
      a hard requirement for the attorney audience (paste a link to a section into a memo).
   e. **Comparative matrix** — point `matrix_cells.source_version` at a provision-scoped
      version so a cell's pinpoint is a real section; human-gated (draft → sign-off → publish).

**3. Tier-3 metadata index** — ~170 more jurisdictions from WIPO Lex, link-only, "not
   maintained" (instrument identity + source_url, no full text). Completes the world map.

**4. Ops / product decisions** — own venv vs borrowing `~/Julie/ai-law-portal/.venv`; hosting
   (local vs Render); copyright-only vs IP-wide (patent/trademark/trade-secret would need a
   body-of-law row in the top nav).

### Reference notes for the ingest fan-out (kept from the Tier-2 waves)
- **`_common.py`** (`ef8ecdc`): a new ingest = `parse()`→`RecordSet` + an INSTRUMENT dict + a
  thin `main()` calling `run_ingest`. Copy `ingest_de_urhg.py` (HTML) or `ingest_uslm.py` (XML).
- **Sourcing gotchas:** WIPO Lex PDFs sit behind CloudFront presigned URLs (grab the signed
  link off the details page; bare paths 301/403). MX had no EN PDF → WIPO text-view HTML. CN's
  CDN 403s scripted fetch → verbatim text via a reader proxy, Wikisource-checked. NL used the
  IViR academic translation. Some ingests read a `pdftotext` .txt via the `--html` flag.

## Decisions still pending (from CLAUDE.md)
- Hosting (local vs Render); own venv vs. borrowing ai-law-portal's.
- **Copyright-only vs IP-wide** — the product name says IP, the corpus is copyright. If patent
  (Title 35) / trademark (Lanham) / trade secret (DTSA) are coming, the top nav needs a
  body-of-law row above the material-type row. Deliberately unresolved.
- Recitals-as-provisions: RESOLVED and shipped (kind='recital', role='recital'). Sub-call
  still open: whether CDPA consequential-amendment/repeal schedules (Sch 7/8) are operative-here.
