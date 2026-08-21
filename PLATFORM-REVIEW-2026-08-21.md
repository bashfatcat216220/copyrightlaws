# Platform Review — 2026-08-21 (practitioner's-lens walkthrough)

_A click-through of the running app (`:8021`, `corpus.db`) evaluating the PLATFORM — organization,
usability, depth, work-product credibility — NOT a line-by-line validity audit of the law (that
stays with the `AUDIT-FINDINGS-*` sweeps; every substantive claim still gets confirmed against the
primary source). Reviewer stance: an IP attorney deciding whether this is trustworthy work product.
Grounded in screenshots of 14 pages + a read of the tables behind them. No writes made._

## Method / pages walked
Home · `/jurisdiction/US` · `/jurisdiction/INT` · instrument landings (17 U.S.C., CDPA, TRIPS,
DSM, Berne, Spain TRLPI) · the section reader (`/instrument/1/s-107`, fair use) · a case page
(`/instrument/36`, *Oracle v. Google*) · `/search?q=fair use` · `/alerts` · `/matrix`. DB spot-check
of `case_treatment`, `provisions`, `instruments`.

## Verdict
**Good work product at the statute/treaty layer — real, careful, honest about its limits.** The
infrastructure reads like a genuine legal research tool, not a demo. The gap to close is **content
depth on the three things a litigator reaches for first**: case law, cross-jurisdiction comparison,
and (to a lesser degree) full-text reach. Today it is a credible **statutory finding aid**, not yet
a **research platform**.

## Strengths (would survive "show me")
- **Discipline is visible everywhere.** The "internal research aid — not verified for currency"
  caveat rides every page; every provision carries `source_url` + `retrieved_at` (verified the live
  `uscode.house.gov` USLM link under § 107).
- **The section reader is the best screen** — three-column: section index / full statutory text with
  the four fair-use factors / cases in the right rail. Right shape for the work.
- **Real structure, not flattened dumps** — TRIPS Parts I–VII with article ranges + counts; CDPA
  Parts + numbered grid with `[Repealed]` tombstones; Spain Books I–IV + transitional/final.
- **Currency honesty on translations** — Spain's page shows "source translation dated ~2012 — may not
  reflect later amendments." That flag is exactly what an attorney needs surfaced, not buried.
- **Change-monitor works** — `/alerts` shows 91 real CDPA redline diffs. Deep-linkable pinpoints
  (`/instrument/1/s-107`) work.

## Punch list — ordered by how much it bites a practitioner

### 1 — Case law is the weakest link, and it's the most valuable content. **[HIGH]**
Under the hood: **81 cases · 93 `case_treatment` links**, but:
- **Standalone case pages are empty shells.** `/instrument/36` (*Oracle v. Google*) → "No stored
  version yet for this instrument," Cases · 0. A case's content lives ONLY as a snippet hung off a
  statutory section, so navigating *to* a case is a dead-end.
- **`treatment`/`holding` are honest-but-thin (not a defect).** Every link is `treatment='cited'`
  and the `holding` field carries the raw CourtListener opinion excerpt (~600 chars) shown as citing
  context, not an editorial headnote. This is a *documented, deliberate* honesty choice
  (`ingest_cases.py` docstring) and the UI already discloses it ("'cited' is factual; editorial
  treatment is not asserted"). Correct posture for a finding aid — flagged only as a depth ceiling,
  not a bug.
- **Linkage looks capped and noisy.** Sections cluster at *exactly* 5 cases each (§§ 102, 103, 106,
  107, 108, 201, 204, 301 all = 5) — an arbitrary cap (`_search` `[:per]`, default 5), not real
  citation frequency. Confirmed false positive: *State ex rel. Gambill v. Opperman* (an **Ohio
  public-records mandamus** case) is linked to § 107 fair use.
- **Duplicate rows + an "In Force" mislabel.** The same opinion was minted under multiple
  CourtListener clusters (e.g. *Gamma v. Ean-Chea*, *American Geophysical* 60 F.3d 913); and case
  instruments render the statute status **"In Force"** — a statute concept leaking onto an opinion.
  _(Earlier drafts of this review also reported a "stray 1768" in the case rail — that was a
  low-resolution misread of pixelated citation text; the rail renders no such field.)_

**Resolution (2026-08-21) — display fixes + safe dedup shipped:** standalone case pages are now a
real, reachable **reverse-citation finding aid** (case metadata + the provisions it's recorded as
citing, deep-linked back into the reader + a link out to the full opinion); the rail's case names now
link to those pages, and court+year fallbacks no longer masquerade as reporter citations; the "In
Force" mislabel is gone; and migration `009_dedupe_cases.py` merged the duplicate case rows on both
DBs (81 → 77 cases; validated on a backup clone, invariants intact, 0 orphans, pytest 6/6).
**Deferred (gated CourtListener re-fetch):** the relevance filter (false positives like *Gambill*),
real reporter citations + `court_level`, the 5-per-section cap, and the 22-section curation — the
work that improves case *coverage*.

### 2 — The Matrix is empty. **[HIGH — expectation gap]**
`/matrix` is a top-nav item (the cross-jurisdiction comparison: term, moral rights, TDM/AI exception,
fair use, safe harbour) that lands on "The matrix is empty. Cells are populated in Phase 4." Shipping
it in the nav while empty invites disappointment. Either populate (human-gated, per prime rule 4) or
hide until it has cells.

**Resolution (2026-08-21) — populated as a real, human-gated comparison grid.** A vertical-slice seed
(6 jurisdictions US/GB/EU/CA/AU/DE × 6 attributes: individual term, corporate/for-hire term, open
fair use vs. closed list, commercial TDM/AI, moral-rights waivability, intermediary safe harbour = 36
cells) was **drafted by claude-opus-4-8 strictly from the cited corpus provisions** (`seed_cells.py`),
loaded as **Drafts** (`load_cells.py` → `matrix_cells`, resolving each to its source version; one
documented gap — DE platform liability lives in UrhDaG, not in corpus — loads unsourced). `/matrix`
now renders a grid (attributes × jurisdictions), each cell showing the value, a Draft/Verified marker,
and a deep link to the source provision. Human gate wired: `verify.py` promotes a cell only if it
cites a source version (the schema trigger enforces it — tested). The Claude API draft path is wired
offline-safe (`draft.py`). **Still Draft until Bing signs off** via `verify.py`. pytest 8/8.
**Deferred:** the other 9 attributes + 12 jurisdictions; an unattended API draft batch once a key is
in `.env`.

### 3 — Cases and the Compendium are invisible from browse. **[MED]**
`/jurisdiction/US` lists **2 instruments** (17 U.S.C. + 37 C.F.R.) while its own subtitle promises
"+ Copyright Office Compendium" (not present). All 81 cases are unreachable except via search or a
section's right rail — a researcher browsing "US copyright" would never learn the case law exists.

**Resolution (2026-08-21).** `/jurisdiction/US` now carries a **"Case law · 77"** section — an
alphabetical index of every case, each linking to its case page (built in issue 1), with the reporter
citation (or year for court+year fallbacks). The home US card shows "2 INSTRUMENTS · 77 CASES", and
the false "Copyright Office Compendium" subtitle was corrected to "17 U.S.C. (Title 17) + 37 C.F.R.
(Copyright Office regulations)" in `seed_jurisdictions.sql` + both DBs. The "instruments" denominator
stays **law-only (32)** — cases are counted separately, never folded in (honesty). No-case
jurisdictions render unchanged. pytest 8/8. **Deferred:** a global `/cases` index (once cases exist
for >1 jurisdiction) and actually loading the Compendium.

### 4 — Search can't reach the cases. **[MED]**
`/search?q=fair use` returns statute/treaty snippets (mostly "fair dealing"), not case discussion,
because opinion text isn't in the searchable store. For fair use specifically, the cases *are* the
law — a real depth gap.

## Scope note — this is a COPYRIGHT corpus
For a trademark practice there is essentially nothing direct (no Lanham Act, no TMEP, no PTO/TTAB).
The one bridge is **TRIPS Part II** (loaded, 33 articles), which covers trademarks (Arts. 15–21). As
a *trademark* tool it is out of scope today; as an architectural **template** for a Lanham Act +
TTAB + Madrid corpus it is strong — the connector / versioning / caveat machinery ports directly.

## Next steps
Fixes gated behind plan mode (no edits made in this pass). **Starting with issue 1 (case law).**
The highest-leverage order: (1) make case pages real + fix the false-positive/capped linkage,
(2) surface cases + Compendium in browse, (3) hide-or-populate the Matrix, (4) index opinion text
into search.
