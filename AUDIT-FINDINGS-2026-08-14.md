# Full jurisdiction gap audit — 2026-08-14 (6 read-only fable agents)

Every instrument cross-checked against its **source artifact** (not just the DB). The motivating
bug (Korea: repealed articles printed "Deleted. ⟨by Act No…⟩" → captured blank) does **not**
recur anywhere except CDPA (F-GB1). But the source-cross-check surfaced many other defects.
Durable record — protects against context loss. Fix status tracked in the right column.

Severity: **H** wrong/blank/missing law shown · **M** degraded · **L** cosmetic.

## Cross-cutting
- **STATUS never set.** `provisions.status` is `in_force` for all ~14,207 rows, incl. every
  repealed/deleted/reserved/omitted provision. Ingests should set `status='repealed'` when they
  detect a tombstone. (US §509/§601/§116A, GB ~31 ss., DE 5, NL 9, CA 30, IN 5, IT/ES/BR notices.) **M**
- **Root causes (shared):** (a) treaty paragraph-splitter treats ANY `(N)`/year token as a
  paragraph → fabricated pinpoints (fix: require sequential 1..N); (b) article/section
  segmentation runs to "next Article/EOF" instead of stopping at chapter/annex/footnote/schedule
  boundaries → tail-bleed & annex dumps; (c) `RecordSet` `#N` uniquifier mints fake pinpoint
  citations from duplicate markers; (d) PDF footnote-gluing (superscripts + footnote bodies).

## By instrument

### GB CDPA 1988 (id 2)
- **F-GB1 H** — 6 repealed ss. **265,268,282,283,284,300** stored as bare number + dots heading
  (the Korea class). Source repeal is in `CommentaryRef`. → capture notice + status=repealed. `ingest_clml.py`
- **F-GB2 H** — **Schedule 5A** (s.296ZE permitted-acts list) stored EMPTY; ~30 `Pnumber`-less
  `P` paragraphs skipped. → handle unnumbered `P` in `ScheduleBody`.
- **F-GB3 M** — 25 more repealed ss. hold source's dots-text but status=in_force (same fix as F-GB1).
- **F-GB4 M** — Schedule 4 canonical citations point at the "Arrangement of Sections" TOC stub;
  real text is under disambiguated `#2` citations (~50 pairs). Deep links resolve wrong-way-round.

### US 17 U.S.C. (id 1) — clean
- **F-US1 L** — §509/§601 (`status="repealed"`) and §116A (`renumbered`) carry the notice text but
  DB status=in_force. → map USLM `status` attr in `ingest_uslm.py`.

### US 37 C.F.R. (id 19) — clean
- **F-CFR1 L** — 6 reserved-RANGE headings garbled (".21 [Reserved]" vs "§§ 201.19-201.21 [Reserved]").
  `ingest_ecfr.py:63` `_split_head` regex stops at 2nd dotted number. Single-section reserved OK.
- **F-CFR2 L** — status nits; instrument title "Parts 201–212" but DB correctly has 200–235.

### DE UrhG (id 5) — clean
- 5 repealed ss. show "(repealed)" ✓. §§139–141 store lone en-dash "–" (source-faithful). status nit.

### FR CPI (id 11) — clean data
- **F-FR1 M** — SOURCE currency: `fr_cpi.txt` is a ~2006 translation (newest act 2006-236); no HADOPI/
  CDSM. France silently ~20yr stale → flag vintage in UI. 658 regulatory "R-" articles excluded (document).

### NL Auteurswet (id 8)
- **F-NL1 M** — PDF footnote bodies absorbed into ~6 articles (15c, 16ga→holds 16d's footnote, 18b;
  glued markers 16d/17a/17d). → strip trailing `^\d+ ⟨footnote⟩` + glued digits in `ingest_nl.py`.
- 9 repeal stubs show notices ✓ (status nit). "as op 07-01-1973" typo is in source.

### ES TRLPI (id 15)
- **F-ES1 H** — sort collision: Art. **31 bis→(44), 40 bis→(54), 40 ter→(56)** — `ordinal()` rejects
  spaced "31 bis" → doc-order fallback collides w/ real 44/54/56. → normalize "31 bis"→"31bis" before `ordinal()` (`_common.py`).
- **F-ES2 H** — Art. **167** swallowed ALL back matter (~15k chars: Additional/Transitional/Repeal/Final
  provisions) — none separately addressable. → split back matter into own provisions.
- **F-ES3 H** — footnote bleed into ~20 arts; **Art. 28 reads as REPEALED while in force** (14,19,20,23,
  40ter,59,104,108,133,144,167). → purge translator footnotes.
- **F-ES4 M** — SOURCE currency: 2012 translation; Art. 25 shows "(Repealed)" but current is in force
  (post-2014/2017 private-copying). Flag vintage. Arts 24/142 notices OK (status nit).

### IT LDA 633/1941 (id 18) — worst body
- **F-IT1 H** — Art. **182 MISSING** (PDF glued its footnote "8" → "Article 1828"; DB jumps 181ter→182bis).
- **F-IT2 H** — Art. **182-bis** stored content is footnote 8's text; the real 182-bis text sits at the tail of "Art. 7 #2".
- **F-IT3 H** — "**Art. 7 #2**" = 5.5k chars of quoted D.Lgs 419/1999 stored as enacting LDA Art. 7 (role should be quoted/excluded).
- **F-IT4 M** — Arts **175–179** (repealed range) absent entirely. → display as repealed.
- **F-IT5 L** — Arts 77/27bis notices OK, status nit; 6 hyphenation splits.

### MX LFDA (id 17) — clean body
- **F-MX1 M** — Transitory provisions (First–Ninth, incl. the clause repealing the 1956/1963 law) dropped. Arts 1–238 exact ✓.

### BR LDA (id 12) — clean
- Art. 111 "(VETOED)" ✓. Art. 115 tail carries signature block (L). 3 hyphen splits (L).

### JP Copyright Act (id 14) — clean
- Deleted Arts 55/85 show "[Deleted]" ✓. status nit. Section citations chapter-blind `#N` (L, cosmetic).

### CN Copyright Law 2020 (id 16) — content clean
- **F-CN1 M** — All 8 subchapter CITATIONS wrong: `ingest_cn.py:105` uses the section number as the
  chapter (Ch. II Sec. 3 stored "Ch. 3 Sec. 3 #25"). Container-only, but citation is the pinpoint key.

### KR Copyright Act (id 13) — clean (fixed earlier)
- 101-6/121 repeal notices verified ✓. **F-KR1 L** — mojibake `¡?` in 2 section headings → normalize to `'`.

### CA Copyright Act C-42 (id 6)
- **F-CA1 H** — 28/277 stored "sections" are amending-act text from the source `<Schedule id="RelatedProvs">`
  appendix under fake C-42 citations (s.280/299/300/301/54.1/58.1 + 22 `#N`). → stop parse at RelatedProvs boundary. `ingest_ca.py:99`
- 30 repeal tombstones show notices ✓ (status nit). No French bleed.

### AU Copyright Act 1968 (id 7)
- **F-AU1 H** — s. **249** swallowed ~68KB (The Schedule + all compilation Endnotes). `ingest_au.py:93`
  slices last section to EOF. → cap at first `ActHead1`; optionally ingest The Schedule.
- 148 textless = legit containers ✓; 18 absent ss. = repealed, omitted from source ✓.

### IN Copyright Act 1957 (id 9)
- **F-IN1 M** — pdftotext superscript pollution: 54/105 bodies keep `N[` markers ("3[sound recording]"),
  ~14 garbled headings (Ch. II "…AND 2[Appellate BOARD]"). `_clean` (`ingest_in.py:52`) doesn't strip them.
- Omitted ss. carry notices ✓; "***" omissions source-faithful.

### SG Copyright Act 2021 (id 10)
- **F-SG1 H** — 111 duplicate "ghost" containers (ids 11062–11172): the Part/Division/Subdivision spine is
  parsed twice (trailing TOC block in `sg_copyright.html`). Minted "Part 1 #2" etc. → cut artifact at TOC / dedupe; delete 111 rows.
- 541 sections continuous ✓ (deletion s.313 "[ Deleted… ]" preserved). Container citations lack Part (L).

### EU directives
- **DSM(20)/Software(21)/Rental(24)/Orphan(25)/Enforcement(26): CLEAN** (recital counts match source).
- **F-EU1 L** — Term(23) consolidated Art. 1 & 10a end with stray "B" (EUR-Lex `▼B` marker residue from
  `ingest_eu_consolidated._strip`). Database(22) Arts 2/6/11 end with next CHAPTER heading (mid-article tail-bleed).
- InfoSoc(3): current = consolidated 2019 ✓, recitals = original OJ ✓. Clean.

### International treaties — biggest no-fake-law liability
- **F-INT1 H** — **~100 fabricated/duplicate pinpoints:** Berne 72 `#N` citations (Art.30(2)#2..#5,
  Appendix I(1)#2..#10, …) + Art.29bis(2)/32(6) cross-ref children; TRIPS 20 footnote-marker "paragraphs"
  (3(3),27(5),28(6),31(7),33(8),36(9),39(10),42(11),50(12),51(13),51(14),73(1)-(9)); year pinpoints
  WCT 25(2002), WPPT 33(2002), Beijing 1(1961), Marrakesh 22(2013)/5(11). → sequential-numbering parser guard + purge.
- **F-INT2 H** — **TRIPS Art. 73** = security clause + entire ANNEX + APPENDIX + footnotes block +
  mojibake `�Berne Convention�` + dangling `</`. Annex/Appendix exist ONLY as bleed (0 own rows).
- **F-INT3 M** — **Missing content:** WCT 10 + WPPT 16 Agreed Statements dropped entirely; Beijing/Marrakesh
  agreed statements dumped into the last article (Art.30/Art.22) instead of their own rows.
- **F-INT4 M** — Missing pinpoints: TRIPS 39(2),62(5),65(3),65(4),31bis(5); Beijing 1(2); Marrakesh 5(4).
- **F-INT5 L** — Tail-bleed of next structural heading on 16 TRIPS arts, Berne 33(headless)/38, Rome 34,
  WPPT/Database chapter headings.

## Remediation waves (plan)
1. **DONE (2026-08-14).** Purged 100 fabricated treaty pinpoints (Berne 72 `#N`, TRIPS 20, 4 year,
   4 cross-ref/footnote) — all carried 0 text. Parser root fixes: `ingest_treaty` + `ingest_berne`
   now require STRICTLY SEQUENTIAL `(1),(2),(3)…` (footnote markers/cross-refs/years/dups rejected);
   `ingest_treaty` WTO parser cuts Art. 73 at "ANNEX TO THE TRIPS AGREEMENT" (kills the annex/mojibake/
   dangling-tag bleed AND the 73(1)-(9) fakes); `ingest_eu_consolidated._strip` strips `▼B/▼M1` as a
   unit (Term `▼B` residue gone). Re-ingested TRIPS; both DBs verified 0 fakes. **F-INT1, F-INT2, F-EU1(Term) fixed.**
   Still open in INT: F-INT3 (agreed statements missing/dumped), F-INT4 (missing pinpoints), F-INT5 (tail-bleed), Database chapter-bleed.
2. **DONE (2026-08-14).** CDPA repealed sections now show the GROUNDED repeal notice from the source
   `<Commentary>` (e.g. s.265 → "S. 265 repealed (9.12.2001) by S.I. 2001/3949…") — 29 sections
   (F-GB1 6 + F-GB3 23). Cross-cutting `status='repealed'` set on all 87 tombstone provisions (29 CDPA
   + 58 others: CA 30, NL 9, DE 6, US 3, ES 3, IT 2, JP 2, KR 2, BR 1); reader shows a rust "Repealed"
   badge. Durable: `_common` auto-detects repeal tombstones (`is_repealed`) + writes `status`;
   `ingest_clml` captures the commentary notice + status. **F-GB1, F-GB3, cross-cutting status fixed.**
   (Remaining durability nit: `ingest_uslm`/`ingest_ecfr`/`ingest_berne`/`ingest_formex` are pre-`_common`
   — their status is set by the current-data migration but a full rebuild wouldn't re-set it; low priority.)
3. **DONE (2026-08-14).** Boundary cuts in three ingests + surgical data excision (both DBs):
   `ingest_sg` stops at the trailing TOC → deleted 111 ghost containers (763→652); `ingest_ca` cuts
   at `RelatedProvs` → deleted 28 amending-act appendix sections incl. the fake s.280/54.1 (277→249
   real sections); `ingest_au` caps the last section at `ActHead1`/Endnotes → s.249 72,000→3,394 chars
   (ends "…within 4 years of receiving it."). TRIPS Art.73 annex bleed already done in wave 1.
   **F-SG1, F-CA1, F-AU1 fixed.**
4. **MOSTLY DONE (2026-08-14).** ES: footnote bleed stripped from ~20 articles (Art. 28 no longer
   reads as repealed) + F-ES1 bis/ter sort collision fixed (31 bis→(31,BIS)). IN: amendment
   apparatus `N[text]`/`N***` stripped from 54 bodies + 11 headings. NL: page-bottom footnote lines
   + glued footnote digits stripped from ~6 articles. All re-ingested both DBs. **F-ES1, F-ES3, F-IN1,
   F-NL1 fixed.** Remaining: IT hyphenation line-splits (F-IT5, low).
5. **DONE (2026-08-14, 5 parallel fix-agents).** IT: Art. 182 recovered (footnote "8" was fused into
   "1828" → header unmatched → whole article dropped) as repealed; Art. 182-bis restored to its real
   AGCOM/SIAE text; the mis-filed quoted-decree "LDA Art. 7 #2" removed; Arts 175-179 added as repealed;
   de-hyphenated; +grounded Art. 101 (`l01` OCR) recovered → 258 articles, no missing integers.
   ES: Art. 167 bounded (715 ch) + back matter split into 27 provisions (5 Additional/20 Transitional/
   Repeal/Final). Treaties: WCT 10 / WPPT 16 / Beijing 11 / Marrakesh 13 Agreed Statements as own
   `recital` provisions + TRIPS Annex+Appendix restored; Beijing Art.30 / Marrakesh Art.22 dumps cleared.
   CDPA Schedule 5A filled SURGICALLY (33 entries, alerts still 91, no existing-row churn). MX transitory
   (9 clauses + container, "Transitional" per source). **F-IT1..5, F-ES2, F-INT3/annex, F-GB2, F-MX1 fixed.**
6. **DONE (2026-08-14).** CN subchapter citations use the enclosing chapter roman (Ch. II Sec. 1);
   KR `¡?`→`'` mojibake; eCFR reserved-range headings show full "§§ X-Y [Reserved]"; FR (~2006) & ES
   (~2012) source-vintage UI caveat on those instruments' pages. **F-CN1, F-KR1, F-CFR1, F-FR1, F-ES4 fixed.**

**Remaining (low):** IT hyphenation edge cases if any; ES Art. 167 "repealed by" was the real Repeal
Provision (now split out, resolved); F-ES4/F-FR1 currency is FLAGGED not re-fetched (by design).
Full regression after all waves: 0 fabricated pinpoints, 0 junk, 0 blank bodies, 0 duplicate citations.
