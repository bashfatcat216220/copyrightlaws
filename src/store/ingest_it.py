"""Tier-2 ingest — Italy, Law No. 633/1941 (Legge sul diritto d'autore, LDA).

Per the Tier-2 fan-out contract (see ingest_de_urhg.py): an INSTRUMENT dict + a `parse()`
returning a `_common.RecordSet` + a thin `main()`. All DB/versioning/idempotency lives in
`_common`. NEVER originates text — every article body is lifted from the fetched source.

Source: WIPO Lex "Italy — Law No. 633 of April 22, 1941, on the Protection of Copyright and
Neighboring Rights" (record 15998), signed English PDF it211en.pdf on wipolex-res.wipo.int,
labelled "UNOFFICIAL DRAFT ENGLISH VERSION – REVISED FEBRUARY 2004", consolidated as amended
up to Legislative Decree No. 68 of April 9, 2003. It is an unofficial TRANSLATION, so
`run_ingest(..., is_official_language=0)` (authentic language = Italian; flagged in the UI).

Structure (from the PDF, converted via `pdftotext -layout`):
    PART <roman> → CHAPTER <roman> → SECTION <roman> → Article N
Container and article headers are CENTRED whole lines. Italy inserts bis/ter/quater articles
(e.g. "Article 64 bis", "Art. 71 quinquies", "Article 110bis") — the suffix is normalised to
the compact form so the citation is stable ("LDA Art. 64bis"). Article numbers are NOT simple
integers → the label is handed to `_common.ordinal`; `64bis` splits to (64,"BIS"); space- or
hyphen-separated forms may fall to DOCUMENT ORDER (authoritative from the single fetch) — fine.
Articles RAIL in the reader (kind='article', operative content); containers are
part/chapter/subchapter (PART→part, CHAPTER→chapter, SECTION→subchapter).

Run:
    python src/store/ingest_it.py --db db/corpus.db --allow-corpus \
        --html spike/artifacts/it_lda.txt \
        --source-url https://www.wipo.int/wipolex/en/legislation/details/15998
"""
from __future__ import annotations

import argparse
import re

from _common import RecordSet, ordinal, run_ingest

INSTRUMENT = dict(jurisdiction="IT", type="statute",
                  official_citation="Law No. 633/1941 (LDA)",
                  ext_id_scheme="NATIONAL", ext_id="it-lda-633-1941",
                  title="Law No. 633 of 22 April 1941 on Copyright and Neighbouring Rights (Italy)")

# Structural containers → provisions.kind. PART → 'part', CHAPTER → 'chapter', SECTION →
# 'subchapter'. All are addressable but shareless containers.
_KIND = {"PART": "part", "CHAPTER": "chapter", "SECTION": "subchapter"}

# The Latin ordinal suffixes Italy uses for inserted articles.
_SUFFIX = r"bis|ter|quater|quinquies|sexies|septies|octies|novies|decies|undecies|duodecies"

# A container header is a CENTRED whole line: keyword + roman numeral, optionally with a
# trailing "bis"/"ter" (PART II bis). Case: PART/CHAPTER/SECTION are upper-cased in the body.
_HEADER = re.compile(
    rf"^\s+(PART|CHAPTER|SECTION)\s+([IVXLC]+(?:\s+(?:{_SUFFIX}))?)\s*$")
# An article header is a CENTRED whole line: "Article 20" / "Article 64 bis" / "Art. 171 bis"
# / "Article 110bis". Trailing prose (footnotes citing "Art. 39 of Decree ...") is excluded by
# the whole-line anchor.
_ARTICLE = re.compile(
    rf"^\s+(?:Article|Art\.)\s+(\d+)\s*((?:{_SUFFIX}))?\s*$", re.I)
# Page-footer noise: a bare page number on its own (right-padded) line.
_PAGENO = re.compile(r"^\s*\d{1,3}\s*$")


def _norm_num(n: str, suffix: str | None) -> str:
    """'64' + 'bis' → '64bis'; '20' + None → '20'. Compact form → stable citation."""
    return f"{n}{suffix.lower()}" if suffix else n


def _lines(path: str) -> list[str]:
    text = open(path, encoding="utf-8", errors="replace").read()
    return [ln.rstrip() for ln in text.split("\n")]


def parse(path: str) -> RecordSet:
    lines = _lines(path)
    n = len(lines)
    rs = RecordSet()
    # open container ids by kind; a shallower container clears the deeper ones below it
    container = {"part": None, "chapter": None, "subchapter": None}
    doc_i = 0
    # Skip the TABLE OF CONTENTS: the body begins at the first centred "PART I" header, which
    # is preceded in the TOC only by left-aligned "Part I ..." lines.
    start = 0
    for i, ln in enumerate(lines):
        if re.match(r"^\s{20,}PART\s+I\s*$", ln):
            start = i
            break

    def parent_for_article() -> int | None:
        return (container["subchapter"] or container["chapter"] or container["part"])

    def _heading_after(idx: int) -> str | None:
        """The centred title line that follows a container header (skip blank lines)."""
        j = idx + 1
        while j < n and not lines[j].strip():
            j += 1
        if j < n:
            cand = lines[j].strip()
            if cand and not _HEADER.match(lines[j]) and not _ARTICLE.match(lines[j]) \
                    and not _PAGENO.match(lines[j]):
                return cand
        return None

    i = start
    while i < n:
        hm = _HEADER.match(lines[i])
        if hm:
            unit = hm.group(1)                       # PART / CHAPTER / SECTION
            roman = hm.group(2).strip()              # "I" / "II bis"
            kind = _KIND[unit]
            heading = _heading_after(i)
            doc_i += 1
            si, su = ordinal(roman, doc_i)           # roman → falls back to doc order
            label = f"{unit.title()} {roman}"
            if kind == "part":
                container["chapter"] = container["subchapter"] = None
                parent = None
            elif kind == "chapter":
                container["subchapter"] = None
                parent = container["part"]
            else:  # SECTION
                parent = container["chapter"] or container["part"]
            container[kind] = rs.add(parent_local=parent, kind=kind, label=label,
                                     heading=heading, sort_int=si, sort_suffix=su,
                                     citation=f"LDA {label}")
            i += 1
            continue

        am = _ARTICLE.match(lines[i])
        if am:
            num = _norm_num(am.group(1), am.group(2))    # "64bis" / "20"
            body: list[str] = []
            j = i + 1
            while j < n:
                if _HEADER.match(lines[j]) or _ARTICLE.match(lines[j]):
                    break
                s = lines[j].strip()
                if s and not _PAGENO.match(lines[j]):
                    body.append(s)
                j += 1
            content = "\n".join(body).strip() or None
            doc_i += 1
            si, su = ordinal(num, doc_i)                 # '64bis'→(64,'BIS'); space form→doc order
            rs.add(parent_local=parent_for_article(), kind="article",
                   label=f"Article {num}", heading=None, sort_int=si, sort_suffix=su,
                   citation=f"LDA Art. {num}", content=content)
            i = j
            continue

        i += 1
    return rs


def main() -> None:
    ap = argparse.ArgumentParser(description="Ingest Italy LDA (WIPO Lex EN translation).")
    ap.add_argument("--db", required=True)
    ap.add_argument("--html", required=True, help="path to it_lda.txt (pdftotext of it211en.pdf)")
    ap.add_argument("--source-url", required=True)
    ap.add_argument("--point-in-time", default=None)
    ap.add_argument("--allow-corpus", action="store_true")
    a = ap.parse_args()
    s = run_ingest(a.db, INSTRUMENT, parse(a.html), a.source_url, point_in_time=a.point_in_time,
                   allow_corpus=a.allow_corpus, is_official_language=0,   # English translation
                   version_label="WIPO Lex (EN translation, consolidated to D.Lgs. 68/2003; "
                                 "revised Feb 2004)",
                   fts_title="LDA")
    print(f"instrument #{s['instrument_id']}  Italy LDA (Law 633/1941) — {s['provisions']} "
          f"provisions ({s['by_kind'].get('article', 0)} articles); versions new "
          f"{s['versions_new']}, unchanged {s['versions_unchanged']} (is_official_language=0)")


if __name__ == "__main__":
    main()
