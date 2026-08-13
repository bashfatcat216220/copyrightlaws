"""Tier-2 ingest — Brazil, Law No. 9,610 of February 19, 1998 (Copyright and Neighbouring Rights).

Per the Tier-2 fan-out contract (see ingest_de_urhg.py / ingest_fr.py): an INSTRUMENT dict + a
`parse()` returning a `_common.RecordSet` + a thin `main()`. All DB/versioning/idempotency lives
in `_common`. NEVER originates text — every article body is lifted from the fetched source.

Source: WIPO Lex "Brazil — Law No. 9.610 of February 19, 1998 (Law on Copyright and Neighboring
Rights, as amended by Law No. 12.853 of August 14, 2013)", record 17474. The signed English PDF
(br224en.pdf on wipolex-res.wipo.int), converted via `pdftotext -layout`. It is an unofficial
English TRANSLATION (authentic language = Portuguese) of a CONSOLIDATED text (incorporates Law
12.853/2013), so `run_ingest(..., is_official_language=0, is_authentic=1, is_consolidated=1)` —
the translation caveat is flagged in the UI.

Structure (from the PDF; the translation renders the Portuguese *Título* as "Section" and
*Capítulo* as "Chapter"):
    Section I..VIII (part) -> Chapter I..N (chapter) -> Art. N (article, the RAIL/operative unit)
Article numbers run Art. 1 .. Art. 115, with letter-suffixed insertions (Art. 109-A). The number
is handed to `_common.ordinal` (109-A normalised to 109A so 109 < 109-A < 110). Some articles have
no parent Chapter (they sit directly under a Section) — parent falls back to the open Section.
Container headings = the immediately following non-empty line. Citations: "Law 9610/1998 (Brazil)
Art. N".

Run:
    python src/store/ingest_br.py --db db/corpus.db --allow-corpus \
        --html spike/artifacts/br_lda.txt \
        --source-url https://www.wipo.int/wipolex/en/legislation/details/17474
"""
from __future__ import annotations

import argparse
import re

from _common import RecordSet, ordinal, run_ingest

INSTRUMENT = dict(jurisdiction="BR", type="statute",
                  official_citation="Law No. 9,610/1998",
                  ext_id_scheme="NATIONAL", ext_id="br-9610-1998",
                  title="Law No. 9,610 of February 19, 1998 on Copyright and "
                        "Neighbouring Rights (Brazil)")

# A structural container header is a WHOLE line: keyword + roman numeral. In this translation the
# top-level unit *Título* is rendered "Section" (-> part) and *Capítulo* "Chapter" (-> chapter).
_SECTION = re.compile(r"^Section\s+([IVXLC]+)$")
_CHAPTER = re.compile(r"^Chapter\s+([IVXLC]+)$")
# An article header is a WHOLE-line start: "Art. 46." / "Art. 1" / "Art. 109-A." — captures the
# number (with optional letter suffix) and the rest of the line as the first body text.
_ARTICLE = re.compile(r"^Art\.\s+(\d+(?:-[A-Za-z]+)?)\.?\s*(.*)$")


def _norm(token: str) -> str:
    """'109-A' -> '109A' so _common.ordinal yields (109, 'A'): 109 < 109-A < 110."""
    return token.replace("-", "")


def _lines(path: str) -> list[str]:
    # form-feeds (\f) prefix page-break headers (e.g. "\fSection II") — strip so they match.
    text = open(path, encoding="utf-8", errors="replace").read().replace("\f", "\n")
    return [ln.rstrip() for ln in text.split("\n")]


def _heading_after(lines: list[str], i: int) -> str | None:
    """The container's heading = the next non-empty line, unless that line is itself a header."""
    j = i + 1
    n = len(lines)
    while j < n and not lines[j].strip():
        j += 1
    if j < n:
        cand = lines[j].strip()
        if cand and not _SECTION.match(cand) and not _CHAPTER.match(cand) \
                and not _ARTICLE.match(cand):
            return cand
    return None


def parse(path: str) -> RecordSet:
    lines = _lines(path)
    rs = RecordSet()
    container = {"part": None, "chapter": None}   # local ids of the open Section / Chapter
    part_roman = ""                                # current Section roman (scopes chapter citations)
    doc_i = 0
    i, n = 0, len(lines)

    while i < n:
        line = lines[i].strip()

        sm = _SECTION.match(line)
        if sm:
            roman = sm.group(1)
            doc_i += 1
            si, su = ordinal(roman, doc_i)        # roman -> falls back to doc order (authoritative)
            container["chapter"] = None
            part_roman = roman
            container["part"] = rs.add(parent_local=None, kind="part",
                                       label=f"Section {roman}",
                                       heading=_heading_after(lines, i), sort_int=si,
                                       sort_suffix=su, citation=f"Law 9610/1998 (Brazil) Section {roman}")
            i += 1
            continue

        cm = _CHAPTER.match(line)
        if cm:
            roman = cm.group(1)
            doc_i += 1
            si, su = ordinal(roman, doc_i)
            container["chapter"] = rs.add(parent_local=container["part"], kind="chapter",
                                          label=f"Chapter {roman}",
                                          heading=_heading_after(lines, i), sort_int=si,
                                          sort_suffix=su,
                                          citation=f"Law 9610/1998 (Brazil) Section {part_roman} "
                                                   f"Chapter {roman}")
            i += 1
            continue

        am = _ARTICLE.match(line)
        if am:
            num, first = am.group(1), am.group(2).strip()
            body = [first] if first else []
            j = i + 1
            while j < n:
                nxt = lines[j].strip()
                if _ARTICLE.match(nxt) or _SECTION.match(nxt) or _CHAPTER.match(nxt):
                    break
                if nxt:
                    body.append(nxt)
                j += 1
            content = "\n".join(body).strip() or None
            doc_i += 1
            si, su = ordinal(_norm(num), doc_i)   # codified number -> (int, suffix)
            parent = container["chapter"] or container["part"]
            rs.add(parent_local=parent, kind="article", label=f"Art. {num}", heading=None,
                   sort_int=si, sort_suffix=su, role="enacting",
                   citation=f"Law 9610/1998 (Brazil) Art. {num}", content=content)
            i = j
            continue

        i += 1
    return rs


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Ingest Brazil Law No. 9,610/1998 (WIPO Lex EN translation).")
    ap.add_argument("--db", required=True)
    ap.add_argument("--html", required=True, help="path to br_lda.txt (pdftotext -layout of br224en.pdf)")
    ap.add_argument("--source-url", required=True)
    ap.add_argument("--point-in-time", default=None)
    ap.add_argument("--allow-corpus", action="store_true")
    a = ap.parse_args()
    s = run_ingest(a.db, INSTRUMENT, parse(a.html), a.source_url, point_in_time=a.point_in_time,
                   allow_corpus=a.allow_corpus, is_official_language=0,   # English translation
                   version_label="WIPO Lex (EN translation, consolidated as amended by "
                                 "Law 12.853/2013)", fts_title="Law No. 9,610/1998")
    print(f"instrument #{s['instrument_id']}  Brazil Law 9.610/1998 — {s['provisions']} provisions "
          f"({s['by_kind'].get('article', 0)} articles); versions new {s['versions_new']}, "
          f"unchanged {s['versions_unchanged']} (is_official_language=0)")


if __name__ == "__main__":
    main()
