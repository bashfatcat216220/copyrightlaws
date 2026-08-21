# CourtListener re-fetch — design (2026-08-21, rev. 2 — DRAFT for Bing's review)

> **Plain language:** the case-law data we hold is real but thin and slightly noisy — the original
> fetch took the top 5 *search-relevance* hits per section, which let in an off-topic Ohio
> public-records case, left 10 cases without a real citation, and never captured which court
> decided anything. This plan re-fetches the case layer properly: rank by **how often a case is
> cited** (which surfaces the actual landmark cases — verified today: § 107 returns Harper & Row,
> Sony, Campbell), capture real citations + court level from the same response, and screen out
> off-topic hits. **Nothing touches the database until you approve a written ADD/REMOVE list**
> (phase 1 produces it; phase 2 applies it, and only with the approval code you paste from the
> sheet you read). Statutes, versions, alerts, the monitor: untouched.
>
> **Rev. 2:** reviewed by a senior-developer agent 2026-08-21; 4 blocking + 7 should-fix findings
> folded in. The material changes: existing cases are matched by *opinion identity* (not
> CourtListener's cluster id) so no case page URL ever breaks; links that merely fall below the
> new cap are KEPT, not removed (only screened/absent links are removal candidates); apply is a
> declarative per-DB end-state; approval is an explicit `--approved-sha`/`--approved-by` argument.

## Why (the four defects, from PLATFORM-REVIEW-2026-08-21)
1. **Relevance noise** — full-text phrase search ordered by score linked *State ex rel. Gambill v.
   Opperman* (Ohio mandamus) to § 107.
2. **10/77 cases carry a court+year fallback** instead of a real reporter citation.
3. **`court_level` is 0/77** — binding-vs-persuasive reach can't be computed (migration 002's
   `precedent` axis is unused for cases).
4. **Exactly-5-per-section cap** — top-5 search hits, not real citation frequency.

## Grounded in the live API (probed 2026-08-21, not from memory)
`GET /api/rest/v4/search/?q="17 U.S.C. § 107"&type=o&order_by=citeCount desc&stat_Published=on`
returns (verified):
- the canon in order: Harper & Row (citeCount 1200, scotus), Sony (992), Leadsinger (903, ca9),
  Dudnikov (660, ca10), Campbell (635, scotus) — 644 published hits total;
- per result: `citation` (full parallel-cite list, e.g. `['471 U.S. 539', '105 S. Ct. 2218', …]`),
  `court` (full name) + `court_id` (`scotus`/`ca9`/…), `citeCount`, `status` (Published/…),
  `dateFiled`, `absolute_url`, `cluster_id`, `docket_id`, and `opinions[0].snippet` (real opinion
  text);
- so **one request per section** — no per-cluster second fetch needed for citations or court.

## Design

### Query & ranking (fixes 1 + 4)
- Exact-phrase query per curated section: `"17 U.S.C. § {N}"`; `type=o`, `stat_Published=on`
  (published/precedential only), **`order_by=citeCount desc`**.
- Take top **N=15 per section** (configurable `--per`, default 15). One result page each →
  ~22 requests total, 0.6 s apart, UA identified; optional `COURTLISTENER_API_TOKEN` env for
  authenticated rate limits. Estimated corpus effect: 77 → roughly 200–300 unique cases
  (landmarks repeat across sections and dedupe), 89 → ~330 links. Case pages already render
  multi-section citing.
- citeCount ordering *is* the main noise filter: an off-topic case that mentions a section in
  passing almost never outranks the canon. Two explicit screens on top:
  - **Mechanical screen:** drop hits with `status != 'Published'`; record everything dropped.
  - **Model screen (per CLAUDE.md prime rule 5), ADVISORY:** `claude-opus-4-8` judges each
    surviving hit — given case name, court, snippet, and the target section: *does this opinion
    actually engage this copyright provision?* keep/drop + one-line reason. Constraints:
    * **Offline-safe:** with no `ANTHROPIC_API_KEY`, the screen is marked `not_run` in the
      artifact (never guessed) and all hits pass through. **A `not_run` artifact may not drive
      relevance-based removals at apply time — mechanical reasons only** (the reviewer has no
      legal background and cannot substitute for the screen).
    * **citeCount floor guard:** the model may never drop a hit with citeCount ≥ 200 without the
      row being flagged `high_signal_drop` in the review sheet (a hallucinated drop of Campbell
      must not be one unnoticed checkbox away).
    * If the snippet turns out to be opinion-head rather than citing context (open item 2), the
      screen's verdicts are systematically weak — it stays advisory and its drops require the
      human gate either way.
    * **Invariant: model output never enters the DB.** Every written field (title, cite,
      court_level, holding, source_url, dates) is source-derived; the model only classifies
      fetched text (prime rule 1).
  - **Nothing is silently discarded**: every drop (mechanical or model) lands in the review
    artifact with its reason.

### Identity & matching (review finding B1 — protects existing URLs)
CourtListener carries the same opinion under multiple clusters, and migration 009 already merged
such duplicates — so **`cl-<cluster_id>` is NOT the identity of an opinion**. Matching order at
plan time:
1. **Opinion identity first:** match each fetched hit to existing case instruments by 009's
   `_merge_key` (real reporter cite alone; else title+cite — reuse the function, don't re-derive).
   A merge-key match is a **KEEP/UPDATE against the existing instrument id** — never a
   REMOVE+ADD — so every existing `/instrument/{id}` case URL survives.
2. `ext_id='cl-<n>'` second, for hits with no usable cite.
3. Only a hit matching nothing existing becomes an ADD. 009's dedupe also runs across the fetched
   set itself (parallel-cluster dupes can't re-enter), and 009 re-runs post-apply as a backstop —
   the *mechanism* is merge-key matching at plan time, not the backstop.

### Fields captured (fixes 2 + 3; review findings S1–S3)
- **`official_citation`** = best real cite from the `citation` list, preferred in this order:
  official reporter (`U.S.`) → federal (`F.4th/F.3d/F.2d/F.`) → `F. Supp.` series → `S. Ct.` →
  `L. Ed.` → neutral/regional → specialty (`U.S.P.Q.`, `WL`, `LEXIS`) last. Full parallel list
  retained in the artifact. **A hit with an empty citation list stores NULL** — no minted cite
  and no more court+year pseudo-cites (NULL is also what 009's merge key and the citation slot
  of the UI already handle correctly); existing pseudo-cite rows get a real cite via UPDATE where
  the new data provides one.
- **`authority='precedent'`** set on every case INSERT (CLAUDE.md rule 3a; the current
  `_upsert_case` omits it and only a backfill saved us — new adds must not land NULL).
- **`court_level`** derived from the returned court name/id (source-given, not inferred):
  `scotus` (court_id `scotus`) · `circuit` ("Court of Appeals … Circuit" / `ca1–ca11`, `cadc`,
  `cafed`) · `district` ("District Court") · **`other`** (everything else — state courts, Court
  of Federal Claims, bankruptcy; kept, since state courts hear § 301 preemption and the CFC hears
  § 1498(b) claims). NOT named `state_or_other` (mislabels federal specialty courts). The
  documented vocabulary in `db/schema.sql` + `002_authority_axis.sql` comments is updated to
  `scotus|circuit|district|other`, and the template gets a display mapping (no raw
  `OTHER`-shouting). The full court *name* stays artifact-only for now — no DB column exists and
  no consumer needs it yet; when contextual binding-reach is actually computed, adding a `court`
  column is its own reviewed migration (justified drop, not an oversight).
- **`holding`** = the fetched snippet (≤600 chars, real opinion text, labeled an excerpt — if
  open item 2 shows it's the opinion's opening rather than the citing passage, the UI label says
  "opening excerpt"; never silently implied to be the citing context). `treatment` stays
  `'cited'` — a fact we can source; editorial followed/distinguished remains out.
- **`case_treatment.cite_count` (new nullable INTEGER column, migration 011)** — CourtListener's
  citeCount at fetch time (source-given, dated by `retrieved_at`). This is what lets the reader
  rail order cases by significance instead of `enacted_date DESC` — without it, § 107's rail
  would show 15 cases newest-first with Harper & Row (1985) at the bottom and the whole citeCount
  win never reaches the screen (review finding S6). Rail order: `cite_count DESC NULLS LAST`,
  then date. Additive column; existing rows NULL until touched.
- **Case instrument `status` → `'unknown'`** (schema-legal, render-safe — verified: templates
  badge only `in_force`/`repealed`) — set on new INSERTs **and UPDATEd on every kept existing
  case row**, retiring the `'in_force'` statute concept on opinions at the data level.
- `dateFiled`, full cite list, court id/name, per-section rank: artifact (review context).

### Diff & REMOVE policy (review finding B2 — never delete true data on cap grounds)
Phase 1 diffs the fetched target set against each DB and classifies every existing link:
- **KEEP** — re-confirmed in the new top-N (refresh `retrieved_at`; instrument
  `last_updated_at`).
- **KEEP (below_cap)** — the opinion is still in CourtListener's result set, just not in the
  top-N (verified by a targeted check, not assumed). The link was true when ingested and is true
  now; **a moved cap is not a reason to delete sourced data. Default: KEEP**, listed as its own
  table so Bing can see the category (and could opt to prune it as a *category*, never as
  silently-dropped rows).
- **REMOVE (screened_irrelevant)** — model screen verdict, with its reason (requires the screen
  to have run; blocked on `not_run` artifacts). *Gambill v. Opperman* should land here.
- **REMOVE (not_published)** — mechanical, source-stated status.
- **REMOVE (no_longer_returned)** — verified truly absent from CourtListener for that query
  (not merely below the cap).
Every REMOVE row carries its taxonomy reason; "not in the new result set" as a blanket reason is
banned — for below-cap cases it is factually false. Note: the old fetch used a different,
score-ordered query, so overlap with the new top-15 may be low — expect the below-cap KEEP table
to be significant, which is exactly why it is not a removal category.

### Two-phase gated flow (prime rule: risky seeds gate on human review)
**Phase 1 — plan (no DB writes).** Fetch + screen once, then compute a **per-DB diff**
(corpus.db and corpus-demo.db hold different case states — replaying one DB's diff onto the
other would leave demo's own noise untouched while claiming the same cleanup, review finding
B4). Apply is therefore **declarative**: "after apply, the case layer for the 22 curated
sections equals the approved target set" — each DB converges to the same reviewed end-state via
its own computed steps. Outputs:
- `spike/artifacts/cases_refetch_<date>.json` — the full machine artifact (every hit, field,
  screen verdict, per-DB diff), with its sha256;
- `CASES-REFETCH-REVIEW-<date>.md` — the human review sheet: ADD (name, real cite, court,
  citeCount, **dateFiled**, section, screen verdict) · UPDATE (old → new cite / court_level /
  status) · KEEP · KEEP-below-cap · REMOVE (by taxonomy reason), per DB where they differ, plus
  the artifact sha printed for approval.

**Phase 2 — apply (after sign-off only).**
- **`--apply --artifact <json> --approved-sha <sha> --approved-by "<name>"`** — the sha is the
  one Bing pastes from the sheet he actually read; a mismatch (e.g. phase 1 silently re-ran in
  between) refuses to apply. Pair-consistency between JSON and MD is NOT approval (review
  finding B3 — both are machine-generated; only the operator-supplied sha binds the run to a
  human review). `--approved-by` is recorded in the run output, same discipline as
  `matrix/verify.py --by`.
- **Backup BOTH DBs via the sqlite backup API first** (not just clone-validation — rule 9), then
  validate the full apply on the clone, then apply to both.
- Upserts on the matched existing instrument id (identity rules above) — case page URLs stable.
  REMOVE deletes only `case_treatment` links; a case instrument left with zero links is deleted
  too (it existed only as a citing record; FK ON makes any stray reference abort, links-first
  delete order). 009 re-run as backstop.
- Post-apply, same transaction: `sync_case_fts` (search stays live; stale rowids would already
  drop out of the inner join, but don't rely on it), invariant snapshot printed
  (provisions/versions/alerts byte-identical — this touches **no** monitored text), FK +
  integrity checks, idempotent re-run proof (second apply = 0 changes).

### Where the code lives (review finding S4 — no second path beside the bad one)
The new query/screen/field logic **replaces** the fetch path inside `src/store/ingest_cases.py`
(plan/apply subcommands); the old score-ordered, unscreened, 5-cap `_search` is retired in the
same change. Leaving it alive would re-create all four defects on its next run — the CLAUDE.md
pattern is "fix it durably in the ingest," not "add a better path beside the bad one."
`sync_case_fts` stays as-is (migration 010 imports it).

### UI follow-ups surfaced by the new scale (flagged now, small)
- `/search` case query dedupes AFTER `LIMIT 40`; at ~330 links a landmark citing 8 sections eats
  8 of the 40 slots — group per case in SQL (or raise the pre-dedupe limit) in the same change.
- `/jurisdiction/US` becomes a ~250-case alphabetical list — functional; pagination/grouping is
  a known follow-up, not part of this change.
- Reader rail ordering switches to `cite_count DESC NULLS LAST, enacted_date DESC` (see the
  cite_count column above).

### Tests (keep the suite green; today 10/10)
- Unit: reporter-cite chooser (parallel-list → best real cite; empty list → NULL, never minted);
  court_level mapper (scotus/circuit/district/other fixtures incl. a state court and the CFC);
  merge-key matching (same opinion under a new cluster id → UPDATE, not REMOVE+ADD);
  apply refuses a sha mismatch; apply is idempotent; `not_run` artifact blocks relevance REMOVEs.
- Clone validation + live checks: `/search?q=fair use` surfaces Campbell/Harper & Row/Sony;
  § 107 reader rail leads with the landmarks (cite_count ordering); existing case URLs still 200;
  jurisdiction browse renders.

### Out of scope (unchanged decisions)
- No opinion re-hosting (finding aid, prime rule 2) — excerpts only, link out for full text.
- The 22-section curation stays as-is; widening it is a separate, later decision.
- No editorial treatment labels; no citator ambitions.
- No `court` name column yet (artifact-only; its own migration when contextual binding-reach is
  built).

### Open items to verify at implementation (flagged, not assumed)
1. Whether CourtListener tokenizes `§` away (i.e. `"17 U.S.C. § 107"` ≡ `"17 U.S.C. 107"`); if
   not equivalent, run both phrase variants and union before ranking.
2. Whether the snippet under citeCount ordering is match-context or opinion-head (today's probe
   suggests opinion-head); if opinion-head, either request highlighting or keep and label it
   "opening excerpt" — never silently imply it's the citing passage. Affects the model screen's
   strength (kept advisory regardless).
3. Anonymous rate-limit headroom for ~22 search requests + the below-cap verification checks
   (still small; token is a fallback, not a requirement).
