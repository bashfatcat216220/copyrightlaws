"""Tier-2 ingest — France, Code de la propriété intellectuelle (CPI), Part I.

Per the Tier-2 fan-out contract (see ingest_de_urhg.py): an INSTRUMENT dict + a `parse()`
returning a `_common.RecordSet` + a thin `main()`. All DB/versioning/idempotency lives in
`_common`. NEVER originates text — every article body is lifted from the fetched source.

Source: WIPO Lex "France — Intellectual Property Code" ENGLISH translation (fr467en.pdf,
record 18275, consolidated as of 7 September 2018). It is an unofficial TRANSLATION, so
`run_ingest(..., is_official_language=0)` (authentic language = French; flagged in the UI).

Scope: PART I "Literary and Artistic Property" ONLY — Books I–III, Articles L111-1 to
L343-4 (copyright, related rights, databases). The PDF continues into PART II "Industrial
Property" (L4xx…L7xx); this ingest STOPS at the "PART II" boundary — no patents/marks.

Structure (from the PDF, converted via pdftotext):
    PART I → BOOK → TITLE → CHAPTER → SECTION → Article Lxxx-yy
Codified article numbers (L122-5, L331-1, L122-6-1) are NOT simple integers → the label is
handed to `_common.ordinal`, which falls back to DOCUMENT ORDER (authoritative from the
single fetch). Articles RAIL in the reader (kind='article'); containers are part/chapter/
subchapter (Book/Title→part, Chapter→chapter, Section→subchapter). Citations: "CPI Art. Lxxx".

Run:
    python src/store/ingest_fr.py --db db/corpus.db --allow-corpus \
        --html spike/artifacts/fr_cpi.txt \
        --source-url https://www.wipo.int/wipolex/en/legislation/details/18275
"""
from __future__ import annotations

import argparse
import re

from _common import RecordSet, ordinal, run_ingest

INSTRUMENT = dict(jurisdiction="FR", type="statute",
                  official_citation="Code de la propriété intellectuelle (CPI)",
                  ext_id_scheme="NATIONAL", ext_id="fr-cpi-lit",
                  title="Intellectual Property Code — Literary and Artistic Property "
                        "(Articles L111-1 et seq.)")

# Structural containers → provisions.kind. Book & Title both nest as 'part' (Title under Book),
# Chapter → 'chapter', Section → 'subchapter'. All are addressable but shareless containers.
_KIND = {"BOOK": "part", "TITLE": "part", "CHAPTER": "chapter",
         "SECTION": "subchapter", "SOLE CHAPTER": "chapter"}

# A structural header is a WHOLE line: keyword + roman numeral (or the bare "SOLE CHAPTER").
_HEADER = re.compile(r"^(BOOK|TITLE|CHAPTER|SECTION)\s+([IVXLC]+)$|^(SOLE CHAPTER)$")
# An article header is a WHOLE line: "Article L122-5" / "Article L122-6-1" (no trailing prose,
# which excludes mid-paragraph cross-references like "Article L122-5 and item 2 of...").
_ARTICLE = re.compile(r"^Article\s+(L\d+-\d+(?:-\d+)?)$")
# Where PART I (copyright) ends and PART II (industrial property) begins — hard stop.
_PART_II = re.compile(r"^PART II$")
# Body noise to drop: per-page footers and the repeated running page-header.
_NOISE = re.compile(r"^(Updated\s+\d.*Page\s+\d+/\d+|INTELLECTUAL PROPERTY CODE|"
                    r"Legislative Part|PART I|Literary and Artistic Property)$")
# TOC "range summary" that trails every container header ("Articles L111-1 to" / "L133-4").
_RANGE = re.compile(r"^Articles\s+L\d+-\d+\s+to\s*$|^L\d+-\d+\s*$")


def _lines(path: str) -> list[str]:
    text = open(path, encoding="utf-8", errors="replace").read()
    return [ln.rstrip() for ln in text.split("\n")]


def parse(path: str) -> RecordSet:
    lines = _lines(path)
    rs = RecordSet()
    # open container ids by kind — a deeper container clears the shallower ones below it
    container = {"part_book": None, "part_title": None, "chapter": None, "subchapter": None}
    doc_i = 0
    i, n = 0, len(lines)

    def parent_for_article() -> int | None:
        return (container["subchapter"] or container["chapter"] or
                container["part_title"] or container["part_book"])

    while i < n:
        raw = lines[i]
        line = raw.strip()

        if _PART_II.match(line):        # reached Industrial Property — stop (copyright scope only)
            break

        hm = _HEADER.match(line)
        if hm:
            unit = hm.group(1) or hm.group(3)        # "BOOK"/"TITLE"/… or "SOLE CHAPTER"
            roman = hm.group(2) or ""
            # heading = the immediately following non-empty line, unless it's a range/article/header
            heading = None
            j = i + 1
            while j < n and not lines[j].strip():
                j += 1
            if j < n:
                cand = lines[j].strip()
                if cand and not _RANGE.match(cand) and not _HEADER.match(cand) \
                        and not _ARTICLE.match(cand) and not _NOISE.match(cand):
                    heading = cand
            kind = _KIND[unit]
            doc_i += 1
            si, su = ordinal(roman, doc_i)           # roman → falls back to doc order (authoritative)
            label = f"{unit.title()} {roman}".strip()
            if unit == "BOOK":
                container["part_title"] = container["chapter"] = container["subchapter"] = None
                parent, slot = None, "part_book"
            elif unit == "TITLE":
                container["chapter"] = container["subchapter"] = None
                parent, slot = container["part_book"], "part_title"
            elif unit in ("CHAPTER", "SOLE CHAPTER"):
                container["subchapter"] = None
                parent = container["part_title"] or container["part_book"]
                slot = "chapter"
            else:  # SECTION
                parent = container["chapter"] or container["part_title"] or container["part_book"]
                slot = "subchapter"
            container[slot] = rs.add(parent_local=parent, kind=kind, label=label,
                                     heading=heading, sort_int=si, sort_suffix=su,
                                     citation=f"CPI {label}")
            i += 1
            continue

        am = _ARTICLE.match(line)
        if am:
            num = am.group(1)                        # e.g. "L122-5"
            body: list[str] = []
            j = i + 1
            while j < n:
                nxt = lines[j].strip()
                am2 = _ARTICLE.match(nxt)
                if am2 and am2.group(1) == num:      # duplicated header (pdftotext caption artifact):
                    j += 1                           # skip the phantom, keep reading the real body
                    continue
                if am2 or _HEADER.match(nxt) or _PART_II.match(nxt):
                    break
                if nxt and not _NOISE.match(nxt) and not _RANGE.match(nxt):
                    body.append(nxt)
                j += 1
            content = "\n".join(body).strip() or None
            doc_i += 1
            si, su = ordinal(num, doc_i)             # codified label → doc order fallback
            rs.add(parent_local=parent_for_article(), kind="article",
                   label=f"Article {num}", heading=None, sort_int=si, sort_suffix=su,
                   citation=f"CPI Art. {num}", content=content)
            i = j
            continue

        i += 1
    return rs


def main() -> None:
    ap = argparse.ArgumentParser(description="Ingest France CPI Part I (WIPO Lex EN translation).")
    ap.add_argument("--db", required=True)
    ap.add_argument("--html", required=True, help="path to fr_cpi.txt (pdftotext of fr467en.pdf)")
    ap.add_argument("--source-url", required=True)
    ap.add_argument("--point-in-time", default=None)
    ap.add_argument("--allow-corpus", action="store_true")
    a = ap.parse_args()
    s = run_ingest(a.db, INSTRUMENT, parse(a.html), a.source_url, point_in_time=a.point_in_time,
                   allow_corpus=a.allow_corpus, is_official_language=0,   # English translation
                   version_label="WIPO Lex (EN translation, consolidated 2018-09-07)",
                   fts_title="CPI")
    print(f"instrument #{s['instrument_id']}  France CPI (Part I) — {s['provisions']} provisions "
          f"({s['by_kind'].get('article', 0)} articles); versions new {s['versions_new']}, "
          f"unchanged {s['versions_unchanged']} (is_official_language=0)")


if __name__ == "__main__":
    main()
