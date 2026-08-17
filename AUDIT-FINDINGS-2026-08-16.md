# Audit Findings — 2f (authoritative editions) + 2g (back-matter/appendices)

_Read-only sweep, 2026-08-16, 7 `fable` agents by jurisdiction group (US / UK / Commonwealth /
EU / INT / national×2). Every claim below is grounded in a fetched source artifact or a live
source URL; agents made NO writes. This is the review gate (prime rule 2) BEFORE ingest._

## Scope
Two questions across all 32 instruments:
- **2f — Are we holding the actual authoritative edition of the law, or a finding-aid edition?**
- **2g — Is every appendix / schedule / annex / addenda / transitional provision captured?**

---

## 2g — Missing operative back-matter (the "appendices" work). PUNCH LIST.

Ordered by severity. "Present in artifact" = the text is already on disk in `spike/artifacts/`,
so ingesting it needs NO new fetch. Root cause is a parser that stops before the back-matter.

| # | Instrument (id) | Missing item | Why it's operative | Sev |
|---|---|---|---|---|
| 1 | 37 C.F.R. (19) | **Part 202 Appendix B** ("Best Edition" statement) + Appendix A (Technical Guidelines) | App. B is *incorporated by reference* into in-force § 202.19(b)(1) — it governs mandatory deposit. `ingest_ecfr.py` drops `TYPE="APPENDIX"` nodes. | **HIGH** |
| 2 | EU Orphan Works 2012/28 (25) | **The Annex** (minimum diligent-search sources) | Mandated verbatim by Art 3(2) ("shall include at least the relevant sources listed in the Annex"). `ingest_eu_directive.py` has no annex stage. | **HIGH** |
| 3 | KR Copyright Act (13) | **9 Addenda blocks (부칙)** | Enforcement-date + transitional rules for each amending Act (Nos. 8852/2008 … 12137/2013). Present in KLRI artifact, 0 in corpus. | **HIGH** |
| 4 | JP Copyright Act (14) | **Supplementary Provisions (附則)** — 55 blocks | Operative transitional rules (application to pre-existing works). 0 in corpus. | **HIGH** |
| 5 | 17 U.S.C. (1) | **1976 Act Transitional & Supplementary Provisions** (Pub. L. 94-553 §§102–115) | Operative uncodified law (effective-date, savings). Carried in artifact as statutory notes; `ingest_uslm.py` SKIPs all notes. | MED |
| 6 | DE UrhG (5) | **Annex to § 61a** (diligent-search sources) | Referenced by § 61a(1) ("at the very least the sources set out in the Annex"). 0 in corpus. | MED |
| 7 | CA Copyright Act (6) | **Schedule I "Existing Rights"** (+ Sch II/III repeal tombstones) | Sch I is referenced by in-force s. 60 ("column I of Schedule I"). Never captured (ingest only mints numbered sections). NOT lost by the prior appendix excision. | MED |
| 8 | AU Copyright Act (7) | **"The Schedule"** (oath/affirmation) | Referenced by in-force s. 144. Only schedule in the Act; 0 in corpus. | MED |
| 9 | EU Software (21), Rental (24), Term (23) | **Annex I/II** (repealed-directive list + transposition dates + correlation table) | Referenced by the directives' final articles; non-substantive codification apparatus. | LOW |
| 10 | ES TRLPI (15) | RDL 1/1996 wrapper (Single Article / **Single Repeal** / Single Final) | The repeal provision (derogatoria) is operative. Not captured or documented as excluded. | LOW |
| 11 | UK CDPA (2) | Schedule 8 (Repeals) is a **content-less stub** | Exclude-eligible (repeals table reproducing other acts) but silent — needs the table text OR a documented exclusion note. | LOW |

### 2g — confirmed OK / no action
- **Treaty Agreed Statements are PRESENT, not missing** — the old "skipped for PDFs" note is
  STALE. WCT 9/9, WPPT 10/10, Beijing 11/11, Marrakesh 13/13 (backfilled 2026-08-14). Berne
  Appendix I–VI complete; TRIPS Annex + Appendix complete and clean.
- **SG (10):** the 2021 Act has **no Schedules** in the SSO source (premise not borne out —
  reported honestly, nothing invented). **IN (9):** no Schedules (Gazette controls). **CA:** the
  RELATED-PROVISIONS / AMENDMENTS-NOT-IN-FORCE appendices correctly stay excluded.
- BR/CN/MX tails all present & clean (MX 9 Transitorios restored, verified verbatim incl. a
  source typo faithfully reproduced).

### 2g — data-quality cleanups found along the way (cheap, no new law)
- Berne Appendix Art VI swallowed ~1,350 chars of WIPO editorial footnotes (incl. quoted 1896
  treaty text — a fake-law confusion risk). **MED.** Re-segment before the `<hr>`.
- Rome Art 34 / WCT Art 25 / WPPT Art 33 each swallowed a small "Source: WIPO" editorial endnote. LOW.
- JP Chapter VIII sort defect: 123/124 sort before 120-2/121-2/122-2. LOW.

---

## 2f — Authoritative-edition findings

Most of 2f is **relabeling** (metadata), not new text. Only a few items are genuine new-text ingests.

### Relabels (no re-ingest — just fix `source_edition`)
- **CA (6):** `finding_aid` → **official** — Justice Laws is official for evidentiary purposes
  since 2009-06-01 (site's own Important Note).
- **AU (7):** `finding_aid` → **official** — Federal Register of Legislation is the authoritative
  register (Legislation Act 2003 ss 15B/15ZA); corpus already holds the current compilation.
- **UK CDPA (2):** `finding_aid` → **consolidated** — it's TNA's official revised edition, not a
  mere aid. (Do NOT re-ingest: it carries point-in-time versions + fired alerts.)
- **IN (9):** keep `finding_aid` (Gazette controls) + add an instrument note.
- **SG (10):** relabel → official **pending manual check** (SSO 403s scripted fetch, can't verify authority statement).

### New-text ingests (real authoritative law we don't hold)
- **EU InfoSoc 2001/29 (3):** we hold only the editorial consolidation as enacting text; the only
  `is_authentic=1` rows are its 61 recitals. Recommend ingesting the **authentic original articles**
  (+ the 2 amendment layers). Authentic original text is already on disk.
- **EU Term 2006/116 (23):** Art 10a exists only as consolidation text; ingest amending act
  **2011/77** (or an amendments row) for the authentic layer.
- **37 C.F.R. (19):** authoritative = GPO annual CFR + Federal Register (eCFR is a finding aid).
  Recommend an **additive** pinned official point-in-time baseline (GPO annual XML, fetch verified),
  keeping eCFR as the current working text. Label already honest.

### Already authoritative / correctly labeled (no action)
- **17 U.S.C. (1):** positive-law title — the Code text IS legal evidence regardless of
  manifestation; `finding_aid` label honest. (Optional: cross-ref the GPO package; fix a dead
  `bulkdata/USCODE` URL in `src/connectors/govinfo_us.py`.)
- **7 treaties (4, 27–32):** authentic-language text from WIPO Lex / WTO. No action.
- **5 EU original_act directives (20, 21, 24, 25, 26):** no post-adoption amendment → authentic
  original is current. (Enforcement 2004/48: one OJ L 195 corrigendum spot-check.)
- **10 translations (5, 8, 11, 12, 13, 14, 15, 16, 17, 18):** all correctly `translation` /
  `is_official_language=0`; keep + link to the official-language portal. **Add missing vintage
  caveats: NL (~2012), IT (~2003)** — FR (~2006) and ES (~2012) already have them.

### 2f — real bugs found (not new law, but honesty gaps)
- **UK CDPA `has_unapplied_effects` is never set** — the current CLML snapshot carries a live
  `RequiresApplied="true"` effect (SI 2026/103, Pt 2) but all 1,597 versions read 0. `ingest_clml.py`
  never parses the effects metadata. Prime-rule-3 surfacing failure. **MED.**
- **37 C.F.R. reserved sections** carry `status='in_force'` (should be `reserved`/`unknown`). LOW.
- **`is_authentic=1` on all 10 translations** contradicts `is_official_language=0` — schema-semantics review. LOW.
- **EU `amendments` table is empty** though the corpus embodies ≥3 amendment events. Provenance-metadata gap (do NOT feed to the change monitor). LOW.
- **37 C.F.R. instrument title** says "Parts 201–212" but corpus correctly holds Parts 200–235 (F-CFR2). LOW.

---

## Proposed remediation waves (each scratch-validated before central load; gated on Bing)
- **Wave A (HIGH back-matter):** #1 37 CFR appendices · #2 Orphan Works Annex · #3 KR Addenda ·
  #4 JP Supplementary Provisions. New `kind`/role = `schedule` (TRIPS precedent; no migration needed).
- **Wave B (MED back-matter):** #5 US 94-553 transitional · #6 DE §61a Annex · #7 CA Schedule I
  (+ II/III tombstones) · #8 AU The Schedule.
- **Wave C (2f relabels + honesty):** CA/AU→official, UK→consolidated (+ has_unapplied_effects fix),
  IN/SG notes, NL/IT vintage caveats, 37 CFR reserved status + title.
- **Wave D (2f new-text):** EU InfoSoc authentic articles · Term 2011/77 · 37 CFR GPO baseline.
- **Wave E (LOW cleanups):** EU codification annexes · ES RDL wrapper · CDPA Sch 8 note ·
  Berne/Rome/WCT/WPPT footnote trims · JP sort · schema-semantics review.
</content>
</invoke>
