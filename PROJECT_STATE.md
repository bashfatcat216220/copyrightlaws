# Copyright Corpus — PROJECT_STATE

> Status comes from THIS file, read fresh. Do not answer "where are we" from memory.

_Last updated: 2026-08-12._

## Where we are (one breath)

**Phase 0 is COMPLETE.** The KM IP — Statute Browser design is live over a section-level
`provisions` model, with real copyright law from all four Tier-1 source shapes ingested,
searchable, and cited at the provision level. Migration applied to `corpus.db`; branch pushed.

- **Corpus (live in `corpus.db`):** 4 instruments · **8,734 provisions** · **1,145 provision
  versions**, every version SHA-256'd with `source_url` + `retrieved_at`.
  | Jur | Instrument | Shape | Loaded |
  |---|---|---|---|
  | US | 17 U.S.C. | USLM XML | 15 chapters · 153 sections (nests 4 deep) |
  | UK | CDPA 1988 | CLML XML | 436 Body sections + 349 schedule paragraphs |
  | EU | Directive 2001/29 (InfoSoc) | Formex XML + OJ HTML | 4 chapters · 15 articles + **61 recitals** |
  | INT | Berne Convention (Paris 1971) | WIPO Lex HTML | 53 articles (bis/ter + roman Appendix) + 250 paras |
- **Live server:** `uvicorn src.app:app` on `corpus.db`, http://127.0.0.1:8021 — the section
  reader shows real US/UK/EU/INT law; search is grounded (`fair use`→§107, `parody`→Art.5(3)(k)).
- **Git:** `main` pushed to `origin` (github.com/bashfatcat216220/copyrightlaws.git); latest
  `0b6f06c`. `pytest` 6/6.
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

## Next steps — roadmap & recommendation

Per CLAUDE.md's phased roadmap; Phase 0 done, now branching into corpus expansion + monitoring.

**▶ Recommended next: Phase 2 — change monitoring.** This is where the tool earns its keep
(and where partners start caring per CLAUDE.md), and the schema is already built for it: every
provision version carries `content_sha256`. Build `src/monitor/`: re-fetch a source → parse →
diff per-provision sha → write an `alerts` row (old_version→new_version) → render a redline
in the reader / a digest. Pairs naturally with building the first real **connector**
(`discover(since)`/`fetch`) so re-fetch is automated rather than manual artifact-swapping.

**Also queued (any order):**
- **Phase 1 — finish Tier-1 corpus:** 37 C.F.R. (eCFR, keyless), EU **DSM 2019/790** + the
  other copyright directives (reuse `ingest_formex.py`), and the remaining core treaties
  (TRIPS/WCT/WPPT/Rome/Beijing/Marrakesh via WIPO — reuse the Berne HTML pattern).
- **Cases tab → real data:** populate `case_treatment` (per-provision decisions,
  followed/distinguished/criticized) so the practice panel's second tab lights up. Needs a
  case source + the treatment-colour vocabulary (rust = adverse) already speced.
- **Deep-linkable provision URLs** (`/instrument/{id}/{citation}`) — a hard requirement for
  the attorney audience; today it's `?sec=<id>`.
- **Comparative matrix (Phase 4 groundwork):** point `matrix_cells.source_version` at a
  provision-scoped version so a cell's pinpoint is a real section; keep it human-gated.
- **Own venv + hosting decision** (still borrowing `~/Julie/ai-law-portal/.venv`; local vs Render).

## Decisions still pending (from CLAUDE.md)
- Hosting (local vs Render); own venv vs. borrowing ai-law-portal's.
- **Copyright-only vs IP-wide** — the product name says IP, the corpus is copyright. If patent
  (Title 35) / trademark (Lanham) / trade secret (DTSA) are coming, the top nav needs a
  body-of-law row above the material-type row. Deliberately unresolved.
- Recitals-as-provisions: RESOLVED and shipped (kind='recital', role='recital'). Sub-call
  still open: whether CDPA consequential-amendment/repeal schedules (Sch 7/8) are operative-here.
