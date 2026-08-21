# CourtListener re-fetch — REVIEW SHEET (2026-08-21)

Per design `CASES-REFETCH-DESIGN-2026-08-21.md`. Top 15 published opinions per section, citeCount-ranked, both `§` phrase variants. Model screen: **not_run** — relevance-based removals are BLOCKED for this artifact (mechanical reasons only); below-cap links will be screened on a future plan run with the key set.

Artifact: `cases_refetch_2026-08-21.json`
**APPROVAL SHA:** `d585ca6f9b627885e33697f4e14bea888dfc07dec913ba5a054009b60fabb615`

To apply (per DB, after review):
```
python src/store/ingest_cases.py apply --db db/corpus.db --allow-corpus \
    --artifact spike/artifacts/cases_refetch_2026-08-21.json \
    --approved-sha d585ca6f9b627885e33697f4e14bea888dfc07dec913ba5a054009b60fabb615 --approved-by "<your name>"
```

Apply also normalizes every case instrument's `status` `'in_force'` → `'unknown'` (a statute concept retired on opinions — disclosed here, not hidden in code).

## corpus-demo.db

ADD 226 new cases carrying 323 section links + 0 new links to existing cases · UPDATE 7 · KEEP 7 · KEEP-below-cap 63 · REMOVE 0 · MANUAL 0

### ADD — new cases (one row per case; §§ = every section it topped)

| Case | Cite | Court | citeCount | Filed | §§ | Screen |
|---|---|---|---|---|---|---|
| Chambers v. Time Warner, Inc. | 282 F.3d 147 | circuit | 4257 | 2002-02-21 | 106, 501 | not_run |
| Arista Records, LLC v. Doe 3 | 604 F.3d 110 | circuit | 2828 | 2010-04-29 | 106 | not_run |
| Lexmark Int'l, Inc. v. Static Control Components, Inc. | 572 U.S. 118 | scotus | 2774 | 2014-03-25 | 1201 | not_run |
| Feist Publications, Inc. v. Rural Telephone Service Co. | 499 U.S. 340 | scotus | 2736 | 1991-03-27 | 102 | not_run |
| Cipollone v. Liggett Group, Inc. | 505 U.S. 504 | scotus | 2642 | 1992-06-24 | 301 | not_run |
| Gasperini v. Center for Humanities, Inc. | 518 U.S. 415 | scotus | 1870 | 1996-06-24 | 302 | not_run |
| Fogerty v. Fantasy, Inc. | 510 U.S. 517 | scotus | 1804 | 1994-03-01 | 505 | not_run |
| Harper & Row, Publishers, Inc. v. Nation Enterprises | 471 U.S. 539 | scotus | 1200 | 1985-05-20 | 102, 106, 107, 115, 504 | not_run |
| Community for Creative Non-Violence v. Reid | 490 U.S. 730 | scotus | 1160 | 1989-06-05 | 201, 301 | not_run |
| City of New York v. Mickalis Pawn Shop, LLC | 645 F.3d 114 | circuit | 1157 | 2011-05-04 | 411 | not_run |
| Bank of the West v. Superior Court | 833 P.2d 545 | other | 1058 | 1992-07-30 | 106 | not_run |
| Sony Corp. of America v. Universal City Studios, Inc. | 464 U.S. 417 | scotus | 992 | 1984-01-17 | 102, 107, 411, 501 | not_run |
| Professional Real Estate Investors, Inc. v. Columbia Picture | 508 U.S. 49 | scotus | 962 | 1993-05-03 | 106, 109 | not_run |
| Marek v. Chesny | 473 U.S. 1 | scotus | 926 | 1985-06-27 | 505 | not_run |
| Leadsinger, Inc. v. BMG Music Publishing | 512 F.3d 522 | circuit | 903 | 2008-01-02 | 102, 106, 107, 115 | not_run |
| Reed Elsevier, Inc. v. Muchnick | 559 U.S. 154 | scotus | 754 | 2010-03-02 | 102, 411, 412 | not_run |
| TechnoMarine SA v. Giftports, Inc. | 758 F.3d 493 | circuit | 723 | 2014-07-15 | 501 | not_run |
| Bouchat v. Baltimore Ravens Football Club, Inc. | 346 F.3d 514 | circuit | 698 | 2003-10-08 | 412, 412, 504 | not_run |
| Edward H. Bohlin Co., Inc. v. Banning Co., Inc. | 6 F.3d 350 | circuit | 675 | 1993-11-10 | 501 | not_run |
| Dudnikov v. Chalk & Vermilion Fine Arts, Inc. | 514 F.3d 1063 | circuit | 660 | 2008-01-28 | 107, 512 | not_run |
| Campbell v. Acuff-Rose Music, Inc. | 510 U.S. 569 | scotus | 635 | 1994-03-07 | 106, 107 | not_run |
| Mavrix Photo, Inc. v. Brand Technologies, Inc. | 647 F.3d 1218 | circuit | 604 | 2011-08-08 | 501 | not_run |
| Cindy Garcia v. Google, Inc. | 786 F.3d 733 | circuit | 597 | 2015-05-18 | 102, 106A, 201, 203, 512 | not_run |
| Fantasy, Inc. v. Fogerty | 984 F.2d 1524 | circuit | 575 | 1993-02-02 | 505 | not_run |
| Metro-Goldwyn-Mayer Studios Inc. v. Grokster, Ltd. | 545 U.S. 913 | scotus | 547 | 2005-06-27 | 504 | not_run |
| Marder v. Lopez | 450 F.3d 445 | circuit | 535 | 2006-06-12 | 106 | not_run |
| Briarpatch Limited, L.P., Gerard F. Rubin v. Phoenix Picture | 373 F.3d 296 | circuit | 534 | 2004-06-25 | 102, 103, 106, 301 | not_run |
| Regan v. Time, Inc. | 468 U.S. 641 | scotus | 510 | 1984-07-03 | 106 | not_run |
| Arista Records LLC v. John Does 1-19 | 551 F. Supp. 2d 1 | district | 509 | 2008-04-28 | 512 | not_run |
| A&M Records, Inc. v. Napster, Inc. | 239 F.3d 1004 | circuit | 496 | 2001-02-12 | 106, 107, 115, 501, 512 | not_run |
| Dastar Corp. v. Twentieth Century Fox Film Corp. | 539 U.S. 23 | scotus | 493 | 2003-06-02 | 102, 106A | not_run |
| Penguin Group (USA) Inc. v. American Buddha | 609 F.3d 30 | circuit | 481 | 2010-06-15 | 501 | not_run |
| Darrell J. Bird v. Marshall Parsons, Stephen Vincent, George | 289 F.3d 865 | circuit | 479 | 2002-05-21 | 106 | not_run |
| Anthony Dash v. Floyd Mayweather, Jr. | 731 F.3d 303 | circuit | 473 | 2013-09-26 | 504 | not_run |
| Salinger v. Colting | 607 F.3d 68 | circuit | 463 | 2010-04-30 | 107 | not_run |
| Phillips v. Audio Active Ltd. | 494 F.3d 378 | circuit | 451 | 2007-07-24 | 504 | not_run |
| Petrella v. Metro-Goldwyn-Mayer, Inc. | 572 U.S. 663 | scotus | 442 | 2014-05-19 | 115, 504 | not_run |
| Brownmark Films, LLC v. Comedy Partners | 682 F.3d 687 | circuit | 427 | 2012-06-07 | 107 | not_run |
| Axiom Foods, Inc. v. Acerchem International, Inc. | 874 F.3d 1064 | circuit | 427 | 2017-11-01 | 501 | not_run |
| Therasense, Inc. v. Becton, Dickinson and Co. | 649 F.3d 1276 | circuit | 425 | 2011-05-25 | 411 | not_run |
| Nola Spice Designs, L.L.C. v. Haydel Enterprises, Inc. | 783 F.3d 527 | circuit | 420 | 2015-04-08 | 102 | not_run |
| Computer Associates International, Inc., Plaintiff-Appellant | 982 F.2d 693 | circuit | 411 | 1992-12-17 | 102, 106, 301 | not_run |
| Lloyd Lieb, Trading as Specialized Cassettes v. Topstone Ind | 788 F.2d 151 | circuit | 404 | 1986-04-14 | 505 | not_run |
| Warren v. Fox Family Worldwide, Inc. | 328 F.3d 1136 | circuit | 398 | 2003-05-13 | 201, 501 | not_run |
| Harris v. Garner | 216 F.3d 970 | circuit | 392 | 2000-06-27 | 411, 411 | not_run |
| Feltner v. Columbia Pictures Television, Inc. | 523 U.S. 340 | scotus | 376 | 1998-03-31 | 504 | not_run |
| Progressive Animal Welfare Society v. University of Washingt | 884 P.2d 592 | other | 373 | 1994-11-22 | 106 | not_run |
| Securacomm Consulting, Inc. v. Securacom Inc. | 224 F.3d 273 | circuit | 364 | 2000-08-21 | 505 | not_run |
| MAI Systems Corp. v. Peak Computer, Inc. | 991 F.2d 511 | circuit | 359 | 1993-04-07 | 106 | not_run |
| Yurman Design, Inc. Plaintiff-Appellee-Cross-Appellant v. Pa | 262 F.3d 101 | circuit | 358 | 2001-08-10 | 102, 103, 504 | not_run |
| Perfect 10, Inc. v. Amazon. Com, Inc. | 508 F.3d 1146 | circuit | 345 | 2007-12-03 | 107, 411, 501, 512 | not_run |
| Ellison v. Robertson | 357 F.3d 1072 | circuit | 342 | 2004-02-10 | 501, 512 | not_run |
| Knitwaves, Inc., Plaintiff-Appellee-Cross-Appellant v. Lolly | 71 F.3d 996 | circuit | 337 | 1995-11-13 | 412, 504, 505 | not_run |
| Thomas Walker v. Time Life Films, Inc., David Susskind, Gill | 784 F.2d 44 | circuit | 334 | 1986-01-07 | 102, 301 | not_run |
| Humphreys & Partners Architects v. Lessard Design, Incorpora | 790 F.3d 532 | circuit | 329 | 2015-06-23 | 102 | not_run |
| Durham Industries, Inc. v. Tomy Corporation | 630 F.2d 905 | circuit | 328 | 1980-09-02 | 102, 103, 301 | not_run |
| Stewart v. Abend | 495 U.S. 207 | scotus | 323 | 1990-04-24 | 103, 107 | not_run |
| Data General Corp. v. Grumman Systems Support Corp. | 36 F.3d 1147 | circuit | 322 | 1994-09-15 | 102, 301, 411, 504 | not_run |
| Tewarson v. Simon | 750 N.E.2d 176 | other | 308 | 2001-01-03 | 301 | not_run |
| Elektra Entertainment Group Inc. v. Crawford | 226 F.R.D. 388 | district | 307 | 2005-02-11 | 501, 504, 505 | not_run |
| Image Software, Inc. v. Reynolds & Reynolds Co. | 459 F.3d 1044 | circuit | 307 | 2006-08-23 | 501 | not_run |
| Strike 3 Holdings, LLC v. John Doe | 964 F.3d 1203 | circuit | 307 | 2020-07-14 | 512 | not_run |
| Lipton v. Nature Co. | 71 F.3d 464 | circuit | 303 | 1995-11-28 | 501, 504 | not_run |
| Castle Rock Entertainment, Inc. v. Carol Publishing Group, I | 150 F.3d 132 | circuit | 302 | 1998-07-10 | 107 | not_run |
| Carruthers v. Carrier Access Corp. | 251 P.3d 1199 | other | 301 | 2010-10-28 | 505 | not_run |
| Adriana International Corp. v. Thoeren | 913 F.2d 1406 | circuit | 300 | 1990-09-10 | 501 | not_run |
| Batzel v. Smith | 333 F.3d 1018 | circuit | 291 | 2003-06-24 | 512, 512 | not_run |
| Disney Enterprises, Inc. v. Vidangel, Inc. | 869 F.3d 848 | circuit | 290 | 2017-08-24 | 107, 109, 110, 1201 | not_run |
| Harolds Stores, Inc. v. Dillard Department Stores, Inc. | 82 F.3d 1533 | circuit | 281 | 1996-05-03 | 301, 412 | not_run |
| Baker & Hostetler LLP v. United States Department of Commerc | 473 F.3d 312 | circuit | 270 | 2006-12-22 | 505 | not_run |
| Dowling v. United States | 473 U.S. 207 | scotus | 269 | 1985-06-28 | 115 | not_run |
| The Gates Rubber Co. v. Bando Chemical Industries, Ltd. | 9 F.3d 823 | circuit | 266 | 1993-10-19 | 301 | not_run |
| Barefoot Architect, Inc. v. Bunge | 632 F.3d 822 | circuit | 264 | 2011-01-14 | 201, 204 | not_run |
| Fourth Estate Pub. Benefit Corp. v. Wall-Street.com, LLC | 586 U.S. 296 | scotus | 257 | 2019-03-04 | 411 | not_run |
| Smith v. Jackson | 84 F.3d 1213 | circuit | 248 | 1996-06-05 | 505 | not_run |
| Umg Recordings, Inc. v. Shelter Capital Partners Llc | 718 F.3d 1006 | circuit | 245 | 2013-03-14 | 505, 512, 1201 | not_run |
| Darrell Taylor, D/B/A Darrell Taylor Topographic Charts v. J | 712 F.2d 1112 | circuit | 243 | 1983-07-07 | 504, 505 | not_run |
| Art Rogers, Plaintiff-Appellee-Cross-Appellant v. Jeff Koons | 960 F.2d 301 | circuit | 237 | 1992-04-02 | 107, 504 | not_run |
| TWENTIETH CENTURY MUSIC CORP. Et Al. v. AIKEN | 422 U.S. 151 | scotus | 235 | 1975-06-17 | 110 | not_run |
| Spinelli v. National Football League | 903 F.3d 185 | circuit | 235 | 2018-09-11 | 1202 | not_run |
| ProCD, Inc. v. Zeidenberg | 86 F.3d 1447 | circuit | 233 | 1996-06-20 | 301 | not_run |
| Chicago Building Design, P.C. v. Mongolian House, Inc. | 770 F.3d 610 | circuit | 233 | 2014-10-23 | 504 | not_run |
| Lyons Partnership, L.P., a Texas Limited Partnership v. Morr | 243 F.3d 789 | circuit | 232 | 2001-03-16 | 505 | not_run |
| Israel Santiago-Lugo v. Warden | 785 F.3d 467 | circuit | 231 | 2015-04-30 | 411 | not_run |
| Rimini Street, Inc. v. Oracle USA, Inc. | 586 U.S. 334 | scotus | 228 | 2019-03-04 | 505 | not_run |
| On Davis v. The Gap, Inc. | 246 F.3d 152 | circuit | 227 | 2001-04-10 | 107, 412 | not_run |
| Lotes Co. v. Hon Hai Precision Industry Co. | 753 F.3d 395 | circuit | 227 | 2014-06-04 | 411 | not_run |
| Psihoyos v. John Wiley & Sons, Inc. | 748 F.3d 120 | circuit | 227 | 2014-04-04 | 411 | not_run |
| Eldred v. Ashcroft | 537 U.S. 186 | scotus | 226 | 2003-01-15 | 107, 108, 110, 302 | not_run |
| Kirtsaeng v. John Wiley & Sons, Inc. | 579 U.S. 197 | scotus | 225 | 2016-06-16 | 505 | not_run |
| James W. Cleary v. News Corporation and Harpercollins Publis | 30 F.3d 1255 | circuit | 221 | 1994-08-01 | 201 | not_run |
| James Owens v. Republic of Sudan | 864 F.3d 751 | circuit | 219 | 2017-07-28 | 411 | not_run |
| Microsoft Corp. v. At&t Corp. | 550 U.S. 437 | scotus | 217 | 2007-04-30 | 1201 | not_run |
| Kernel Records Oy v. Timothy Z. Mosley | 694 F.3d 1294 | circuit | 216 | 2012-09-14 | 302, 411 | not_run |
| S.O.S., Inc. v. Payday, Inc. | 886 F.2d 1081 | circuit | 215 | 1989-09-13 | 109, 201, 204, 301 | not_run |
| Perfect 10, Inc. v. Giganews, Inc. | 847 F.3d 657 | circuit | 215 | 2017-01-23 | 512 | not_run |
| Howard v. America Online Inc. | 208 F.3d 741 | circuit | 214 | 2000-03-29 | 204 | not_run |
| Hobby Lobby Stores, Inc. v. Sebelius | 723 F.3d 1114 | circuit | 214 | 2013-06-27 | 411 | not_run |
| Norman Birnbaum, B. Leonard Avery and Mary Rule MacMillen Pl | 588 F.2d 319 | circuit | 211 | 1978-11-09 | 301 | not_run |
| Roddenberry v. Roddenberry | 44 Cal. App. 4th 634 | other | 209 | 1996-04-16 | 204 | not_run |
| Tom Waits v. Frito-Lay, Inc. Tracy-Locke, Inc. | 978 F.2d 1093 | circuit | 205 | 1992-10-22 | 301 | not_run |
| Waldman Publishing Corp. And Playmore Inc., Publishers v. La | 43 F.3d 775 | circuit | 204 | 1994-12-22 | 201, 301 | not_run |
| I.A.E., Inc. v. Shaver | 74 F.3d 768 | circuit | 198 | 1996-01-17 | 204 | not_run |
| Marvel Characters, Inc. v. Kirby | 726 F.3d 119 | circuit | 195 | 2013-08-08 | 201, 203 | not_run |
| Simplexgrinnell Lp v. Integrated Systems & Power, Inc. | 642 F. Supp. 2d 206 | district | 194 | 2009-07-27 | 103 | not_run |
| Lakedreams, a Texas Partnership v. Steve Taylor, D/B/A Calif | 932 F.2d 1103 | circuit | 193 | 1991-06-11 | 201 | not_run |
| Downing v. Abercrombie & Fitch | 265 F.3d 994 | circuit | 192 | 2001-09-13 | 103 | not_run |
| Alcatel Usa, Inc., Plaintiff-Counter-Defendant-Appellee-Cros | 166 F.3d 772 | circuit | 189 | 1999-01-29 | 103 | not_run |
| Apple Computer, Inc. v. Microsoft Corp. | 35 F.3d 1435 | circuit | 179 | 1994-09-19 | 103 | not_run |
| Venegas-Hernandez v. Sonolux Records | 370 F.3d 183 | circuit | 177 | 2004-06-07 | 412 | not_run |
| Latimer v. Roaring Toyz, Inc. | 601 F.3d 1224 | circuit | 176 | 2010-04-02 | 103, 204 | not_run |
| Maljack Productions, Inc. v. Goodtimes Home Video Corp. | 81 F.3d 881 | circuit | 170 | 1996-04-17 | 103 | not_run |
| Sybersound Records, Inc. v. UAV Corp. | 517 F.3d 1137 | circuit | 167 | 2008-02-27 | 201 | not_run |
| Montgomery v. Noga | 168 F.3d 1282 | circuit | 163 | 1999-03-05 | 103, 412 | not_run |
| Craigslist, Inc. v. NATUREMARKET, INC. | 694 F. Supp. 2d 1039 | district | 163 | 2010-03-05 | 1201 | not_run |
| Eden Toys, Inc., Cross-Appellee v. Florelee Undergarment Co. | 697 F.2d 27 | circuit | 162 | 1982-12-02 | 103, 204, 412 | not_run |
| Perfect 10, Inc. v. Visa International Service, Ass'n | 494 F.3d 788 | circuit | 162 | 2007-07-03 | 512 | not_run |
| Davis v. Blige | 505 F.3d 90 | circuit | 158 | 2007-10-05 | 201, 204 | not_run |
| Nancey Silvers v. Sony Pictures Entertainment, Inc. | 402 F.3d 881 | circuit | 158 | 2005-03-25 | 201 | not_run |
| Cable/Home Communication Corp. v. Network Productions, Inc. | 902 F.2d 829 | circuit | 157 | 1990-06-04 | 412 | not_run |
| Universal City Studios, Inc. v. Corley | 273 F.3d 429 | circuit | 155 | 2001-11-28 | 1201 | not_run |
| Michael Baisden v. I'm Ready Productions, Inc., et | 693 F.3d 491 | circuit | 153 | 2012-08-31 | 103, 204 | not_run |
| BWP Media USA, Inc. v. T & S Software Associates., Inc. | 852 F.3d 436 | circuit | 152 | 2017-03-27 | 512 | not_run |
| Estate of Hevia v. Portrio Corp. | 602 F.3d 34 | circuit | 150 | 2010-04-20 | 204 | not_run |
| Gary Friedrich Enterprises, LLC v. Marvel Characters, Inc. | 716 F.3d 302 | circuit | 149 | 2013-06-11 | 201 | not_run |
| Stevens v. Corelogic, Inc. | 899 F.3d 666 | circuit | 149 | 2018-06-20 | 512, 1202 | not_run |
| Lexmark International, Inc. v. Static Control Components, In | 387 F.3d 522 | circuit | 149 | 2004-10-26 | 1201 | not_run |
| Kirtsaeng v. John Wiley & Sons, Inc. | 568 U.S. 519 | scotus | 148 | 2013-03-19 | 109 | not_run |
| Karen L. Erickson v. Trinity Theatre, Inc., Individually and | 13 F.3d 1061 | circuit | 147 | 1994-01-06 | 201, 302 | not_run |
| Mills Music, Inc. v. Snyder | 469 U.S. 153 | scotus | 145 | 1985-03-18 | 103, 115, 203 | not_run |
| Blueport Co., LLC v. United States | 533 F.3d 1374 | circuit | 140 | 2008-07-25 | 1201, 1202 | not_run |
| TD Bank NA v. Vernon Hill, II | 928 F.3d 259 | circuit | 139 | 2019-07-01 | 115, 201, 203, 204 | not_run |
| Davidson & Associates v. Jung | 422 F.3d 630 | circuit | 138 | 2005-09-01 | 1201 | not_run |
| Harris v. Emus Records Corp. | 734 F.2d 1329 | circuit | 137 | 1984-05-29 | 115 | not_run |
| M.G.B. Homes, Inc. v. Ameron Homes, Inc., and Daniel James B | 903 F.2d 1486 | circuit | 137 | 1990-06-25 | 412 | not_run |
| Barrett v. Rosenthal | 146 P.3d 510 | other | 137 | 2006-11-20 | 512 | not_run |
| Derek Andrew, Inc. v. Poof Apparel Corp. | 528 F.3d 696 | circuit | 134 | 2008-06-11 | 412 | not_run |
| Christopher Phelps & Associates, LLC v. Galloway | 492 F.3d 532 | circuit | 132 | 2007-07-05 | 103, 302 | not_run |
| Kip Rano v. Sipa Press, Inc., Sipa, Inc., Goskin Sipahioglu, | 987 F.2d 580 | circuit | 131 | 1993-03-24 | 203 | not_run |
| Bourne v. Walt Disney Co. | 68 F.3d 621 | circuit | 128 | 1995-10-18 | 109 | not_run |
| Bateman v. Mnemonics, Inc. | 79 F.3d 1532 | circuit | 127 | 1996-03-22 | 204 | not_run |
| DRK Photo v. McGraw-Hill Global Education Holdings, LLC | 870 F.3d 978 | circuit | 124 | 2017-09-12 | 204 | not_run |
| Neil Gaiman and Marvels and Miracles, Llc, Plaintiffs-Appell | 360 F.3d 644 | circuit | 124 | 2004-03-31 | 204 | not_run |
| Gamma Audio & Video, Inc. v. Ean-Chea D/B/A Overseas Video | 11 F.3d 1106 | circuit | 124 | 1993-12-22 | 412 | not_run |
| Lasercomb America, Inc. v. Job Reynolds Larry Holliday, and  | 911 F.2d 970 | circuit | 123 | 1990-09-27 | 302 | not_run |
| Stone v. Williams | 970 F.2d 1043 | circuit | 121 | 1992-07-13 | 203, 203, 302, 302 | not_run |
| Jane Doe No. 1 v. Backpage.Com, LLC | 817 F.3d 12 | circuit | 121 | 2016-03-14 | 412 | not_run |
| 16 Casa Duse, LLC v. Merkin | 791 F.3d 247 | circuit | 120 | 2015-06-29 | 412 | not_run |
| New York Times Co. v. Tasini | 533 U.S. 483 | scotus | 119 | 2001-06-25 | 108, 203 | not_run |
| Apple Inc. v. Psystar Corp. | 658 F.3d 1150 | circuit | 117 | 2011-09-28 | 109 | not_run |
| Horror Inc. v. Miller | 15 F.4th 232 | circuit | 117 | 2021-09-30 | 203 | not_run |
| Gerald Zuk v. Eastern Pennsylvania Psychiatric Institute of  | 103 F.3d 294 | circuit | 115 | 1996-12-31 | 109 | not_run |
| Lugosi v. Universal Pictures | 603 P.2d 425 | other | 114 | 1979-12-03 | 302 | not_run |
| John G. Danielson, Inc. v. Winchester-Conant Properties, Inc | 322 F.3d 26 | circuit | 107 | 2003-03-06 | 204 | not_run |
| The Chamberlain Group, Inc. v. Skylink Technologies, Inc. | 381 F.3d 1178 | circuit | 102 | 2004-10-22 | 1201 | not_run |
| MDY Industries, LLC v. Blizzard Entertainment, Inc. | 629 F.3d 928 | circuit | 102 | 2010-12-14 | 1201 | not_run |
| Abend v. MCA, Inc. | 863 F.2d 1465 | circuit | 101 | 1988-12-27 | 302 | not_run |
| Guzman v. Hacienda Records & Recording Studio, Inc. | 808 F.3d 1031 | circuit | 100 | 2015-12-14 | 1202 | not_run |
| Columbia Pictures Industries, Inc. v. Redd Horne, Inc. | 749 F.2d 154 | circuit | 97 | 1984-11-23 | 109 | not_run |
| Ground Zero Museum Workshop v. Wilson | 813 F. Supp. 2d 678 | district | 97 | 2011-11-04 | 1201 | not_run |
| Paice LLC v. Toyota Motor Corp. | 504 F.3d 1293 | circuit | 95 | 2007-10-18 | 115 | not_run |
| Media Rights Technologies, Inc v. Microsoft Corporation | 922 F.3d 1014 | circuit | 91 | 2019-05-02 | 1201 | not_run |
| DVD Copy Control Ass'n, Inc. v. Bunner | 75 P.3d 1 | other | 91 | 2003-10-15 | 1201 | not_run |
| Zalewski v. Cicero Builder Dev., Inc. | 754 F.3d 95 | circuit | 89 | 2014-06-05 | 1202 | not_run |
| Jacobus Rentmeester v. Nike, Inc. | 883 F.3d 1111 | circuit | 87 | 2018-02-27 | 1202 | not_run |
| Peer International Corp. v. Luna Records, Inc. | 887 F. Supp. 560 | district | 83 | 1995-04-28 | 115 | not_run |
| Stephanie Hays and Gail MacDonald v. Sony Corporation of Ame | 847 F.2d 412 | circuit | 82 | 1988-06-22 | 302 | not_run |
| London-Sire Records, Inc. v. Doe 1 | 542 F. Supp. 2d 153 | district | 80 | 2008-03-31 | 109, 115 | not_run |
| DIRECTV, Inc. v. Trone | 209 F.R.D. 455 | district | 80 | 2002-08-14 | 1201 | not_run |
| Martin's Herend Imports, Inc. v. Diamond & GEM Trading USA,  | 112 F.3d 1296 | circuit | 79 | 1997-05-28 | 109 | not_run |
| Fischer v. Forrest | 286 F. Supp. 3d 590 | district | 79 | 2018-02-16 | 1202 | not_run |
| Muhammad-Ali v. Final Call, Inc. | 832 F.3d 755 | circuit | 74 | 2016-08-10 | 109 | not_run |
| Video Pipeline, Inc. v. Buena Vista Home Entertainment, Inc. | 210 F. Supp. 2d 552 | district | 74 | 2002-07-26 | 109 | not_run |
| Golan v. Holder | 565 U.S. 302 | scotus | 73 | 2012-01-18 | 302 | not_run |
| Quality King Distributors, Inc. v. L'Anza Research Internati | 523 U.S. 135 | scotus | 72 | 1998-03-09 | 109 | not_run |
| Authors Guild, Inc. v. HathiTrust | 755 F.3d 87 | circuit | 71 | 2014-06-10 | 108 | not_run |
| St. Luke's Cataract & Laser Institute. P.A. v. Sanderson | 573 F.3d 1186 | circuit | 70 | 2009-07-09 | 1202 | not_run |
| Vault Corporation v. Quaid Software Limited | 847 F.2d 255 | circuit | 68 | 1988-06-20 | 108, 302 | not_run |
| Veronica Vincent v. City Colleges of Chicago, Ezekiel Morris | 485 F.3d 919 | circuit | 66 | 2007-04-30 | 109 | not_run |
| Polar Bear Productions, Inc., a Montana Corporation v. Timex | 384 F.3d 700 | circuit | 66 | 2004-10-25 | 1202 | not_run |
| Stephanie Lenz v. Universal Music Corp. | 815 F.3d 1145 | circuit | 65 | 2016-03-17 | 108 | not_run |
| Brilliance Audio, Inc. v. Haights Cross Communications, Inc. | 474 F.3d 365 | circuit | 64 | 2007-01-26 | 109 | not_run |
| Clare Milne, by and Through Michael Joseph Coyne, Her Receiv | 430 F.3d 1036 | circuit | 64 | 2005-12-08 | 203, 302 | not_run |
| Personal Keepsakes, Inc. v. Personalizationmall.com, Inc. | 975 F. Supp. 2d 920 | district | 63 | 2013-09-24 | 1202 | not_run |
| Friedman v. Live Nation Merchandise, Inc. | 833 F.3d 1180 | circuit | 63 | 2016-08-18 | 1202 | not_run |
| Baldwin v. EMI Feist Catalog, Inc. | 805 F.3d 18 | circuit | 61 | 2015-10-08 | 203 | not_run |
| Bretford Manufacturing, Inc. v. Smith System Manufacturing C | 419 F.3d 576 | circuit | 59 | 2005-08-08 | 106A | not_run |
| Donna R. Hotaling William W. Hotaling, Jr. James P. Maher Do | 118 F.3d 199 | circuit | 59 | 1997-06-30 | 108 | not_run |
| Giordano v. Claudio | 714 F. Supp. 2d 508 | district | 55 | 2010-05-14 | 106A | not_run |
| International Korwin Corp. v. Tadeusz Kowalczyk | 855 F.2d 375 | circuit | 54 | 1988-08-16 | 110 | not_run |
| Abkco Music, Inc. And Abkco Music and Records, Inc. v. Stell | 96 F.3d 60 | circuit | 54 | 1996-09-19 | 115 | not_run |
| Mango v. Buzzfeed, Inc. | 356 F. Supp. 3d 368 | district | 54 | 2019-01-17 | 1202 | not_run |
| EMI April Music, Inc. v. White | 618 F. Supp. 2d 497 | district | 52 | 2009-05-22 | 110 | not_run |
| Community for Creative Non-Violence v. James Earl Reid | 846 F.2d 1485 | circuit | 52 | 1988-05-31 | 203, 302 | not_run |
| Mango v. Buzzfeed, Inc. | 970 F.3d 167 | circuit | 50 | 2020-08-13 | 1202 | not_run |
| Carter v. Helmsley-Spear, Inc. | 71 F.3d 77 | circuit | 48 | 1995-12-01 | 106A | not_run |
| Ronald Louis Smith, Jr. v. Harry Wayne Casey | 741 F.3d 1236 | circuit | 48 | 2014-01-22 | 203 | not_run |
| Vacheron & Constantin-Le Coultre Watches, Inc. v. Benrus Wat | 260 F.2d 637 | circuit | 47 | 1958-10-21 | 115 | not_run |
| Cyril Russell, Etc. v. Daniel A. Price, and Albert C. Drebin | 612 F.2d 1123 | circuit | 47 | 1980-02-19 | 203 | not_run |
| Capitol Records, LLC v. Bluebeat, Inc. | 765 F. Supp. 2d 1198 | district | 47 | 2010-12-08 | 1202 | not_run |
| Dielsi v. Falk | 916 F. Supp. 985 | district | 45 | 1996-01-23 | 106A | not_run |
| Philadelphia Eagles Football Club, Inc. v. City of Philadelp | 573 Pa. 189 | other | 43 | 2003-04-25 | 203 | not_run |
| BanxCorp v. Costco Wholesale Corp. | 723 F. Supp. 2d 596 | district | 40 | 2010-07-14 | 1202 | not_run |
| Joanne Pollara v. Joseph J. Seymour and Thomas E. Casey, Joh | 344 F.3d 265 | circuit | 36 | 2003-09-19 | 106A | not_run |
| Castillo v. G&M Realty L.P. | 950 F.3d 155 | circuit | 33 | 2020-02-20 | 106A | not_run |
| Maharishi Hardy Blechman Ltd. v. Abercrombie & Fitch Co. | 292 F. Supp. 2d 535 | district | 30 | 2003-12-08 | 106A | not_run |
| Universal City Studios, Inc. v. Sony Corp. of America | 480 F. Supp. 429 | district | 28 | 1979-12-05 | 108 | not_run |
| Jan Randolph Martin, Plaintiff-Appellee/cross-Appellant v. C | 192 F.3d 608 | circuit | 26 | 1999-08-31 | 106A | not_run |
| Massachusetts Museum of Contemporary Art Foundation, Inc. v. | 593 F.3d 38 | circuit | 26 | 2010-01-27 | 106A | not_run |
| Fahmy v. Jay-Z | 908 F.3d 383 | circuit | 25 | 2018-05-31 | 106A | not_run |
| Simon Cheffins v. Michael Stewart | 825 F.3d 588 | circuit | 24 | 2016-06-08 | 106A | not_run |
| Annie Lee and Annie Lee & Friends Company, Inc. v. A.R.T. Co | 125 F.3d 580 | circuit | 24 | 1997-09-18 | 106A | not_run |
| International Korwin Corp. v. Kowalczyk | 665 F. Supp. 652 | district | 24 | 1987-07-01 | 110 | not_run |
| Dsc Communications Corporation v. Pulse Communications, Inc. | 170 F.3d 1354 | circuit | 20 | 1999-03-11 | 108 | not_run |
| Swallow Turn Music v. Wilson | 831 F. Supp. 575 | district | 20 | 1993-08-31 | 110 | not_run |
| Cass County Music Company v. Vasfi Muedini D/B/A Port Town F | 55 F.3d 263 | circuit | 19 | 1995-05-16 | 110 | not_run |
| T.B. Harms Co. v. Jem Records, Inc. | 655 F. Supp. 1575 | district | 18 | 1987-03-26 | 108 | not_run |
| Broadcast Music, Inc. v. Niro's Palace, Inc. | 619 F. Supp. 958 | district | 15 | 1985-05-28 | 110 | not_run |
| Encyclopaedia Britannica Educational Corp. v. Crooks | 447 F. Supp. 243 | district | 15 | 1978-02-27 | 110 | not_run |
| Disney Enterprises, Inc. v. VidAngel, Inc. | 224 F. Supp. 3d 957 | district | 14 | 2016-12-12 | 110 | not_run |
| Hickory Grove Music v. Andrews | 749 F. Supp. 1031 | district | 14 | 1990-09-13 | 110 | not_run |
| Sailor Music v. The Gap Stores, Inc. | 668 F.2d 84 | circuit | 14 | 1981-12-15 | 110 | not_run |
| Hachette Book Group, Inc. v. Internet Archive | 115 F.4th 163 | circuit | 13 | 2024-09-04 | 108 | not_run |
| Golan v. Gonzales | 501 F.3d 1179 | circuit | 11 | 2007-09-04 | 108 | not_run |
| Association of American Medical Colleges v. Carey | 728 F. Supp. 873 | district | 10 | 1990-01-12 | 108 | not_run |
| Pacific and Southern Co., Inc. v. Duncan | 572 F. Supp. 1186 | district | 9 | 1983-10-13 | 108 | not_run |

### UPDATE — existing cases (old → new)

- [51] Carter v. Helmsley-Spear, Inc.: court_level: None → 'district' · status: 'in_force' → 'unknown'
- [59] American Geophysical Union v. Texaco Inc.: court_level: None → 'circuit' · status: 'in_force' → 'unknown'
- [59] American Geophysical Union v. Texaco Inc.: court_level: None → 'circuit' · status: 'in_force' → 'unknown'
- [52] Worldwide Church Of God v. Philadelphia Church Of God, Inc.: court_level: None → 'circuit' · status: 'in_force' → 'unknown'
- [52] Worldwide Church Of God v. Philadelphia Church Of God, Inc.: court_level: None → 'circuit' · status: 'in_force' → 'unknown'
- [67] Kelly v. L.L. Cool J.: court_level: None → 'district' · status: 'in_force' → 'unknown'
- [66] Palladium Music, Inc. v. Eatsleepmusic, Inc.: court_level: None → 'circuit' · status: 'in_force' → 'unknown'

### KEEP (below cap) — true links outside the new top-N, verified still in CourtListener's results; KEPT by policy

- [33] Situation Management Systems v. ASP Consulting Group → § 102
- [34] Windgate Software, L.L.C. v. Minnesota Computers, Inc. → § 102
- [35] State ex rel. McNew v. Ohio Dept. of Rehab. & Corr. → § 102
- [36] Oracle America, Inc. v. Google Inc. → § 102
- [37] Zitz v. Bernadino Dos Santos → § 102
- [38] Tasini v. The New York Times Company, Inc. → § 103
- [39] Ryan v. Carl Corp. → § 103
- [40] Gamma v. Ean-Chea → § 103
- [42] Dream Custom Homes, Inc. v. Modern Day Construction, Inc. → § 103
- [43] First World Architects Studio, PSC v. McGhee → § 106
- [44] TruLogic, Inc. v. Gen. Elec. Co. → § 106
- [45] Southern Credentialing Support v. Hammond Surgical → § 106
- [46] Berrios Nogueras v. Home Depot → § 106
- [47] Excel Homes, Inc. v. Locricchio → § 106
- [48] Hunter v. Squirrel Hill Associates, L.P. → § 106A
- [49] Pavia v. 1120 Avenue of the Americas Associates → § 106A
- [50] Flack v. Friends of Queen Catherine Inc. → § 106A
- [52] Worldwide Church Of God v. Philadelphia Church Of God, Inc. → § 107
- [53] Raanan Katz v. Irina Chevaldina → § 107
- [54] State ex rel. Gambill v. Opperman → § 107
- [55] Peterman v. Republican Nat'l Comm. → § 107
- [56] Smithkline Beecham Consumer Healthcare, L.P., Plaintiffappellant v. Wa → § 107
- [57] Authors Guild, Inc. v. Hathitrust → § 108
- [58] Whether Government Reproduction of Copyrighted Materials is a Noninfri → § 108
- [60] American Geophysical Union v. Texaco Inc. → § 108
- [62] Schwartz-Liebman Textiles v. Last Exit Corp. → § 109
- [63] Apple, Inc. v. Psystar Corp. → § 109
- [64] Softman Products Co., LLC v. Adobe Systems, Inc. → § 109
- [65] In Re Valley Media, Inc. → § 109
- [68] Yesh Music, LLC v. Amazon.com, Inc. → § 115
- [38] Tasini v. The New York Times Company, Inc. → § 201
- [69] Sisyphus Touring, Inc. v. TMZ Productions, Inc. → § 201
- [70] Forward v. Thorogood → § 201
- [71] Recht v. METRO GOLDWYN MAYER STUDIO, INC. → § 201
- [73] Harry Wayne Casey v. Richard R. Finch → § 203
- [74] Tammy Livingston v. Jay Livingston Music, Inc. → § 203
- [69] Sisyphus Touring, Inc. v. TMZ Productions, Inc. → § 204
- [75] Conwell v. Gray Loon Outdoor Marketing Group, Inc. → § 204
- [76] Tiffany Design, Inc. v. Reno-Tahoe Specialty, Inc. → § 204
- [77] Metropolitan Regional Information Systems, Inc. v. American Home Realt → § 204
- [78] Thornton v. J Jargon Co. → § 204
- [43] First World Architects Studio, PSC v. McGhee → § 301
- [44] TruLogic, Inc. v. Gen. Elec. Co. → § 301
- [79] Cheng v. Haney → § 301
- [80] Capitol Records, Inc. v. Mp3tunes, LLC → § 301
- [81] Zito v. Steeplechase Films, Inc. → § 301
- [82] Rodrigue v. Rodrigue → § 302
- [83] Kroni Inc. v. Kohler Company → § 302
- [43] First World Architects Studio, PSC v. McGhee → § 411
- [84] Derminer v. Kramer → § 411
- [85] Precision Automation, Inc. v. Technical Services, Inc. → § 411
- [86] Raquel, a Partnership v. Education Management Corporation Art Institut → § 411
- [87] Centurion Wireless Technologies, Inc. v. Hop-On Communications, Inc. → § 411
- [43] First World Architects Studio, PSC v. McGhee → § 412
- [45] Southern Credentialing Support v. Hammond Surgical → § 412
- [88] Loree Rodkin Management Corp. v. Ross-Simons, Inc. → § 412
- [89] Pavlica v. Behr → § 412
- [90] Coton v. Televised Visual X-Ography, Inc. → § 412
- [91] Amini Innovation Corp. v. KTY International Marketing → § 504
- [90] Coton v. Televised Visual X-Ography, Inc. → § 504
- [92] Alaska Stock, LLC v. Pearson Education, Inc. → § 504
- [93] The Cambridge Institute, Inc., Plaintiff-Cross-Defendant-Appellee v. T → § 504
- [94] Clever Covers, Inc. v. Southwest Florida Storm Defense, LLC → § 504

## corpus.db

ADD 224 new cases carrying 321 section links + 0 new links to existing cases · UPDATE 9 · KEEP 9 · KEEP-below-cap 82 · REMOVE 0 · MANUAL 0

### ADD — new cases (one row per case; §§ = every section it topped)

| Case | Cite | Court | citeCount | Filed | §§ | Screen |
|---|---|---|---|---|---|---|
| Chambers v. Time Warner, Inc. | 282 F.3d 147 | circuit | 4257 | 2002-02-21 | 106, 501 | not_run |
| Arista Records, LLC v. Doe 3 | 604 F.3d 110 | circuit | 2828 | 2010-04-29 | 106 | not_run |
| Lexmark Int'l, Inc. v. Static Control Components, Inc. | 572 U.S. 118 | scotus | 2774 | 2014-03-25 | 1201 | not_run |
| Feist Publications, Inc. v. Rural Telephone Service Co. | 499 U.S. 340 | scotus | 2736 | 1991-03-27 | 102 | not_run |
| Cipollone v. Liggett Group, Inc. | 505 U.S. 504 | scotus | 2642 | 1992-06-24 | 301 | not_run |
| Gasperini v. Center for Humanities, Inc. | 518 U.S. 415 | scotus | 1870 | 1996-06-24 | 302 | not_run |
| Fogerty v. Fantasy, Inc. | 510 U.S. 517 | scotus | 1804 | 1994-03-01 | 505 | not_run |
| Harper & Row, Publishers, Inc. v. Nation Enterprises | 471 U.S. 539 | scotus | 1200 | 1985-05-20 | 102, 106, 107, 115, 504 | not_run |
| Community for Creative Non-Violence v. Reid | 490 U.S. 730 | scotus | 1160 | 1989-06-05 | 201, 301 | not_run |
| City of New York v. Mickalis Pawn Shop, LLC | 645 F.3d 114 | circuit | 1157 | 2011-05-04 | 411 | not_run |
| Bank of the West v. Superior Court | 833 P.2d 545 | other | 1058 | 1992-07-30 | 106 | not_run |
| Sony Corp. of America v. Universal City Studios, Inc. | 464 U.S. 417 | scotus | 992 | 1984-01-17 | 102, 107, 411, 501 | not_run |
| Professional Real Estate Investors, Inc. v. Columbia Picture | 508 U.S. 49 | scotus | 962 | 1993-05-03 | 106, 109 | not_run |
| Marek v. Chesny | 473 U.S. 1 | scotus | 926 | 1985-06-27 | 505 | not_run |
| Leadsinger, Inc. v. BMG Music Publishing | 512 F.3d 522 | circuit | 903 | 2008-01-02 | 102, 106, 107, 115 | not_run |
| Reed Elsevier, Inc. v. Muchnick | 559 U.S. 154 | scotus | 754 | 2010-03-02 | 102, 411, 412 | not_run |
| TechnoMarine SA v. Giftports, Inc. | 758 F.3d 493 | circuit | 723 | 2014-07-15 | 501 | not_run |
| Bouchat v. Baltimore Ravens Football Club, Inc. | 346 F.3d 514 | circuit | 698 | 2003-10-08 | 412, 412, 504 | not_run |
| Edward H. Bohlin Co., Inc. v. Banning Co., Inc. | 6 F.3d 350 | circuit | 675 | 1993-11-10 | 501 | not_run |
| Dudnikov v. Chalk & Vermilion Fine Arts, Inc. | 514 F.3d 1063 | circuit | 660 | 2008-01-28 | 107, 512 | not_run |
| Campbell v. Acuff-Rose Music, Inc. | 510 U.S. 569 | scotus | 635 | 1994-03-07 | 106, 107 | not_run |
| Mavrix Photo, Inc. v. Brand Technologies, Inc. | 647 F.3d 1218 | circuit | 604 | 2011-08-08 | 501 | not_run |
| Cindy Garcia v. Google, Inc. | 786 F.3d 733 | circuit | 597 | 2015-05-18 | 102, 106A, 201, 203, 512 | not_run |
| Fantasy, Inc. v. Fogerty | 984 F.2d 1524 | circuit | 575 | 1993-02-02 | 505 | not_run |
| Metro-Goldwyn-Mayer Studios Inc. v. Grokster, Ltd. | 545 U.S. 913 | scotus | 547 | 2005-06-27 | 504 | not_run |
| Marder v. Lopez | 450 F.3d 445 | circuit | 535 | 2006-06-12 | 106 | not_run |
| Briarpatch Limited, L.P., Gerard F. Rubin v. Phoenix Picture | 373 F.3d 296 | circuit | 534 | 2004-06-25 | 102, 103, 106, 301 | not_run |
| Regan v. Time, Inc. | 468 U.S. 641 | scotus | 510 | 1984-07-03 | 106 | not_run |
| Arista Records LLC v. John Does 1-19 | 551 F. Supp. 2d 1 | district | 509 | 2008-04-28 | 512 | not_run |
| A&M Records, Inc. v. Napster, Inc. | 239 F.3d 1004 | circuit | 496 | 2001-02-12 | 106, 107, 115, 501, 512 | not_run |
| Dastar Corp. v. Twentieth Century Fox Film Corp. | 539 U.S. 23 | scotus | 493 | 2003-06-02 | 102, 106A | not_run |
| Penguin Group (USA) Inc. v. American Buddha | 609 F.3d 30 | circuit | 481 | 2010-06-15 | 501 | not_run |
| Darrell J. Bird v. Marshall Parsons, Stephen Vincent, George | 289 F.3d 865 | circuit | 479 | 2002-05-21 | 106 | not_run |
| Anthony Dash v. Floyd Mayweather, Jr. | 731 F.3d 303 | circuit | 473 | 2013-09-26 | 504 | not_run |
| Salinger v. Colting | 607 F.3d 68 | circuit | 463 | 2010-04-30 | 107 | not_run |
| Phillips v. Audio Active Ltd. | 494 F.3d 378 | circuit | 451 | 2007-07-24 | 504 | not_run |
| Petrella v. Metro-Goldwyn-Mayer, Inc. | 572 U.S. 663 | scotus | 442 | 2014-05-19 | 115, 504 | not_run |
| Brownmark Films, LLC v. Comedy Partners | 682 F.3d 687 | circuit | 427 | 2012-06-07 | 107 | not_run |
| Axiom Foods, Inc. v. Acerchem International, Inc. | 874 F.3d 1064 | circuit | 427 | 2017-11-01 | 501 | not_run |
| Therasense, Inc. v. Becton, Dickinson and Co. | 649 F.3d 1276 | circuit | 425 | 2011-05-25 | 411 | not_run |
| Nola Spice Designs, L.L.C. v. Haydel Enterprises, Inc. | 783 F.3d 527 | circuit | 420 | 2015-04-08 | 102 | not_run |
| Computer Associates International, Inc., Plaintiff-Appellant | 982 F.2d 693 | circuit | 411 | 1992-12-17 | 102, 106, 301 | not_run |
| Lloyd Lieb, Trading as Specialized Cassettes v. Topstone Ind | 788 F.2d 151 | circuit | 404 | 1986-04-14 | 505 | not_run |
| Warren v. Fox Family Worldwide, Inc. | 328 F.3d 1136 | circuit | 398 | 2003-05-13 | 201, 501 | not_run |
| Harris v. Garner | 216 F.3d 970 | circuit | 392 | 2000-06-27 | 411, 411 | not_run |
| Feltner v. Columbia Pictures Television, Inc. | 523 U.S. 340 | scotus | 376 | 1998-03-31 | 504 | not_run |
| Progressive Animal Welfare Society v. University of Washingt | 884 P.2d 592 | other | 373 | 1994-11-22 | 106 | not_run |
| Securacomm Consulting, Inc. v. Securacom Inc. | 224 F.3d 273 | circuit | 364 | 2000-08-21 | 505 | not_run |
| MAI Systems Corp. v. Peak Computer, Inc. | 991 F.2d 511 | circuit | 359 | 1993-04-07 | 106 | not_run |
| Yurman Design, Inc. Plaintiff-Appellee-Cross-Appellant v. Pa | 262 F.3d 101 | circuit | 358 | 2001-08-10 | 102, 103, 504 | not_run |
| Perfect 10, Inc. v. Amazon. Com, Inc. | 508 F.3d 1146 | circuit | 345 | 2007-12-03 | 107, 411, 501, 512 | not_run |
| Ellison v. Robertson | 357 F.3d 1072 | circuit | 342 | 2004-02-10 | 501, 512 | not_run |
| Knitwaves, Inc., Plaintiff-Appellee-Cross-Appellant v. Lolly | 71 F.3d 996 | circuit | 337 | 1995-11-13 | 412, 504, 505 | not_run |
| Thomas Walker v. Time Life Films, Inc., David Susskind, Gill | 784 F.2d 44 | circuit | 334 | 1986-01-07 | 102, 301 | not_run |
| Humphreys & Partners Architects v. Lessard Design, Incorpora | 790 F.3d 532 | circuit | 329 | 2015-06-23 | 102 | not_run |
| Durham Industries, Inc. v. Tomy Corporation | 630 F.2d 905 | circuit | 328 | 1980-09-02 | 102, 103, 301 | not_run |
| Stewart v. Abend | 495 U.S. 207 | scotus | 323 | 1990-04-24 | 103, 107 | not_run |
| Data General Corp. v. Grumman Systems Support Corp. | 36 F.3d 1147 | circuit | 322 | 1994-09-15 | 102, 301, 411, 504 | not_run |
| Tewarson v. Simon | 750 N.E.2d 176 | other | 308 | 2001-01-03 | 301 | not_run |
| Elektra Entertainment Group Inc. v. Crawford | 226 F.R.D. 388 | district | 307 | 2005-02-11 | 501, 504, 505 | not_run |
| Image Software, Inc. v. Reynolds & Reynolds Co. | 459 F.3d 1044 | circuit | 307 | 2006-08-23 | 501 | not_run |
| Strike 3 Holdings, LLC v. John Doe | 964 F.3d 1203 | circuit | 307 | 2020-07-14 | 512 | not_run |
| Lipton v. Nature Co. | 71 F.3d 464 | circuit | 303 | 1995-11-28 | 501, 504 | not_run |
| Castle Rock Entertainment, Inc. v. Carol Publishing Group, I | 150 F.3d 132 | circuit | 302 | 1998-07-10 | 107 | not_run |
| Carruthers v. Carrier Access Corp. | 251 P.3d 1199 | other | 301 | 2010-10-28 | 505 | not_run |
| Adriana International Corp. v. Thoeren | 913 F.2d 1406 | circuit | 300 | 1990-09-10 | 501 | not_run |
| Batzel v. Smith | 333 F.3d 1018 | circuit | 291 | 2003-06-24 | 512, 512 | not_run |
| Disney Enterprises, Inc. v. Vidangel, Inc. | 869 F.3d 848 | circuit | 290 | 2017-08-24 | 107, 109, 110, 1201 | not_run |
| Harolds Stores, Inc. v. Dillard Department Stores, Inc. | 82 F.3d 1533 | circuit | 281 | 1996-05-03 | 301, 412 | not_run |
| Baker & Hostetler LLP v. United States Department of Commerc | 473 F.3d 312 | circuit | 270 | 2006-12-22 | 505 | not_run |
| Dowling v. United States | 473 U.S. 207 | scotus | 269 | 1985-06-28 | 115 | not_run |
| The Gates Rubber Co. v. Bando Chemical Industries, Ltd. | 9 F.3d 823 | circuit | 266 | 1993-10-19 | 301 | not_run |
| Barefoot Architect, Inc. v. Bunge | 632 F.3d 822 | circuit | 264 | 2011-01-14 | 201, 204 | not_run |
| Fourth Estate Pub. Benefit Corp. v. Wall-Street.com, LLC | 586 U.S. 296 | scotus | 257 | 2019-03-04 | 411 | not_run |
| Smith v. Jackson | 84 F.3d 1213 | circuit | 248 | 1996-06-05 | 505 | not_run |
| Umg Recordings, Inc. v. Shelter Capital Partners Llc | 718 F.3d 1006 | circuit | 245 | 2013-03-14 | 505, 512, 1201 | not_run |
| Darrell Taylor, D/B/A Darrell Taylor Topographic Charts v. J | 712 F.2d 1112 | circuit | 243 | 1983-07-07 | 504, 505 | not_run |
| Art Rogers, Plaintiff-Appellee-Cross-Appellant v. Jeff Koons | 960 F.2d 301 | circuit | 237 | 1992-04-02 | 107, 504 | not_run |
| TWENTIETH CENTURY MUSIC CORP. Et Al. v. AIKEN | 422 U.S. 151 | scotus | 235 | 1975-06-17 | 110 | not_run |
| Spinelli v. National Football League | 903 F.3d 185 | circuit | 235 | 2018-09-11 | 1202 | not_run |
| ProCD, Inc. v. Zeidenberg | 86 F.3d 1447 | circuit | 233 | 1996-06-20 | 301 | not_run |
| Chicago Building Design, P.C. v. Mongolian House, Inc. | 770 F.3d 610 | circuit | 233 | 2014-10-23 | 504 | not_run |
| Lyons Partnership, L.P., a Texas Limited Partnership v. Morr | 243 F.3d 789 | circuit | 232 | 2001-03-16 | 505 | not_run |
| Israel Santiago-Lugo v. Warden | 785 F.3d 467 | circuit | 231 | 2015-04-30 | 411 | not_run |
| Rimini Street, Inc. v. Oracle USA, Inc. | 586 U.S. 334 | scotus | 228 | 2019-03-04 | 505 | not_run |
| On Davis v. The Gap, Inc. | 246 F.3d 152 | circuit | 227 | 2001-04-10 | 107, 412 | not_run |
| Lotes Co. v. Hon Hai Precision Industry Co. | 753 F.3d 395 | circuit | 227 | 2014-06-04 | 411 | not_run |
| Psihoyos v. John Wiley & Sons, Inc. | 748 F.3d 120 | circuit | 227 | 2014-04-04 | 411 | not_run |
| Eldred v. Ashcroft | 537 U.S. 186 | scotus | 226 | 2003-01-15 | 107, 108, 110, 302 | not_run |
| Kirtsaeng v. John Wiley & Sons, Inc. | 579 U.S. 197 | scotus | 225 | 2016-06-16 | 505 | not_run |
| James W. Cleary v. News Corporation and Harpercollins Publis | 30 F.3d 1255 | circuit | 221 | 1994-08-01 | 201 | not_run |
| James Owens v. Republic of Sudan | 864 F.3d 751 | circuit | 219 | 2017-07-28 | 411 | not_run |
| Microsoft Corp. v. At&t Corp. | 550 U.S. 437 | scotus | 217 | 2007-04-30 | 1201 | not_run |
| Kernel Records Oy v. Timothy Z. Mosley | 694 F.3d 1294 | circuit | 216 | 2012-09-14 | 302, 411 | not_run |
| S.O.S., Inc. v. Payday, Inc. | 886 F.2d 1081 | circuit | 215 | 1989-09-13 | 109, 201, 204, 301 | not_run |
| Perfect 10, Inc. v. Giganews, Inc. | 847 F.3d 657 | circuit | 215 | 2017-01-23 | 512 | not_run |
| Howard v. America Online Inc. | 208 F.3d 741 | circuit | 214 | 2000-03-29 | 204 | not_run |
| Hobby Lobby Stores, Inc. v. Sebelius | 723 F.3d 1114 | circuit | 214 | 2013-06-27 | 411 | not_run |
| Norman Birnbaum, B. Leonard Avery and Mary Rule MacMillen Pl | 588 F.2d 319 | circuit | 211 | 1978-11-09 | 301 | not_run |
| Roddenberry v. Roddenberry | 44 Cal. App. 4th 634 | other | 209 | 1996-04-16 | 204 | not_run |
| Tom Waits v. Frito-Lay, Inc. Tracy-Locke, Inc. | 978 F.2d 1093 | circuit | 205 | 1992-10-22 | 301 | not_run |
| Waldman Publishing Corp. And Playmore Inc., Publishers v. La | 43 F.3d 775 | circuit | 204 | 1994-12-22 | 201, 301 | not_run |
| I.A.E., Inc. v. Shaver | 74 F.3d 768 | circuit | 198 | 1996-01-17 | 204 | not_run |
| Marvel Characters, Inc. v. Kirby | 726 F.3d 119 | circuit | 195 | 2013-08-08 | 201, 203 | not_run |
| Simplexgrinnell Lp v. Integrated Systems & Power, Inc. | 642 F. Supp. 2d 206 | district | 194 | 2009-07-27 | 103 | not_run |
| Lakedreams, a Texas Partnership v. Steve Taylor, D/B/A Calif | 932 F.2d 1103 | circuit | 193 | 1991-06-11 | 201 | not_run |
| Downing v. Abercrombie & Fitch | 265 F.3d 994 | circuit | 192 | 2001-09-13 | 103 | not_run |
| Alcatel Usa, Inc., Plaintiff-Counter-Defendant-Appellee-Cros | 166 F.3d 772 | circuit | 189 | 1999-01-29 | 103 | not_run |
| Apple Computer, Inc. v. Microsoft Corp. | 35 F.3d 1435 | circuit | 179 | 1994-09-19 | 103 | not_run |
| Venegas-Hernandez v. Sonolux Records | 370 F.3d 183 | circuit | 177 | 2004-06-07 | 412 | not_run |
| Latimer v. Roaring Toyz, Inc. | 601 F.3d 1224 | circuit | 176 | 2010-04-02 | 103, 204 | not_run |
| Maljack Productions, Inc. v. Goodtimes Home Video Corp. | 81 F.3d 881 | circuit | 170 | 1996-04-17 | 103 | not_run |
| Sybersound Records, Inc. v. UAV Corp. | 517 F.3d 1137 | circuit | 167 | 2008-02-27 | 201 | not_run |
| Montgomery v. Noga | 168 F.3d 1282 | circuit | 163 | 1999-03-05 | 103, 412 | not_run |
| Craigslist, Inc. v. NATUREMARKET, INC. | 694 F. Supp. 2d 1039 | district | 163 | 2010-03-05 | 1201 | not_run |
| Eden Toys, Inc., Cross-Appellee v. Florelee Undergarment Co. | 697 F.2d 27 | circuit | 162 | 1982-12-02 | 103, 204, 412 | not_run |
| Perfect 10, Inc. v. Visa International Service, Ass'n | 494 F.3d 788 | circuit | 162 | 2007-07-03 | 512 | not_run |
| Davis v. Blige | 505 F.3d 90 | circuit | 158 | 2007-10-05 | 201, 204 | not_run |
| Nancey Silvers v. Sony Pictures Entertainment, Inc. | 402 F.3d 881 | circuit | 158 | 2005-03-25 | 201 | not_run |
| Cable/Home Communication Corp. v. Network Productions, Inc. | 902 F.2d 829 | circuit | 157 | 1990-06-04 | 412 | not_run |
| Universal City Studios, Inc. v. Corley | 273 F.3d 429 | circuit | 155 | 2001-11-28 | 1201 | not_run |
| Michael Baisden v. I'm Ready Productions, Inc., et | 693 F.3d 491 | circuit | 153 | 2012-08-31 | 103, 204 | not_run |
| BWP Media USA, Inc. v. T & S Software Associates., Inc. | 852 F.3d 436 | circuit | 152 | 2017-03-27 | 512 | not_run |
| Estate of Hevia v. Portrio Corp. | 602 F.3d 34 | circuit | 150 | 2010-04-20 | 204 | not_run |
| Gary Friedrich Enterprises, LLC v. Marvel Characters, Inc. | 716 F.3d 302 | circuit | 149 | 2013-06-11 | 201 | not_run |
| Stevens v. Corelogic, Inc. | 899 F.3d 666 | circuit | 149 | 2018-06-20 | 512, 1202 | not_run |
| Kirtsaeng v. John Wiley & Sons, Inc. | 568 U.S. 519 | scotus | 148 | 2013-03-19 | 109 | not_run |
| Karen L. Erickson v. Trinity Theatre, Inc., Individually and | 13 F.3d 1061 | circuit | 147 | 1994-01-06 | 201, 302 | not_run |
| Mills Music, Inc. v. Snyder | 469 U.S. 153 | scotus | 145 | 1985-03-18 | 103, 115, 203 | not_run |
| Blueport Co., LLC v. United States | 533 F.3d 1374 | circuit | 140 | 2008-07-25 | 1201, 1202 | not_run |
| TD Bank NA v. Vernon Hill, II | 928 F.3d 259 | circuit | 139 | 2019-07-01 | 115, 201, 203, 204 | not_run |
| Davidson & Associates v. Jung | 422 F.3d 630 | circuit | 138 | 2005-09-01 | 1201 | not_run |
| Harris v. Emus Records Corp. | 734 F.2d 1329 | circuit | 137 | 1984-05-29 | 115 | not_run |
| M.G.B. Homes, Inc. v. Ameron Homes, Inc., and Daniel James B | 903 F.2d 1486 | circuit | 137 | 1990-06-25 | 412 | not_run |
| Barrett v. Rosenthal | 146 P.3d 510 | other | 137 | 2006-11-20 | 512 | not_run |
| Derek Andrew, Inc. v. Poof Apparel Corp. | 528 F.3d 696 | circuit | 134 | 2008-06-11 | 412 | not_run |
| Christopher Phelps & Associates, LLC v. Galloway | 492 F.3d 532 | circuit | 132 | 2007-07-05 | 103, 302 | not_run |
| Kip Rano v. Sipa Press, Inc., Sipa, Inc., Goskin Sipahioglu, | 987 F.2d 580 | circuit | 131 | 1993-03-24 | 203 | not_run |
| Bourne v. Walt Disney Co. | 68 F.3d 621 | circuit | 128 | 1995-10-18 | 109 | not_run |
| Bateman v. Mnemonics, Inc. | 79 F.3d 1532 | circuit | 127 | 1996-03-22 | 204 | not_run |
| DRK Photo v. McGraw-Hill Global Education Holdings, LLC | 870 F.3d 978 | circuit | 124 | 2017-09-12 | 204 | not_run |
| Neil Gaiman and Marvels and Miracles, Llc, Plaintiffs-Appell | 360 F.3d 644 | circuit | 124 | 2004-03-31 | 204 | not_run |
| Gamma Audio & Video, Inc. v. Ean-Chea D/B/A Overseas Video | 11 F.3d 1106 | circuit | 124 | 1993-12-22 | 412 | not_run |
| Lasercomb America, Inc. v. Job Reynolds Larry Holliday, and  | 911 F.2d 970 | circuit | 123 | 1990-09-27 | 302 | not_run |
| Stone v. Williams | 970 F.2d 1043 | circuit | 121 | 1992-07-13 | 203, 203, 302, 302 | not_run |
| Jane Doe No. 1 v. Backpage.Com, LLC | 817 F.3d 12 | circuit | 121 | 2016-03-14 | 412 | not_run |
| 16 Casa Duse, LLC v. Merkin | 791 F.3d 247 | circuit | 120 | 2015-06-29 | 412 | not_run |
| New York Times Co. v. Tasini | 533 U.S. 483 | scotus | 119 | 2001-06-25 | 108, 203 | not_run |
| Apple Inc. v. Psystar Corp. | 658 F.3d 1150 | circuit | 117 | 2011-09-28 | 109 | not_run |
| Horror Inc. v. Miller | 15 F.4th 232 | circuit | 117 | 2021-09-30 | 203 | not_run |
| Gerald Zuk v. Eastern Pennsylvania Psychiatric Institute of  | 103 F.3d 294 | circuit | 115 | 1996-12-31 | 109 | not_run |
| Lugosi v. Universal Pictures | 603 P.2d 425 | other | 114 | 1979-12-03 | 302 | not_run |
| John G. Danielson, Inc. v. Winchester-Conant Properties, Inc | 322 F.3d 26 | circuit | 107 | 2003-03-06 | 204 | not_run |
| The Chamberlain Group, Inc. v. Skylink Technologies, Inc. | 381 F.3d 1178 | circuit | 102 | 2004-10-22 | 1201 | not_run |
| MDY Industries, LLC v. Blizzard Entertainment, Inc. | 629 F.3d 928 | circuit | 102 | 2010-12-14 | 1201 | not_run |
| Abend v. MCA, Inc. | 863 F.2d 1465 | circuit | 101 | 1988-12-27 | 302 | not_run |
| Guzman v. Hacienda Records & Recording Studio, Inc. | 808 F.3d 1031 | circuit | 100 | 2015-12-14 | 1202 | not_run |
| Columbia Pictures Industries, Inc. v. Redd Horne, Inc. | 749 F.2d 154 | circuit | 97 | 1984-11-23 | 109 | not_run |
| Ground Zero Museum Workshop v. Wilson | 813 F. Supp. 2d 678 | district | 97 | 2011-11-04 | 1201 | not_run |
| Paice LLC v. Toyota Motor Corp. | 504 F.3d 1293 | circuit | 95 | 2007-10-18 | 115 | not_run |
| Media Rights Technologies, Inc v. Microsoft Corporation | 922 F.3d 1014 | circuit | 91 | 2019-05-02 | 1201 | not_run |
| DVD Copy Control Ass'n, Inc. v. Bunner | 75 P.3d 1 | other | 91 | 2003-10-15 | 1201 | not_run |
| Zalewski v. Cicero Builder Dev., Inc. | 754 F.3d 95 | circuit | 89 | 2014-06-05 | 1202 | not_run |
| Jacobus Rentmeester v. Nike, Inc. | 883 F.3d 1111 | circuit | 87 | 2018-02-27 | 1202 | not_run |
| Peer International Corp. v. Luna Records, Inc. | 887 F. Supp. 560 | district | 83 | 1995-04-28 | 115 | not_run |
| Stephanie Hays and Gail MacDonald v. Sony Corporation of Ame | 847 F.2d 412 | circuit | 82 | 1988-06-22 | 302 | not_run |
| London-Sire Records, Inc. v. Doe 1 | 542 F. Supp. 2d 153 | district | 80 | 2008-03-31 | 109, 115 | not_run |
| DIRECTV, Inc. v. Trone | 209 F.R.D. 455 | district | 80 | 2002-08-14 | 1201 | not_run |
| Martin's Herend Imports, Inc. v. Diamond & GEM Trading USA,  | 112 F.3d 1296 | circuit | 79 | 1997-05-28 | 109 | not_run |
| Fischer v. Forrest | 286 F. Supp. 3d 590 | district | 79 | 2018-02-16 | 1202 | not_run |
| Muhammad-Ali v. Final Call, Inc. | 832 F.3d 755 | circuit | 74 | 2016-08-10 | 109 | not_run |
| Video Pipeline, Inc. v. Buena Vista Home Entertainment, Inc. | 210 F. Supp. 2d 552 | district | 74 | 2002-07-26 | 109 | not_run |
| Golan v. Holder | 565 U.S. 302 | scotus | 73 | 2012-01-18 | 302 | not_run |
| Quality King Distributors, Inc. v. L'Anza Research Internati | 523 U.S. 135 | scotus | 72 | 1998-03-09 | 109 | not_run |
| Authors Guild, Inc. v. HathiTrust | 755 F.3d 87 | circuit | 71 | 2014-06-10 | 108 | not_run |
| St. Luke's Cataract & Laser Institute. P.A. v. Sanderson | 573 F.3d 1186 | circuit | 70 | 2009-07-09 | 1202 | not_run |
| Vault Corporation v. Quaid Software Limited | 847 F.2d 255 | circuit | 68 | 1988-06-20 | 108, 302 | not_run |
| Veronica Vincent v. City Colleges of Chicago, Ezekiel Morris | 485 F.3d 919 | circuit | 66 | 2007-04-30 | 109 | not_run |
| Polar Bear Productions, Inc., a Montana Corporation v. Timex | 384 F.3d 700 | circuit | 66 | 2004-10-25 | 1202 | not_run |
| Stephanie Lenz v. Universal Music Corp. | 815 F.3d 1145 | circuit | 65 | 2016-03-17 | 108 | not_run |
| Brilliance Audio, Inc. v. Haights Cross Communications, Inc. | 474 F.3d 365 | circuit | 64 | 2007-01-26 | 109 | not_run |
| Clare Milne, by and Through Michael Joseph Coyne, Her Receiv | 430 F.3d 1036 | circuit | 64 | 2005-12-08 | 203, 302 | not_run |
| Personal Keepsakes, Inc. v. Personalizationmall.com, Inc. | 975 F. Supp. 2d 920 | district | 63 | 2013-09-24 | 1202 | not_run |
| Friedman v. Live Nation Merchandise, Inc. | 833 F.3d 1180 | circuit | 63 | 2016-08-18 | 1202 | not_run |
| Baldwin v. EMI Feist Catalog, Inc. | 805 F.3d 18 | circuit | 61 | 2015-10-08 | 203 | not_run |
| Bretford Manufacturing, Inc. v. Smith System Manufacturing C | 419 F.3d 576 | circuit | 59 | 2005-08-08 | 106A | not_run |
| Donna R. Hotaling William W. Hotaling, Jr. James P. Maher Do | 118 F.3d 199 | circuit | 59 | 1997-06-30 | 108 | not_run |
| Giordano v. Claudio | 714 F. Supp. 2d 508 | district | 55 | 2010-05-14 | 106A | not_run |
| International Korwin Corp. v. Tadeusz Kowalczyk | 855 F.2d 375 | circuit | 54 | 1988-08-16 | 110 | not_run |
| Abkco Music, Inc. And Abkco Music and Records, Inc. v. Stell | 96 F.3d 60 | circuit | 54 | 1996-09-19 | 115 | not_run |
| Mango v. Buzzfeed, Inc. | 356 F. Supp. 3d 368 | district | 54 | 2019-01-17 | 1202 | not_run |
| EMI April Music, Inc. v. White | 618 F. Supp. 2d 497 | district | 52 | 2009-05-22 | 110 | not_run |
| Community for Creative Non-Violence v. James Earl Reid | 846 F.2d 1485 | circuit | 52 | 1988-05-31 | 203, 302 | not_run |
| Mango v. Buzzfeed, Inc. | 970 F.3d 167 | circuit | 50 | 2020-08-13 | 1202 | not_run |
| Carter v. Helmsley-Spear, Inc. | 71 F.3d 77 | circuit | 48 | 1995-12-01 | 106A | not_run |
| Ronald Louis Smith, Jr. v. Harry Wayne Casey | 741 F.3d 1236 | circuit | 48 | 2014-01-22 | 203 | not_run |
| Vacheron & Constantin-Le Coultre Watches, Inc. v. Benrus Wat | 260 F.2d 637 | circuit | 47 | 1958-10-21 | 115 | not_run |
| Cyril Russell, Etc. v. Daniel A. Price, and Albert C. Drebin | 612 F.2d 1123 | circuit | 47 | 1980-02-19 | 203 | not_run |
| Dielsi v. Falk | 916 F. Supp. 985 | district | 45 | 1996-01-23 | 106A | not_run |
| Philadelphia Eagles Football Club, Inc. v. City of Philadelp | 573 Pa. 189 | other | 43 | 2003-04-25 | 203 | not_run |
| BanxCorp v. Costco Wholesale Corp. | 723 F. Supp. 2d 596 | district | 40 | 2010-07-14 | 1202 | not_run |
| Joanne Pollara v. Joseph J. Seymour and Thomas E. Casey, Joh | 344 F.3d 265 | circuit | 36 | 2003-09-19 | 106A | not_run |
| Castillo v. G&M Realty L.P. | 950 F.3d 155 | circuit | 33 | 2020-02-20 | 106A | not_run |
| Maharishi Hardy Blechman Ltd. v. Abercrombie & Fitch Co. | 292 F. Supp. 2d 535 | district | 30 | 2003-12-08 | 106A | not_run |
| Universal City Studios, Inc. v. Sony Corp. of America | 480 F. Supp. 429 | district | 28 | 1979-12-05 | 108 | not_run |
| Jan Randolph Martin, Plaintiff-Appellee/cross-Appellant v. C | 192 F.3d 608 | circuit | 26 | 1999-08-31 | 106A | not_run |
| Massachusetts Museum of Contemporary Art Foundation, Inc. v. | 593 F.3d 38 | circuit | 26 | 2010-01-27 | 106A | not_run |
| Fahmy v. Jay-Z | 908 F.3d 383 | circuit | 25 | 2018-05-31 | 106A | not_run |
| Simon Cheffins v. Michael Stewart | 825 F.3d 588 | circuit | 24 | 2016-06-08 | 106A | not_run |
| Annie Lee and Annie Lee & Friends Company, Inc. v. A.R.T. Co | 125 F.3d 580 | circuit | 24 | 1997-09-18 | 106A | not_run |
| International Korwin Corp. v. Kowalczyk | 665 F. Supp. 652 | district | 24 | 1987-07-01 | 110 | not_run |
| Dsc Communications Corporation v. Pulse Communications, Inc. | 170 F.3d 1354 | circuit | 20 | 1999-03-11 | 108 | not_run |
| Swallow Turn Music v. Wilson | 831 F. Supp. 575 | district | 20 | 1993-08-31 | 110 | not_run |
| Cass County Music Company v. Vasfi Muedini D/B/A Port Town F | 55 F.3d 263 | circuit | 19 | 1995-05-16 | 110 | not_run |
| T.B. Harms Co. v. Jem Records, Inc. | 655 F. Supp. 1575 | district | 18 | 1987-03-26 | 108 | not_run |
| Broadcast Music, Inc. v. Niro's Palace, Inc. | 619 F. Supp. 958 | district | 15 | 1985-05-28 | 110 | not_run |
| Encyclopaedia Britannica Educational Corp. v. Crooks | 447 F. Supp. 243 | district | 15 | 1978-02-27 | 110 | not_run |
| Disney Enterprises, Inc. v. VidAngel, Inc. | 224 F. Supp. 3d 957 | district | 14 | 2016-12-12 | 110 | not_run |
| Hickory Grove Music v. Andrews | 749 F. Supp. 1031 | district | 14 | 1990-09-13 | 110 | not_run |
| Sailor Music v. The Gap Stores, Inc. | 668 F.2d 84 | circuit | 14 | 1981-12-15 | 110 | not_run |
| Hachette Book Group, Inc. v. Internet Archive | 115 F.4th 163 | circuit | 13 | 2024-09-04 | 108 | not_run |
| Golan v. Gonzales | 501 F.3d 1179 | circuit | 11 | 2007-09-04 | 108 | not_run |
| Association of American Medical Colleges v. Carey | 728 F. Supp. 873 | district | 10 | 1990-01-12 | 108 | not_run |
| Pacific and Southern Co., Inc. v. Duncan | 572 F. Supp. 1186 | district | 9 | 1983-10-13 | 108 | not_run |

### UPDATE — existing cases (old → new)

- [51] Carter v. Helmsley-Spear, Inc.: court_level: None → 'district' · status: 'in_force' → 'unknown'
- [59] American Geophysical Union v. Texaco Inc.: court_level: None → 'circuit' · status: 'in_force' → 'unknown'
- [59] American Geophysical Union v. Texaco Inc.: court_level: None → 'circuit' · status: 'in_force' → 'unknown'
- [52] Worldwide Church Of God v. Philadelphia Church Of God, Inc.: court_level: None → 'circuit' · status: 'in_force' → 'unknown'
- [52] Worldwide Church Of God v. Philadelphia Church Of God, Inc.: court_level: None → 'circuit' · status: 'in_force' → 'unknown'
- [67] Kelly v. L.L. Cool J.: court_level: None → 'district' · status: 'in_force' → 'unknown'
- [66] Palladium Music, Inc. v. Eatsleepmusic, Inc.: court_level: None → 'circuit' · status: 'in_force' → 'unknown'
- [108] Lexmark International, Inc. v. Static Control Components, In: court_level: None → 'circuit' · status: 'in_force' → 'unknown'
- [112] Capitol Records, LLC v. Bluebeat, Inc.: court_level: None → 'district' · status: 'in_force' → 'unknown'

### KEEP (below cap) — true links outside the new top-N, verified still in CourtListener's results; KEPT by policy

- [33] Situation Management Systems v. ASP Consulting Group → § 102
- [34] Windgate Software, L.L.C. v. Minnesota Computers, Inc. → § 102
- [35] State ex rel. McNew v. Ohio Dept. of Rehab. & Corr. → § 102
- [36] Oracle America, Inc. v. Google Inc. → § 102
- [37] Zitz v. Bernadino Dos Santos → § 102
- [38] Tasini v. The New York Times Company, Inc. → § 103
- [39] Ryan v. Carl Corp. → § 103
- [40] Gamma v. Ean-Chea → § 103
- [42] Dream Custom Homes, Inc. v. Modern Day Construction, Inc. → § 103
- [43] First World Architects Studio, PSC v. McGhee → § 106
- [44] TruLogic, Inc. v. Gen. Elec. Co. → § 106
- [45] Southern Credentialing Support v. Hammond Surgical → § 106
- [46] Berrios Nogueras v. Home Depot → § 106
- [47] Excel Homes, Inc. v. Locricchio → § 106
- [48] Hunter v. Squirrel Hill Associates, L.P. → § 106A
- [49] Pavia v. 1120 Avenue of the Americas Associates → § 106A
- [50] Flack v. Friends of Queen Catherine Inc. → § 106A
- [52] Worldwide Church Of God v. Philadelphia Church Of God, Inc. → § 107
- [53] Raanan Katz v. Irina Chevaldina → § 107
- [54] State ex rel. Gambill v. Opperman → § 107
- [55] Peterman v. Republican Nat'l Comm. → § 107
- [56] Smithkline Beecham Consumer Healthcare, L.P., Plaintiffappellant v. Wa → § 107
- [57] Authors Guild, Inc. v. Hathitrust → § 108
- [58] Whether Government Reproduction of Copyrighted Materials is a Noninfri → § 108
- [60] American Geophysical Union v. Texaco Inc. → § 108
- [62] Schwartz-Liebman Textiles v. Last Exit Corp. → § 109
- [63] Apple, Inc. v. Psystar Corp. → § 109
- [64] Softman Products Co., LLC v. Adobe Systems, Inc. → § 109
- [65] In Re Valley Media, Inc. → § 109
- [68] Yesh Music, LLC v. Amazon.com, Inc. → § 115
- [38] Tasini v. The New York Times Company, Inc. → § 201
- [69] Sisyphus Touring, Inc. v. TMZ Productions, Inc. → § 201
- [70] Forward v. Thorogood → § 201
- [71] Recht v. METRO GOLDWYN MAYER STUDIO, INC. → § 201
- [73] Harry Wayne Casey v. Richard R. Finch → § 203
- [74] Tammy Livingston v. Jay Livingston Music, Inc. → § 203
- [69] Sisyphus Touring, Inc. v. TMZ Productions, Inc. → § 204
- [75] Conwell v. Gray Loon Outdoor Marketing Group, Inc. → § 204
- [76] Tiffany Design, Inc. v. Reno-Tahoe Specialty, Inc. → § 204
- [77] Metropolitan Regional Information Systems, Inc. v. American Home Realt → § 204
- [78] Thornton v. J Jargon Co. → § 204
- [43] First World Architects Studio, PSC v. McGhee → § 301
- [44] TruLogic, Inc. v. Gen. Elec. Co. → § 301
- [79] Cheng v. Haney → § 301
- [80] Capitol Records, Inc. v. Mp3tunes, LLC → § 301
- [81] Zito v. Steeplechase Films, Inc. → § 301
- [82] Rodrigue v. Rodrigue → § 302
- [83] Kroni Inc. v. Kohler Company → § 302
- [43] First World Architects Studio, PSC v. McGhee → § 411
- [84] Derminer v. Kramer → § 411
- [85] Precision Automation, Inc. v. Technical Services, Inc. → § 411
- [86] Raquel, a Partnership v. Education Management Corporation Art Institut → § 411
- [87] Centurion Wireless Technologies, Inc. v. Hop-On Communications, Inc. → § 411
- [43] First World Architects Studio, PSC v. McGhee → § 412
- [45] Southern Credentialing Support v. Hammond Surgical → § 412
- [88] Loree Rodkin Management Corp. v. Ross-Simons, Inc. → § 412
- [89] Pavlica v. Behr → § 412
- [90] Coton v. Televised Visual X-Ography, Inc. → § 412
- [91] Beholder Productions, Inc. v. Catona → § 501
- [92] Elisan Entertainment, Inc. v. Suazo → § 501
- [93] Fantasy, Inc. v. Fogerty → § 501
- [94] Matthews v. Freedman → § 501
- [80] Capitol Records, Inc. v. Mp3tunes, LLC → § 501
- [95] Amini Innovation Corp. v. KTY International Marketing → § 504
- [90] Coton v. Televised Visual X-Ography, Inc. → § 504
- [96] Alaska Stock, LLC v. Pearson Education, Inc. → § 504
- [97] The Cambridge Institute, Inc., Plaintiff-Cross-Defendant-Appellee v. T → § 504
- [98] Clever Covers, Inc. v. Southwest Florida Storm Defense, LLC → § 504
- [99] Lotus v. Borland → § 505
- [100] Big Tree Enterprises, Ltd. Hamstein Music Company Ram's Horn Music, Em → § 505
- [101] Edwards v. Red Farm Studio, Co. → § 505
- [102] Bryant v. Gordon → § 505
- [94] Matthews v. Freedman → § 505
- [103] Mometrix Media, LLC v. LCR Publishing, LLC → § 512
- [105] Hendrickson v. eBay, Inc. → § 512
- [106] Perfect 10, Inc. v. Cybernet Ventures, Inc. → § 512
- [107] Costar Group Inc. v. Loopnet, Inc. → § 512
- [63] Apple, Inc. v. Psystar Corp. → § 1201
- [109] Lexmark Intl Inc v. Static Control → § 1201
- [110] Chamberlain Group, Inc. v. Skylink Technologies, Inc. → § 1201
- [111] Jedson Engineering, Inc. v. Spirit Construction Services, Inc. → § 1202
- [113] Granger v. Gill Abstract Corp. → § 1202

---
*Internal research aid. The reviewer approves this as a DATA diff; legal correctness of case relevance is a separate (attorney) question.*