# Copyright Corpus — PROJECT_STATE

> Status comes from THIS file, read fresh. Do not answer "where are we" from memory.

_Last updated: 2026-08-12._

## Where we are

Pre-Phase-0 scaffold, now carrying the **KM IP — Statute Browser** design system.

- **Location moved**: the repo lives at `~/TIngey/copyright-corpus` (reorganized from
  `~/copyright-corpus` on 2026-08-12). Note: `~/TIngey/copyright-news-site` is a
  SEPARATE, UNRELATED project that merely shares the `TIngey/` parent — do not conflate
  or remix the two. The
  relocated shared venvs are `~/Julie/ai-law-portal/.venv` (has fastapi/uvicorn/jinja2 —
  use this) and `~/Litigation/multi-agent-document-review/.venv` (no web deps).
- **Git**: remote `origin` = https://github.com/bashfatcat216220/copyrightlaws.git,
  branch `main`. **Nothing pushed yet** (holding on the user's instruction).
- **DB**: 18 jurisdictions seeded; **zero** instruments/versions/amendments/etc. No real
  law loaded. Every screen shows honest empty-states — no fake law, per prime rule 1.

## Done this session — UI reskin (ships now)

Rebuilt the web layer to the design handoff's visual system, against the EXISTING
multi-jurisdiction IA (jurisdiction rail → instrument → version). Source of the design:
`~/Downloads/IP Professionals Legal Platform(1).zip` (a Claude-made design handoff;
extracted to `/tmp/ip-design-inspect` for inspection — inspected, not executed).

- `templates/base.html` — full token rewrite: Source Serif 4 (reading) / IBM Plex Sans
  (interface) / IBM Plex Mono (every identifier); five neutrals + Navy (links & current
  position only) + Rust (amendment/expiry/adverse only); **square corners, no shadows, no
  chips/pills**. Dark 52px top bar, 40px breadcrumb with **live** corpus counts (never
  hardcoded), the standing finding-aid caveat on every page, paper-warm jurisdiction rail
  with a rust keyline on the active row.
- `templates/instrument.html` — the design's **three-pane section reader**: reading column
  (max 660px, 16.5px/1.72 serif measure) + provenance (source_url + retrieved_at) + a
  **practice panel with a Cases / History tab bar**. History is backed by `amendments`;
  Cases is an honest empty-state today. The two-tab bar is built NOW so the panel need not
  be re-laid-out when case-treatment lands.
- `templates/{index,jurisdiction,search,matrix}.html` — restyled to the same vocabulary;
  status/flags carried by mono-caps + keyline (chips removed).
- `src/app.py` — `_counts()` + `_ctx(active_nav=…)` for the chrome; instrument route now
  loads `amendments` (joined to the amending instrument's cite/title) and takes `?tab=`.

**What was intentionally NOT copied from the mockup**: its fake statutory prose, fictional
cases, fake citing-decision counts, and the fake "VERIFIED 08 AUG 2026 …" chrome line. The
handoff itself flags all of these as placeholder; our prime rule 1 forbids them.

**Verified**: `pytest` 6/6 green; uvicorn boots; all routes 200 (incl. unknown-jurisdiction
and missing-instrument empty-states); instrument three-pane + both tabs render with no Jinja
errors (synthetic context — the real DB was left empty, no fake law inserted).

## Next — the provisions rebuild (planned, NOT yet built; gate on Bing's review)

The mockup's information architecture is section-level (Title-17 chapter → section reader
with per-section case treatment). Our schema is instrument+version only — no sub-instrument
granularity. Rather than hardcode a Title-17 chapter/section pair, the agreed shape is a
**generic `provisions` table under `instrument`, with `versions` re-pointed to hang off a
provision**, so text can be diffed and cited at section level across every jurisdiction
(a UK section, an EU article, a treaty article — all "provisions").

### Corrected nav hierarchy (do NOT collapse tiers)

The mockup was a **2-level thing inside ONE instrument** (chapter → section). We wrap it in
two tiers above. Keep all four distinct — fusing the jurisdiction rail and the chapter rail
into "one rail that means different things" makes the nav incoherent.

```
Jurisdiction rail        ← our tier, above everything
  └─ Instrument          17 U.S.C., CDPA 1988, InfoSoc …
       └─ Provision d1    = chapters   ← the mockup's "chapter index"
            └─ Provision d2 = sections  ← the mockup's section rail
                 └─ § 203(a)(4) …       addressable; may not be railed
```

### Agreed rebuild sequence (2026-08-12)

Sequence the rebuild BEFORE ingesting real law: today's text would store as one
whole-instrument blob, which does not split into sections retroactively — ingest-first buys
nothing we keep and costs a throwaway whole-document reader + a bad first impression. But do
not design the table blind either.

1. **Parsing spike (DONE 2026-08-12)** — threw three dissimilar shapes at the future schema:
   17 U.S.C. (OLRC USLM, releasepoint 119-102), CDPA 1988 (legislation.gov.uk CLML), and
   InfoSoc 2001/29 (EUR-Lex Formex). Keyless. Script + report + retained artifacts live in
   `spike/` (gitignored, nothing written to `corpus.db`). Re-run: `python spike/parse_spike.py`.
2. **Freeze the `provisions` delta** from what the spike finds → **Bing reviews** → the
   migration lands as its own reviewable step (house rule: risky parses gate on human review).
3. **Re-ingest once** from the retained artifacts into the frozen schema.
4. **Build the section-level reader** — section rail (provision d1/d2), per-provision
   versions/diff, per-provision Cases/History (the tab bar is already in place).

### Spike findings (drive the schema delta — full report in gitignored `spike/out/`)

- **The non-operative axis is QUOTED/AMENDING text, NOT Body-vs-Schedule.** (Correction from
  Claude design — my first cut wrongly skipped Schedules and would have dropped operative law.)
  The only elements that must never be addressable as this instrument's law are those
  reproducing OTHER instruments' words: USLM `quotedContent` (in notes) and CLML
  `BlockAmendment`/`Quotation`. **UK Schedules are operative** (Sch 1 transitional term, Sch 2
  performance permitted acts — a transactional lawyer hits them constantly) → keep as
  `kind='schedule_para'`, a separate numbering class NOT folded into the section sequence.
  Correct counts after this scoping: **153** US sections; **436** UK Body sections **+ 349
  Schedule paragraphs**; **15** EU articles. (Sub-call for Bing: pure consequential-amendment/
  repeal schedules amend other Acts — flag whether those specific ones are operative-here.)
- **Ordinal must be `(sort_int, sort_suffix)`**, not an integer. Real inserted/suffixed
  sections: US 104A/106A/116A/121A; UK 3A…31BA/31BB…50BA…296ZA. Key `(int, suffix_upper)`
  orders `106 < 106A < 107` and `296 < 296ZA`. Verified in the report.
- **Labels are source-given per node** — USLM `section` "§ 203", CLML `P1` "s. 296ZA",
  Formex `ARTICLE` "Article 5". Render the stored label; never a jurisdiction switch.
- **Addressability runs 3–4 deep** — real pinpoints § 104A(d)(2)(A)(i) (US, 4 below) and
  s. 12(5)(a)(i) (UK, 3 below). Emit every cited level as its own node even if the rail
  shows two.
- **Schedules are a SEPARATE provision class** (own paragraph numbering) — model them, don't
  merge into the section sequence.
- **Recitals — resolved (proposed, Bing confirms):** model recitals as **provisions,
  `kind='recital'`, `operative=0`**. CJEU judgments turn on recital language (Recital 31 of
  InfoSoc is cited constantly), so they need stable addressable ids — exactly a provision
  node — but the `operative=0` flag keeps them out of anything that counts or diffs enacted
  law. Consequence, which is a version/provenance decision not a parsing one: the **original
  OJ act (CONSID-tagged) is the STRUCTURAL source** for recitals; the **consolidated
  manifestation** (`is_authentic=0`) is the **current-text source**. This is the first real
  test that `is_authentic` earns its place in the model.
- **EU connector gotcha:** EUR-Lex `legal-content/…/XML` returns a CELLAR *notice* (metadata),
  NOT the act. The Formex act body is the `…fmx4` manifestation (we pulled the consolidated
  one via `publications.europa.eu/resource/celex/…fmx4`). The future EU connector must target
  the manifestation, not the notice.

### Constraints to hold through the rebuild

- **Label comes from source, never inferred.** The reader renders `provision.label` /
  `kind` as stored ("Article 5" vs "§ 203") — never a `if jurisdiction=='EU'` switch. That
  data-drives the one design across jurisdictions.
- **Subsection addressability is a parser risk, not a schema gap.** The schema nests
  arbitrarily (`parent_id`) with a stable natural key (`UNIQUE(instrument_id, citation)`).
  The parser must emit every cited level as its own node (attorneys cite § 203(a)(4)) even
  when the rail only shows two levels. Storage depth ≠ display depth.
- **Ordinal must survive suffixes, insertions, and holes.** A naive integer breaks on
  § 106A (between 106 and 107), § 104A / § 121A, and gaps from repealed sections. The
  spike's real deliverable is the ordering scheme, not just "it parsed."
- **Section facts come from the XML, not memory** (no-fake-law): whether § 601 still
  exists, chapter 6's gaps, § 106A's placement — all discovered from source in the spike.
- **Recitals = a Bing decision.** Whether EU recitals are provisions or metadata is a
  genuine fork; the spike surfaces it with both options costed — it does not decide it.

### Still open (put back to Claude design)

Rail display depth. Mockup rails two levels (chapter→section); attorneys cite four
(§ 203(a)(4)). We store four, rail two, deep-link to the subsection — but whether a long
section's rail should expand to subsections is unspecified by the mockup.

### Proposed schema delta (draft — for review before migration)

```
provisions
  id              INTEGER PK
  instrument_id   INTEGER NOT NULL REFERENCES instruments(id)
  parent_id       INTEGER REFERENCES provisions(id)   -- chapter→section→subsection tree
  sort_int        INTEGER NOT NULL                     -- ordinal part 1: integer of the number
  sort_suffix     TEXT NOT NULL DEFAULT '' COLLATE BINARY  -- ordinal part 2: 'A','ZA',… PIN the
                         -- collation — 296Z<296ZA<296ZEA sorts right by ACCIDENT under default
                         -- lexical order; a locale-aware collation on the column would break it.
  label           TEXT NOT NULL                        -- source-given: '§ 203','s. 296ZA','Article 5'
  heading         TEXT                                 -- section/article title (from source)
  kind            TEXT   -- source-derived structural tag: 'chapter'|'section'|'subsection'|
                         --   'article'|'paragraph'|'part'|'schedule'|'schedule_para'|'recital'
  role            TEXT NOT NULL DEFAULT 'enacting'     -- retrieval semantics (replaces a bare
                         --   operative boolean — too coarse; see delta note):
                         --   'enacting'  → operative law (counted, diffed)
                         --   'schedule'  → operative law in a schedule (counted, diffed)
                         --   'recital'   → interpretive; addressable + SEARCHABLE, never counted/diffed
                         --   'quoted'    → other instruments' words; never surfaced as this text
  citation        TEXT   -- stable pinpoint & natural re-ingest key, e.g. '17 U.S.C. § 203(a)(4)'
  status          TEXT DEFAULT 'in_force'
  UNIQUE (instrument_id, citation)
  -- sort within parent = ORDER BY (sort_int, sort_suffix COLLATE BINARY).
  -- TEST FIXTURE (nastiest series found): US 104/104A/106/106A/107; UK 31B/31BA/31BB,
  -- 296Z/296ZA/296ZEA — assert ordering holds under the pinned collation.
  -- NOTE for review: `role` replaces the earlier `operative` boolean because a boolean
  -- collapses recital (searchable interpretive authority) and quoted-amendment text (never
  -- surfaced) into one flag. Bing to confirm the enum at sign-off.

versions  (CHANGE: text hangs off a provision, not the whole instrument)
  + provision_id  INTEGER REFERENCES provisions(id)    -- NULL = whole-instrument version
  -- content_sha256 stays the per-provision change key → section-level diff & alerts

case_treatment  (NEW — powers the Cases tab; today it is an honest empty-state)
  id              INTEGER PK
  provision_id    INTEGER NOT NULL REFERENCES provisions(id)
  case_instrument INTEGER REFERENCES instruments(id)   -- the deciding case (type='case')
  treatment       TEXT   -- 'followed' | 'cited' | 'distinguished' | 'criticized'
  holding         TEXT   -- grounded to a fetched source; NULL if not fetched
  source_url      TEXT NOT NULL
  retrieved_at    TEXT NOT NULL
```

Design notes carried from this session:
- Treatment colour is the only semantic colour in the practice panel: followed/cited →
  ink/label, distinguished/criticized → **rust** (adverse). No badges — mono caps + keyline.
- `matrix_cells.source_version` should later point at a provision-scoped version so a
  matrix cell's pinpoint is a real section, not a whole instrument.
- Deep-linkable URLs per provision (`/instrument/{id}/{citation}`) are a hard requirement
  for the attorney audience — model as URL state when the reader goes section-level.

**This is a data-model change → it lands as an isolated, reviewable migration BEFORE any
reader/monitor logic depends on it (prime rule: risky seeds gate on human review).** Do not
build the provisions reader until Bing signs off on this delta.

**Migration DRAFTED (not applied):** `db/migrations/001_provisions_rebuild.sql` — provisions +
case_treatment tables, `versions.provision_id`, ordinal collation, role CHECK, FTS over
provision text. Review artifact only; do NOT run against `corpus.db` until sign-off.

**Ingest DRAFTED (not applied to corpus):** `src/store/ingest_uslm.py` — provision-aware,
re-runnable 17 U.S.C. ingest. Refuses to write `corpus.db` without `--allow-corpus`; requires
migration 001. Validated on a scratch DB (schema+migration+seed, then ingest): **3,118
provisions** (15 chapters … 153 sections … down to subitem), **153 section versions**
(sha256'd), provision-FTS grounded (`fair use`→§107, `termination`→§203). **Idempotent** —
a second run inserts 0 new versions. Deep pinpoint `§ 104A(d)(2)(A)(i)` resolves; `§ 106A`
sorts between `§ 106` and `§ 107`.

**Two schema fixes the USLM ingest CAUGHT (folded into migration 001) — why we draft the
ingest before freezing:**
1. `versions` UNIQUE was `(instrument_id, point_in_time, language)` — collides once many
   provisions of one instrument share a point-in-time. Rebuilt to include `provision_id`.
2. `kind` CHECK was missing USLM's deep levels (`subclause`/`item`/`subitem`/`subpart`).
   Extended. (17 U.S.C. nests 4 below the section.)

**CDPA ingest DRAFTED:** `src/store/ingest_clml.py` — CLML, second source shape, exercises
the Body-vs-Schedule role split. Validated on the demo DB: **436 Body sections** (role
`enacting`) **+ 349 Schedule paragraphs** (role `schedule`), `s. 296 < 296A < 296B < 296ZA`
ordering, FTS `fair dealing`→ s.29/s.30. Idempotent (re-run: 0 new). What the CLML ingest
caught: (a) CDPA **Schedule 1 contains `Part` elements** — the Part/Chapter handler had to
PRESERVE schedule context or schedule paragraphs get misclassified as Body sections and
collide with real section numbers (corrupted `s. 1`); (b) some schedule-paragraph citations
still collide (schedule sub-structure the pinpoint doesn't yet capture) — currently guarded
by a deterministic `#n` suffix; **real fix later = full schedule-part pinpointing in the
CLML citation.**

## Source plan — how the corpus gets added

Retrieval-first, provisions-aware: a connector `discover(since)`→refs + `fetch(ref)`→official
text+provenance; the `store/` layer parses each fetch into a provision tree (per the spike's
rules) and versions the text per provision. **Endpoints below are PROVEN in the spike** — the
exact URLs that returned real law, keyless, so they don't get re-discovered:

| Source | Fetch (proven keyless) | XML shape | Change feed | Notes |
|---|---|---|---|---|
| **US 17 U.S.C.** | `uscode.house.gov/download/releasepoints/us/pl/<cong>/<pt>/xml_usc17@<cong>-<pt>.zip` → `usc17.xml` | USLM | OLRC release points (poll the download page) | skip `note`/`quotedContent`; §§ nest 4 deep |
| **UK CDPA 1988** | `legislation.gov.uk/ukpga/1988/48/data.xml` | CLML | Publication Log Atom (free) | Body §§ + Schedule paras (separate class); skip `BlockAmendment` |
| **EU InfoSoc / DSM** | `publications.europa.eu/resource/celex/<CELEX>.ENG.fmx4` (the **fmx4 manifestation**) | Formex | CELLAR | **NOT** `legal-content/…/XML` (that's a metadata notice). Consolidated=`is_authentic=0`; original OJ carries CONSID recitals |
| **Core treaties** (Berne, TRIPS, WCT…) | hand-loaded WIPO/WTO text | n/a | none (manual) | no API; `is_official_language` per text |

**Onboarding order** = the confirmed Phase-0 slice, one per source-shape so the schema is
stress-tested by variety, not volume:
1. **17 U.S.C.** (USLM) — proves deep nesting + ordinal suffixes.
2. **CDPA 1988** (CLML) — proves Body-vs-Schedule role split + inserted-section ordinals.
3. **InfoSoc 2001/29** (Formex) — proves articles + the recital/manifestation provenance split.
4. **Berne Convention** (hand-load) — proves the no-XML, hand-entered path + treaty identity.

Each source lands as its own reviewable ingest run (idempotent on the `citation` natural key,
so Title 17 can be re-parsed repeatedly). Tier-1 fetch is **all keyless** — the pending API
keys (GOVINFO/LEGISCAN/CONGRESS_GOV) are only for the Phase-3 bill pipeline, not this slice.

## Decisions still pending (from CLAUDE.md)

- Hosting (local vs Render).
- Own venv vs. continue borrowing `~/Julie/ai-law-portal/.venv`.
- Confirm the Phase-0 first-slice instruments (CDPA 1988 / 17 U.S.C. / DSM+InfoSoc / Berne).
- Copyright-only vs IP-wide (the handoff's open question — the name says IP, the corpus is
  copyright). Affects whether the top nav needs a body-of-law row.
