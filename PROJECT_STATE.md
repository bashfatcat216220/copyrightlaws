# Copyright Corpus — PROJECT_STATE

> Status comes from THIS file, read fresh. Do not answer "where are we" from memory.

_Last updated: 2026-08-18._

> **Reader UI: instrument-index number-gutter width fix — COMMITTED to local `main`, 2026-08-18 (`e836a0d`).**
> Follow-up to a misaligned-column look on a flat treaty (WPPT): it lists `Article 12`-style items alongside
> `Agreed Statement concerning Articles …` recital labels (~59 chars) in the same index grid. `numw` sized the
> number gutter to the WIDEST label, so it ballooned to ~60ch and shoved every article title to the middle of
> the row. Fix (`src/app.py` `_chapter_index`): `numw` now sizes to SHORT numeric labels only (`len <= 16`) and
> is capped at 16ch; long-label items render as full-width title rows (`.secitem.titlerow`, `templates/instrument.html`)
> instead of overflowing the gutter. **Front-end only — no DB/corpus/schema/version/sha writes; monitor untouched.**
> Chaptered instruments unchanged (CDPA `numw` 8, EU 10). Local `main` only — NOT pushed.

> **CDPA sub-paragraph in-place repeals — surfaced with source notices, LOADED to BOTH DBs, 2026-08-18 (`05d37aa`).**
> Follow-up to a user report of an inline "wall of dots" in s.205B(1) ("cc . . . . d"). Root cause: a sub-paragraph
> repealed IN PLACE (s.205B(1)(cc), s.9(2)(c), Sch. 2 para. 3A, …) prints in legislation.gov.uk's consolidated text
> as a bare dotted leader while the real repeal notice is keyed to the sub-item's `<CommentaryRef>` ("S. 205B(1)(cc)
> repealed (31.7.2017) by Digital Economy Act 2017 (c. 30), s. 34(2)(a)(iii); S.I. 2017/765"). The ingest kept the
> dots but dropped the note → ~70 sub-items across ~50 sections rendered as dot-walls with no citation/date. Fix is
> **metadata-only / monitor-safe** (the section body — which is point-in-time monitored — keeps its VERBATIM dots,
> rule 7 / prime rule 1): `ingest_clml` now sets `status='repealed'` + the keyed notice in `heading` on the sub-item
> row (durable); the reader (`_annotate_repealed_subitems`, label-driven → handles cc/3/3A) splices the notice in
> place of the dots at render, and a redline span that is only a dotted leader collapses to a muted `[repealed]`.
> Migration `006_cdpa_subitem_repeals.py` applied to BOTH DBs: **72 sub-items → repealed (70 with a notice, 2
> verbatim-dots only — Sch. 4 para. 37(1)/48(1)); CDPA repealed 61→133; versions/sha/alerts byte-identical**. Verified:
> change monitor **A/B-identical with vs without the migration (0 alerts attributable)**; reader shows the notice on
> s.205B/s.9/s.31A with **0 dot-walls**; pytest 6/6. Local `main` only — NOT pushed. **Pre-existing, unrelated:** the
> monitor would fire **146 uncaught alerts** on corpus.db from earlier loads (proven independent of this change) — a
> separate cleanup, deliberately NOT run here.

> **Reader UI: in-place (PJAX) navigation — COMMITTED to local `main`, 2026-08-18 (`3af9629`).**
> Resumed an interrupted change (machine died mid-session 2026-08-17) found as the sole uncommitted
> file, `templates/base.html`. The bottom-of-page script now swaps `<main>` in place via `fetch` for
> internal link clicks and same-origin GET forms (top search) instead of full page reloads — no white
> flash between pages. Left-rail scroll is preserved with a per-INSTRUMENT key (section-to-section no
> longer resets it); breadcrumb, corpus counts, and active-nav highlight are synced from the fetched
> document; Back/Forward restore scroll via manual `scrollRestoration` + `popstate`. Falls back to a
> normal full-page load when fetch/History/DOMParser are unavailable or on any error. **Front-end only —
> no DB/corpus/schema writes.** Verified in headless Chromium over CDP, **9/9**: link click + search-form
> submit swap in place (a `window` marker survives = no reload), URL + `<main>` + breadcrumb update, Back
> restores the prior page in-place, no JS exceptions; server logged 200s (only a favicon 404). Local
> `main` only — NOT pushed.

> **CDPA repealed-tombstone + dotted-heading fix — LOADED to BOTH DBs, 2026-08-17 (2 fable agents + orchestrator).**
> Follow-up to a user report of a "wall of dots" in the CDPA reader sidebar. Two root causes, both from
> legislation.gov.uk's dotted-leader repeal convention (verified against `spike/artifacts/cdpa.xml`, rule 9):
> (1) **32 fully-repealed provisions** whose entire body is a dotted leader (`5 . . . .`) were mislabeled
> `status='in_force'` — `ingest_clml` never read `Status="Repealed"` nor the pure-dotted `<Text>`; (2) **6
> repealed sections** (s.265/268/282/283/284/300) stored the dotted "no heading" marker in `heading` while the
> real repeal notice sat in the body, so the rail railed the dots. Fixes: `status='repealed'` on the 32
> (migration `004_cdpa_repealed_tombstones.py` + durable `ingest_clml.is_tombstone`); `heading`→NULL on the 6
> (migration `005_cdpa_dotted_headings.py` + durable `ingest_clml._heading`); rail now shows a muted `[Repealed]`
> ONLY for dotted-leader tombstones while PRESERVING informative repeal-notice previews (`_fill_incipits` gated
> on `status='repealed'` AND a dotted body). All metadata-only — **0 version/content/sha writes, alerts still 91,
> monitor untouched (rule 7)**; CDPA repealed **29→61**; pytest 6/6; app on :8021 shows **0 dot-runs**, 30
> `[Repealed]` labels, the 6 sections now rail their repeal notice, BR/FR live incipits intact. Local `main`
> only — NOT pushed. (Canaries s.29/s.72 with embedded dots correctly stayed `in_force`; 4 headings with a
> trailing omitted-words marker, e.g. s.14/68/72, are legitimate verbatim source and kept.)

> **Back-matter additions (2f/2g audit → Waves A+B) — LOADED to BOTH DBs, 2026-08-16.**
> A fresh read-only audit (7 fable agents by jurisdiction group) → `AUDIT-FINDINGS-2026-08-16.md`
> asked two questions across all 32 instruments: (2f) are we holding the authoritative edition, and
> (2g) is every appendix/schedule/annex/addenda/transitional provision captured. **Waves A+B ingested
> the 8 real missing back-matter items** (~+260 provisions; corpus now ~14,359): 37 C.F.R. Part 202
> App. A & B, EU Orphan Works Annex, KR Addenda (부칙), JP Supplementary Provisions (附則), 17 U.S.C.
> 1976-Act Transitional & Supplementary Provisions (Pub. L. 94-553 §§102–115), DE UrhG Annex to §61a
> (also fixed a §143 annex-bleed bug), CA Schedule I + II/III tombstones, AU "The Schedule" (oath).
> All verbatim from retained artifacts, modeled as `kind='schedule'`/`schedule_para`, `role='schedule'`
> (TRIPS-annex precedent — no schema change); existing law byte-identical; pytest 6/6; caveat renders on
> every new page. **THIS IS STILL A FINDING AID, not an authoritative citation — completeness improved,
> authority unchanged (prime rule 2 holds).** Remaining from the audit (NOT done): Wave C (2f relabels
> CA/AU→official, UK→consolidated + honesty fixes), Wave D (authentic-text ingests: InfoSoc authentic
> articles, Term 2011/77, 37 CFR GPO baseline), Wave E (LOW cleanups + footnote-bleed trims + reader-rail
> surfacing so single-block schedules like 37 CFR App. A / CA Schedule I appear in the rail, not only
> via search/deep-link). Real bug logged: UK CDPA `has_unapplied_effects` never set (SI 2026/103).

> **Waves C + D + E — COMPLETE & LOADED to BOTH DBs, 2026-08-16 (3 fable agents, worktree-isolated).**
> The three remaining 2f/2g audit waves ran as isolated fable agents (each validated on a sqlite-backup
> clone; central load gated + applied by the orchestrator; **Bing approved the CA/AU/UK authority relabels**
> at the gate). Merged to `main` locally (commits `4f25ad6` C / `7a03b3d` D / `6ae60f8` E + merges) — **NOT
> pushed**. Corpus now **14,362 provisions · 6,776 versions · 91 alerts** (monitor NOT run — all additions
> are cross-manifestation/back-matter, CLAUDE rule 6). Integrity clean (0 dup citations, 0 multi-current,
> 0 blank operative bodies, 0 junk, FK + integrity_check ok); pytest 6/6; app re-verified on :8021 (14 pages
> 200, caveat renders). Both DBs at parity.
> - **Wave C** (metadata/honesty + the real bug): CA→`official`, AU→`official`, UK CDPA→`consolidated`
>   (metadata-only, no CDPA re-ingest); 37 C.F.R. 11 `[Reserved]` provisions → `status='reserved'` (new
>   status added via migration `003_wave_c.py` rebuilding the CHECK) + title → "Parts 200–235"; NL ~2012 /
>   IT ~2003 vintage caveats + IN instrument note (app-level). **THE BUG FIXED:** `ingest_clml.py` now parses
>   `ukm:UnappliedEffects` — found **two** live `RequiresApplied` effects (SI 2026/103 art.4(1)→Pt II; TCE
>   Act 2007 Sch 23→repeal of Sch 3 para 17) → `has_unapplied_effects=1` on 76/1597 current versions; UI
>   surfaces a "not fully up to date" flag. Durable in the ingest (self-clearing on future refresh).
> - **Wave D** (authentic-text ingests, real new law): InfoSoc +15 authentic original articles (pit
>   2001-06-22, `is_authentic=1`, additive — consolidated current + recitals untouched); Term Art 10a
>   authentic insertion from Dir 2011/77 (pit 2011-10-11; sha256 matches the consolidation — clean
>   cross-manifestation proof); 37 C.F.R. +211 GPO annual-baseline versions (pit 2025-07-01, official
>   edition, alongside the eCFR working text); `amendments` table populated (+3 provenance rows, monitor
>   NOT fed). **Refused to fabricate** the full amended-state text for InfoSoc Arts 5/12 & Term Arts 1/3/10
>   (amending acts quote only replaced points → recorded as `amendments` rows, not originated text — prime
>   rule 1). New artifacts retained in `spike/artifacts/` (GPO CFR XML, Dir 2011/77 & 2017/1564 OJ HTML).
> - **Wave E** (LOW cleanups + reader surfacing): EU codification annexes 21/23/24 (+6 `schedule`
>   provisions); ES RDL 1/1996 wrapper (+4: Single Article / Single Repeal / Single Final); CDPA Schedule 8
>   repeals table attached (4,898 chars, targeted backfill — no full CDPA re-ingest, rule 7); footnote-bleed
>   trims (Berne App. Art VI 2,377→1,037; Rome Art 34; WCT Art 25; WPPT Art 33 — apparatus only, treaty text
>   intact, all in-place); JP Chapter VIII sort fixed (`_jp_ordinal`: 119,120,120-2,121,121-2,122,122-2,123,124);
>   View-1 "Schedules" group added to `_chapter_index`; WCT/WPPT agreed-statement dedupe (−7 dup rows → 9/10).
>
> **Still pending (NOT done — carry forward):** (1) **SG relabel** — held; needs a human to open the SSO page
> (sso.agc.gov.sg) and read its authority statement (scripted fetch 403s). (2) **Documented-only, no change**:
> `is_authentic=1` on translations vs `is_official_language=0` (schema-semantics call for Bing); the empty EU
> `amendments` table is now populated (D). (3) Cosmetic: reserved/no-current-version provisions spuriously show
> the "not authentic" flag (NULL falsy-inverted); CDPA View-1 Schedules grid lacks per-schedule sub-headers.
> (4) **Not pushed to origin** — local `main` is ahead by the 3 waves + merges.

> **Migration 002 (legal-authority axis) — APPLIED & backfilled (2026-08-14, last commit `68cb6e0`).
> Per-instrument `authority` (binding|persuasive|precedent, set by PROCESS not publisher/`type`),
> `positive_law`, `source_edition`, `court_level`. Backfilled on BOTH DBs: 32 non-case instruments
> = `binding` (0 NULL), cases = `precedent`. Attorney-driven (Copyright Office makes both binding
> 37 C.F.R. rules AND non-binding guidance). See CLAUDE.md prime rule 3a.

## 2f/2g audit waves C, D, E — ✅ DONE (2026-08-16, see the completion banner above)

_All three waves are LOADED to both DBs (details in the banner at the top). The per-item breakdown below
is retained as the RECORD of what was done — it is no longer a backlog. Only the "Still pending" items in
the completion banner remain (SG relabel, the documented-only schema-semantics call, two cosmetic items,
and the push). Source of detail: `AUDIT-FINDINGS-2026-08-16.md`._

### Wave C — 2f relabels + honesty fixes (metadata only, NO new law text)
- **CA (id 6)** `source_edition` finding_aid → **official** (Justice Laws is official for evidentiary
  purposes since 2009-06-01).
- **AU (id 7)** finding_aid → **official** (Federal Register of Legislation is the authoritative register,
  Legislation Act 2003 ss 15B/15ZA; corpus already holds the current compilation).
- **UK CDPA (id 2)** finding_aid → **consolidated** (TNA official revised edition). Do NOT re-ingest
  (it carries point-in-time versions + fired alerts) — metadata-only update.
- **IN (id 9)** keep finding_aid; add an instrument note ("authoritative text = Gazette of India;
  India Code is an as-is departmental consolidation; indiacode.nic.in blocks scripted refresh").
- **SG (id 10)** relabel → official **PENDING manual check** (SSO 403s scripted fetch — can't verify
  the authority statement without a human opening the page).
- **NL (id 8)** add source-vintage caveat **~2012**; **IT (id 18)** add caveat **~2003** (extend
  `SOURCE_VINTAGE` in `src/app.py`; FR ~2006 and ES ~2012 already present).
- **37 C.F.R. (id 19)** reserved sections carry `status='in_force'` → should be `unknown` (or add a
  `reserved` status via migration); fix instrument title "Parts 201–212" → "Parts 200–235".
- **REAL BUG — UK CDPA `has_unapplied_effects` never set (prime rule 3).** The current CLML snapshot
  carries a live `RequiresApplied="true"` effect (SI 2026/103, Pt 2) but all 1,597 versions read 0;
  `ingest_clml.py` never parses the `ukm` effects metadata. Wire it in + flag affected Pt 2 versions.
- (LOW) `is_authentic=1` on all 10 translations contradicts `is_official_language=0` — schema-semantics
  review. EU `amendments` table is empty though ≥3 amendment events exist — populate as provenance
  metadata only (do NOT feed the change monitor — cross-manifestation re-base is not an amendment).

### Wave D — authentic-text ingests (real new law)
- **EU InfoSoc 2001/29 (id 3):** we hold only the editorial consolidation as enacting text — the ONLY
  `is_authentic=1` rows are its 61 recitals. Ingest the **authentic original articles** (+ the 2
  amendment layers: 2017/1564, 2019/790). Authentic original text is already on disk
  (`spike/artifacts/infosoc_oj.html`, `infosoc_act.xml`).
- **EU Term 2006/116 (id 23):** Art 10a exists only as consolidation text → ingest amending act
  **2011/77** (authentic OJ L 265) for the authentic layer, or at minimum an amendments row.
- **37 C.F.R. (id 19):** add an **additive official GPO annual CFR baseline** as a pinned point-in-time
  version (GPO bulk XML `https://www.govinfo.gov/bulkdata/CFR/2025/title-37/CFR-2025-title37-vol1.xml`,
  fetch verified) — keep the eCFR as the current working text; label stays honest.
- (LOW) 17 U.S.C. (id 1): fix the dead `bulkdata/USCODE` URL in `src/connectors/govinfo_us.py`;
  optionally cross-ref the GPO `USCODE-<yr>-title17` package as an authoritative manifestation.

### Wave E — LOW cleanups + data-quality + reader surfacing
- **EU codification annexes:** Software 2009/24 (id 21), Term 2006/116 (id 23), Rental 2006/115 (id 24)
  each have Annex I/II (repealed-directive list + transposition dates + correlation table) — ingest
  like Orphan Works (kind='schedule'). Non-substantive apparatus but referenced by the final articles.
- **ES TRLPI (id 15):** capture the RDL 1/1996 wrapper (Single Article / **Single Repeal** (operative
  derogatoria) / Single Final) or document its exclusion in `ingest_es.py`.
- **UK CDPA Schedule 8 (id 2):** content-less stub — attach the repeals-table text OR add a documented
  exclusion note (currently silent).
- **Footnote-bleed trims:** Berne Appendix Art VI (id 4) swallowed ~1,350 chars of WIPO editorial
  footnotes incl. quoted 1896-treaty text (MED — re-segment before the `<hr>`); Rome Art 34 (id 29),
  WCT Art 25 (id 27), WPPT Art 33 (id 28) each swallowed a small "Source: WIPO" endnote (LOW).
- **JP (id 14) Chapter VIII sort defect:** Arts 123/124 sort before 120-2/121-2/122-2 (sort-key fix).
- **Reader surfacing (View 1):** the chapter-INDEX landing page (e.g. `/instrument/6`) has no
  "Schedules" group — top-level childless schedules (CA Schedule I/II/III) surface in the reader rail +
  search + deep-link but not the default chapter list. Add a Schedules group to `_chapter_index`
  (`_CONTAINER_KINDS` currently excludes schedules). [The reader-RAIL surfacing (View 2) is already done.]
- (LOW) Optionally dedupe/link the repeated WCT/WPPT agreed-statement recital rows.

## Where we are (one breath)

> **Full 18-jurisdiction validity audit (6 fable agents, 2026-08-14) → `AUDIT-FINDINGS-2026-08-14.md`
> — REMEDIATION COMPLETE (waves 1–6, all pushed).** Wave 1: 100 fabricated treaty pinpoints purged +
> sequential-numbering parser fix. Wave 2: CDPA repeal notices + cross-cutting `status='repealed'` (87
> provisions, rust "Repealed" tombstone). Wave 3: SG ghost dupes / CA amending-act appendix / AU s.249
> excised. Wave 4: PDF footnote purges (ES Art.28, IN, NL) + ES bis/ter sort fix. Wave 5 (5 parallel
> fix-agents): IT Art.182/182bis/175-179 untangle + Art.101, ES back-matter split, treaty Agreed
> Statements + TRIPS Annex, CDPA Schedule 5A (surgical — alerts still 91), MX transitional. Wave 6:
> CN citations, KR `¡?`, eCFR ranges, FR/ES source-vintage UI flags. Final regression: 0 fabricated
> pinpoints, 0 junk, 0 blank bodies, 0 duplicate citations; pytest 6/6. Ingest-correctness rules are
> codified in `CLAUDE.md` ("Ingest correctness rules"). Corpus now **32 instruments · ~14,099 provisions
> · ~6,333 versions**.

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
- **InfoSoc sub-article nodes — RESOLVED (2026-08-14).** Re-based the WHOLE InfoSoc instrument
  from the 2019-06-06 Formex CONS.ACT (fetched from CELLAR with `Accept: application/xml;type=fmx4`
  → `spike/artifacts/infosoc_fmx_20190606.xml`), so all 96 article/paragraph/clause current versions
  now carry `point_in_time=2019-06-06` from ONE manifestation (superseding the article-level ELI-HTML
  stopgap in place). +3 real new points **Art. 12(4)(e)–(g)** (DSM-added) → 161 provisions. Recitals
  (61) untouched as authentic-original; 2017 versions retained as `is_current=0`; monitor not run.
  Required a small `ingest_formex._store_version` change (supersede-in-place when a row already
  occupies the same `(provision, point_in_time, language)` UNIQUE slot). Term/Database have no
  sub-article nodes (article-level), so nothing to do there.
- **EU monitor must skip cross-manifestation transitions** — the original-act → consolidated
  version step is a manifestation re-base, not an amendment; the daily cron only monitors UK+US so
  this is moot today, but if the monitor is ever pointed at EU it would fire formatting-noise alerts
  on that transition. Gate it (e.g. only diff same-`version_label` or same-source transitions).

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

4. **EU consolidation currency — FIXED (2026-08-14).** Grounded the audit's flag against live
   EUR-Lex: of the 8 EU directives, exactly **3** were materially out of date (confirmed by the
   consolidated-version list on each act's EUR-Lex ALL page) — the other 5 (DSM, Software, Rental,
   Orphan, Enforcement) have no post-adoption amendment, so their authentic original text IS current
   and was left as authentic=1 (authentic beats an editorial consolidation when there's no gap).
   Re-based the 3 onto their **latest consolidated version** via `src/store/ingest_eu_consolidated.py`
   (new; parses the modern EUR-Lex **ELI consolidated HTML** — `eli-subdivision`/`title-article-norm`/
   `no-parag`, strips ►M/▼M/◄ amendment markers), loaded as **is_authentic=0, is_consolidated=1**,
   `point_in_time` = the consolidation date, behind the "Consolidated — not authentic" banner:
   - **Term 2006/116 → 2011-10-31** (Dir. 2011/77 term extension). The important one: the corpus
     had the pre-2011 term rules — Art. 3 now carries the **70-year** phonogram term (old text had
     zero "70 years"; new has 3), and the **inserted Article 10a** was created (a genuinely new
     provision). 9 articles re-based.
   - **Database 96/9 → 2019-06-06** (Dir. (EU) 2019/790 amendment). 14 articles re-based.
   - **InfoSoc 2001/29 → 2019-06-06** (refresh from 2017-10-10). 13 articles re-based.
   Discipline: consolidated ELI HTML drops recitals, so only ARTICLES were re-based — **recitals
   keep their authentic-original version** (untouched). Because diffing consolidated-ELI text against
   the original-act extraction is cross-source formatting noise, the change monitor was **NOT** run
   for this (it's a manifestation re-base, not an observed amendment — firing "changed" alerts would
   misrepresent reformatting as a legal change). No-clobber: existing article provisions got a NEW
   version only; their row/parent/children were never rewritten. Also fixed a source **mislabel**:
   `ingest_eu_directive` had tagged original acts `is_consolidated=1` (self-contradictory) → now 0,
   and 392 existing original-act versions were corrected.

## Page / rendering audit (2026-08-14)

Swept all 32 instruments + every page type (home, jurisdiction ×18, reader, chapter index,
`/alerts`, `/search`) for "data's-there-but-renders-wrong" bugs. Final sweep: **0 junk hits,
0 blank-body, 0 duplicate citations, all 32 instrument pages + 18 jurisdiction pages HTTP 200,
a textful reader per jurisdiction all non-empty.** Bugs found and FIXED (both DBs):

- **Heading-less lists looked empty (BR, FR)** — Brazilian/French statutes number articles but
  don't title them, so the index/rail showed bare numbers. Now show a muted-italic **incipit**
  (the provision's own opening ~90 chars) when there's no source heading — never an invented
  title. Headed laws (US/DE/UK/EU) unchanged. (`_incipit`/`_fill_incipits` in `app.py`.)
- **EU consolidated footer-JS + annex bleed (regression from the currency fix)** — the last
  article of Term/Database swallowed the page-footer `<script>` jQuery and the ANNEX, because
  `ingest_eu_consolidated._strip` stripped script *tags* but kept their inner JS, and the last
  article's region ran to end-of-page. Fixed: strip `<script>/<style>` blocks before tags, and
  end-cap each article region at the annex/footnote/script boundary (`_END_CAP`). Re-ingested;
  Term Art. 14 / Database Art. 17 now end cleanly ("…addressed to the Member States."). Added
  supersede-in-place to that ingest so re-runs don't collide on the pit UNIQUE slot.
- **InfoSoc reverted by a `--which all` re-run** — re-running the consolidated ingest overwrote
  the agent's Formex InfoSoc articles with ELI-HTML again; restored to the single 2019 Formex
  manifestation (all 96 art/para/clause current versions back to one source, 0 junk).
- **JP showed 20 empty "Section" entries** — Japanese acts are chapter > section > article, so
  the `section` rows are containers (3–8 article children each) but were railing as empty
  readable leaves. Fixed at the read layer: a `section` that contains `article` children is
  treated as a container (rails as a group header, not a clickable entry). US/UK sections hold
  subsections, never articles, so they're unaffected — survives a manifest rebuild.
- **KR Art. 142 leaked `<div`** — one Korean article carried a scraped trailing HTML tag.
  Stripped lowercase HTML tags from KR content (1 row); the 77 legitimate `<Amended by Act…>`
  annotations (official Korean-law convention) are preserved and render correctly (escaped).

Confirmed NON-bugs (left as-is, correct): DE repealed sections (labelled "(repealed)"), US
17 U.S.C. / 37 C.F.R. reserved/renumbered brackets, KR `<Amended by…>` annotations.

- **KR Art. 101-6 / 121 repeal notices — RESOLVED (2026-08-14).** Not gaps — the source prints
  them as "Article N Deleted. ⟨by Act No. …⟩" with no `(heading)` and no body, so the KR parser
  (which keyed on `Article N (Heading)`) captured the number but nothing else. Fixed
  `ingest_kr`: when an article has no body, keep the inline remainder of the title line verbatim
  (the source's own repeal notice) as content — no fabricated old text (a repealed provision's
  superseded text is NOT in the KLRI translation; showing the notice is the honest level, same
  as DE's "(repealed)"). Also hardened `_clean` to drop a dangling unclosed tag at end-of-frag
  (this is what had leaked `<div` into Art. 142; a rebuild now reproduces it clean). Re-ingested
  both DBs: the two articles now read "Deleted. ⟨by Act No. …⟩" in the reader and the index.

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
   d. **Deep-linkable provision URLs — DONE (2026-08-15, commits `d222399` + `2e25a03`).** Sections,
      alerts, and chapter-rail links all resolve on stable citation-derived slugs (survive rebuilds).
      Original design note below. `/instrument/{id}/{pinpoint}`
      (today `?sec=<id>`, an internal DB row id that ROTS across a manifest rebuild); a hard
      requirement for the attorney audience (paste a link to a section into a memo). Design:
      resolve on a stable case-preserving PINPOINT SLUG derived from the `citation`
      (`UNIQUE(instrument_id,citation)`) — e.g. `17 U.S.C. § 107` → `/instrument/1/s-107`,
      `Directive 2001/29 Art. 1(2)(a)` → `.../art-1-2-a`. Verified collision-free across all
      14,099 provisions (case-preserving distinguishes `(i)`/`(I)`; `#N` uniquifier encoded as
      `-no-N`). `?sec=` kept as a backward-compatible fallback.
   e. **Comparative matrix** — point `matrix_cells.source_version` at a provision-scoped
      version so a cell's pinpoint is a real section; human-gated (draft → sign-off → publish).

**2f. Ingest the authoritative official editions (NEW — 2026-08-15).** The `source_edition`
   axis (migration 002) records that only 7/32 instruments are `official`; 7 are `finding_aid`
   (eCFR & OLRC-online — government finding aids, NOT the official legal edition), plus
   consolidated/original_act/translation. We MARK the gap but do not yet HOLD the official
   editions. This item = ingest the controlling texts where they differ from our finding-aid
   source: GPO annual **CFR** + **Federal Register** (vs eCFR), the printed **U.S. Code** /
   Statutes at Large (vs OLRC-online), and EU **authentic OJ** text (vs consolidated). Keep the
   `source_edition` label honest per source; prime rule 2 (finding aid, not authority) still
   holds — this narrows the gap, it does not make the tool a citation.

**2g. Systematic appendix / schedule / annex sweep — AUDIT DONE + Waves A+B LOADED (2026-08-16).**
   See the top banner + `AUDIT-FINDINGS-2026-08-16.md`. The 8 HIGH+MED missing back-matter items are
   ingested to both DBs. Remaining: Wave E LOW items (EU codification annexes 21/23/24, ES RDL wrapper,
   CDPA Sch 8 note) + the reader-rail surfacing tweak. Original scope note:
   **2g. Systematic appendix / schedule / annex sweep (NEW — 2026-08-15).** Appendices & annexes
   are currently captured only where the 2026-08-14 audit happened to touch them (Berne Appendix
   loaded; TRIPS Annex loaded as a `schedule` row; CDPA 349 schedule paras). There is no
   corpus-wide check that every instrument's back-matter (schedules, annexes, appendices,
   transitional provisions) is either ingested as operative provisions or deliberately excluded
   with a noted reason. This item = sweep all 32 instruments for un-ingested back-matter, per the
   ingest-correctness rules (segmentation stops at boundaries; back-matter that is operative law —
   e.g. UK Schedules — becomes provisions; amending-act "RELATED PROVISIONS" appendices do not).

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
