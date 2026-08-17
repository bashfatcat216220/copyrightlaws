"""Wave D (2f) — InfoSoc 2001/29: the AUTHENTIC ORIGINAL articles, as an additive layer.

The corpus holds Directive 2001/29 as (a) 61 authentic-original RECITALS (is_authentic=1,
from the original OJ HTML) and (b) the 2019-06-06 editorial CONSOLIDATION as the current
enacting text (is_authentic=0). This ingest adds the missing piece: the AUTHENTIC ORIGINAL
ARTICLES from the same original-OJ artifact (`spike/artifacts/infosoc_oj.html`, EUR-Lex
CELEX:32001L0029 — DC.source: "Official Journal L 167 , 22/06/2001 P. 0010 - 0019").

ADDITIVE ONLY (no clobber):
  - versions are PINNED at point_in_time=2001-06-22 (the OJ L 167 publication date, which is
    also entry into force — Art. 14: "on the day of its publication") with is_current=0, via
    `_common.store_pinned_version`. The consolidated current versions and the authentic
    recitals are NOT touched.
  - provisions are MATCHED on the existing stable citations ("Directive 2001/29 Art. N");
    the original act's Articles 1-15 all exist already, so no provision rows are created.
    An unmatched article is REPORTED and hard-fails (never silently minted or dropped).
  - the change monitor is NOT run (cross-manifestation re-base, CLAUDE ingest rule 6).

Segmentation (ingest rules 1/3/5): enacting terms run from "HAVE ADOPTED THIS DIRECTIVE"
and are END-CAPPED at "Done at Brussels" — the signature block and the OJ footnote list
((1) OJ C 108 … (11) OJ L 167) are NEVER swallowed by Article 15. CHAPTER headings are
structural (skipped, with their title line). Article numbering is verified contiguous 1..15.

Run (scratch first — CLAUDE rule 9):
    python src/store/ingest_infosoc_authentic.py --db db/scratch-corpus.db \
        --html spike/artifacts/infosoc_oj.html \
        --source-url "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32001L0029"
"""
from __future__ import annotations

import argparse
import html as htmlmod
import os
import re
import sqlite3

from _common import require_migration, store_pinned_version

CELEX = ("EU", "CELEX", "32001L0029")          # instrument identity (must already exist)
POINT_IN_TIME = "2001-06-22"                   # OJ L 167, 22.6.2001 (DC.source; EIF = pub day, Art. 14)
VERSION_LABEL = "EUR-Lex (original OJ)"        # same label as the authentic recitals layer
EXPECTED_ARTICLES = 15

P_RE = re.compile(r"<p[^>]*>(.*?)</p>", re.S)
ART_RE = re.compile(r"^Article (\d+)$")
CH_RE = re.compile(r"^CHAPTER [IVX]+$")


def _clean(fragment: str) -> str:
    """One <p> block -> plain text. Strip <script>/<style> BEFORE tags (rule 5)."""
    t = re.sub(r"<(script|style)\b.*?</\1>", " ", fragment, flags=re.S | re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", htmlmod.unescape(t)).strip()


def parse(html_path: str) -> list[dict]:
    """Return [{num, heading, content}] for the original act's articles, in order."""
    h = open(html_path, encoding="utf-8").read()
    start = h.find("HAVE ADOPTED")
    end = h.find("Done at Brussels")            # end-cap: signatures + OJ footnotes excluded
    if start == -1 or end == -1 or end <= start:
        raise SystemExit("enacting-terms boundaries not found — is this the original OJ HTML?")
    seg = h[start:end]

    arts: list[dict] = []
    cur: dict | None = None
    expect_heading = False
    skip_chapter_title = False
    for m in P_RE.finditer(seg):
        text = _clean(m.group(1))
        if not text:
            continue
        if CH_RE.match(text):                   # structural chapter marker
            skip_chapter_title = True
            continue
        if skip_chapter_title:                  # the chapter's ALL-CAPS title line
            skip_chapter_title = False
            continue
        am = ART_RE.match(text)
        if am:
            n = int(am.group(1))
            expected = (arts[-1]["num"] + 1) if arts else 1
            if cur:
                arts.append(cur)
                expected = arts[-1]["num"] + 1
            if n != expected:                   # sequential-numbering rule (rule 1)
                raise SystemExit(f"article numbering break: got Article {n}, expected {expected}")
            cur = {"num": n, "heading": None, "content": ""}
            expect_heading = True
            continue
        if cur is None:                         # preamble tail before Article 1
            continue
        if expect_heading:
            cur["heading"] = text
            expect_heading = False
        else:
            cur["content"] = (cur["content"] + " " + text).strip() if cur["content"] else text
    if cur:
        arts.append(cur)
    if len(arts) != EXPECTED_ARTICLES:
        raise SystemExit(f"expected {EXPECTED_ARTICLES} articles, parsed {len(arts)}")
    for a in arts:
        if not a["content"]:
            raise SystemExit(f"Article {a['num']} parsed empty — refusing (no blank bodies)")
    return arts


def ingest(db_path: str, html_path: str, source_url: str, allow_corpus: bool = False) -> dict:
    if os.path.basename(db_path) == "corpus.db" and not allow_corpus:
        raise SystemExit("refusing to write the live corpus.db — pass --allow-corpus")
    arts = parse(html_path)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    require_migration(conn)
    row = conn.execute("SELECT id FROM instruments WHERE jurisdiction=? AND ext_id_scheme=? "
                       "AND ext_id=?", CELEX).fetchone()
    if not row:
        raise SystemExit("Directive 2001/29 instrument not found — this layer is additive only")
    iid = row[0]
    stats = {"instrument_id": iid, "articles": 0, "new": 0, "unchanged": 0}
    for a in arts:
        cit = f"Directive 2001/29 Art. {a['num']}"
        prow = conn.execute("SELECT id FROM provisions WHERE instrument_id=? AND citation=?",
                            (iid, cit)).fetchone()
        if not prow:                            # additive: never mint InfoSoc provisions here
            raise SystemExit(f"no existing provision for {cit} — refusing to mint one")
        outcome = store_pinned_version(
            conn, iid, prow[0], cit, a["content"], source_url=source_url,
            point_in_time=POINT_IN_TIME, version_label=VERSION_LABEL,
            fts_title="Directive 2001/29/EC", is_authentic=1, is_consolidated=0)
        stats["articles"] += 1
        stats["new" if outcome == "new" else "unchanged"] += 1
    conn.commit()
    conn.close()
    return stats


def main() -> None:
    ap = argparse.ArgumentParser(description="InfoSoc 2001/29 — authentic ORIGINAL articles "
                                             "(additive pinned layer, is_authentic=1).")
    ap.add_argument("--db", required=True)
    ap.add_argument("--html", required=True, help="original OJ act HTML (infosoc_oj.html)")
    ap.add_argument("--source-url", required=True)
    ap.add_argument("--allow-corpus", action="store_true")
    a = ap.parse_args()
    s = ingest(a.db, a.html, a.source_url, a.allow_corpus)
    print(f"instrument #{s['instrument_id']}  Directive 2001/29/EC — authentic original articles")
    print(f"  articles pinned at {POINT_IN_TIME}: {s['articles']} "
          f"(new {s['new']}, unchanged {s['unchanged']}; is_authentic=1, is_current untouched)")


if __name__ == "__main__":
    main()
