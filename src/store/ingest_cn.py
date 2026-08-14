"""Tier-2 ingest — China, Copyright Law of the People's Republic of China (2020 Amendment).

Per the Tier-2 fan-out contract (see ingest_de_urhg.py): an INSTRUMENT dict + a `parse()`
returning a `_common.RecordSet` + a thin `main()`. All DB/versioning/idempotency lives in
`_common`. NEVER originates text — every article body is lifted verbatim from the fetched
source.

Source: WIPO Lex "China — Copyright Law of the People's Republic of China (amended up to
November 11, 2020)" ENGLISH translation, the signed PDF cn413en_1.pdf (WIPO Lex record
21065, in force 2021-06-01). It is a TRANSLATION (authentic language = Chinese), so
`run_ingest(..., is_official_language=0)` (flagged in the UI). Retained artifact:
spike/artifacts/cn_copyright.txt (the WIPO PDF's text — pass it via --html).

Structure (China): Chapters (I–VI) → Sections (only within Ch. II Copyright and Ch. IV
Copyright-related Rights) → Articles 1..67. Articles carry the operative content and RAIL in
the reader (kind='article'); Chapters → kind='chapter', Sections → kind='subchapter' (both
addressable, shareless containers). Citations: "Copyright Law (China) Art. N".

Parse note: the WIPO text flows articles inline (two "Article N" headers can share a line,
and body prose contains cross-references like "as provided in Article 10"). Articles are
numbered strictly 1..67, so an `Article N` marker is accepted as a real header ONLY when N is
the next expected number; every other `Article N` is an in-body cross-reference and is left in
the body. The leading Contents/TOC block (a single line listing every Chapter/Section) is
skipped by starting the scan at the SECOND "Chapter I" (the real body header).

Run:
    python src/store/ingest_cn.py --db db/corpus.db --allow-corpus \
        --html spike/artifacts/cn_copyright.txt \
        --source-url https://www.wipo.int/wipolex/en/legislation/details/21065
"""
from __future__ import annotations

import argparse
import re

from _common import RecordSet, ordinal, run_ingest

INSTRUMENT = dict(jurisdiction="CN", type="statute",
                  official_citation="Copyright Law of the PRC (2020)",
                  ext_id_scheme="NATIONAL", ext_id="cn-copyright-2020",
                  title="Copyright Law of the People's Republic of China (2020 Amendment)")

# Chapter roman numerals in document order → their integer ordinal (for sort_int).
_ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6}

_CH = re.compile(r"\bChapter\s+(I|II|III|IV|V|VI)\b")
_SEC = re.compile(r"\bSection\s+(\d+)\b")
_ART = re.compile(r"\bArticle\s+(\d+)\b")


def _clean(frag: str) -> str:
    return re.sub(r"\s+", " ", frag or "").strip()


def parse(path: str) -> RecordSet:
    text = open(path, encoding="utf-8", errors="replace").read()
    # Skip the Contents/TOC block: the real body begins at the SECOND "Chapter I".
    first = text.find("Chapter I ")
    body_at = text.find("Chapter I ", first + 5) if first >= 0 else -1
    body = text[body_at:] if body_at >= 0 else text

    # Collect every candidate marker, then accept articles only in strict 1..N sequence
    # (rejecting inline cross-references). Chapters/Sections are always structural.
    cands: list[tuple[int, int, str, object]] = []
    for m in _CH.finditer(body):
        cands.append((m.start(), m.end(), "chapter", m.group(1)))
    for m in _SEC.finditer(body):
        cands.append((m.start(), m.end(), "section", m.group(1)))
    for m in _ART.finditer(body):
        cands.append((m.start(), m.end(), "article", int(m.group(1))))
    cands.sort()

    markers: list[tuple[int, int, str, object]] = []
    expected = 1
    for start, end, kind, val in cands:
        if kind == "article":
            if val == expected:          # next expected number → real header
                markers.append((start, end, kind, val))
                expected += 1
            # else: an in-body cross-reference — leave it in the prose
        else:
            markers.append((start, end, kind, val))

    rs = RecordSet()
    chapter_lid: int | None = None
    chapter_roman: str | None = None            # roman numeral of the OPEN chapter (for Sec. citations)
    section_lid: int | None = None

    for i, (start, end, kind, val) in enumerate(markers):
        seg = body[end: markers[i + 1][0] if i + 1 < len(markers) else len(body)]
        if kind == "chapter":
            roman = val
            si, _ = ordinal(str(_ROMAN[roman]), _ROMAN[roman])
            heading = _clean(seg) or None       # text up to the next marker = chapter title
            chapter_lid = rs.add(parent_local=None, kind="chapter",
                                 label=f"Chapter {roman}", heading=heading,
                                 sort_int=si, citation=f"Copyright Law (China) Ch. {roman}")
            chapter_roman = roman
            section_lid = None                  # a new chapter clears the open section
        elif kind == "section":
            num = val
            si, su = ordinal(num, i)
            heading = _clean(seg) or None
            # F-CN1: cite the ENCLOSING CHAPTER's roman numeral, not the section number
            # ("Ch. II Sec. 3", not "Ch. 3 Sec. 3"). Section numbers repeat across chapters
            # (Ch. II and Ch. IV each hold Sections 1–4) but the chapter qualifier makes the
            # citation unique — no #N uniquifier (never a minted pinpoint, ingest rule 1).
            section_lid = rs.add(parent_local=chapter_lid, kind="subchapter",
                                 label=f"Section {num}", heading=heading,
                                 sort_int=si, sort_suffix=su,
                                 citation=f"Copyright Law (China) Ch. {chapter_roman} Sec. {num}")
        else:  # article — the operative, versioned content
            num = str(val)
            si, su = ordinal(num, i)
            content = _clean(seg) or None
            rs.add(parent_local=section_lid or chapter_lid, kind="article",
                   label=f"Article {num}", heading=None, sort_int=si, sort_suffix=su,
                   citation=f"Copyright Law (China) Art. {num}", content=content)
    return rs


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Ingest China Copyright Law 2020 (WIPO Lex EN translation).")
    ap.add_argument("--db", required=True)
    ap.add_argument("--html", required=True,
                    help="path to cn_copyright.txt (text of WIPO Lex cn413en_1.pdf)")
    ap.add_argument("--source-url", required=True)
    ap.add_argument("--point-in-time", default=None)
    ap.add_argument("--allow-corpus", action="store_true")
    a = ap.parse_args()
    s = run_ingest(a.db, INSTRUMENT, parse(a.html), a.source_url,
                   point_in_time=a.point_in_time, allow_corpus=a.allow_corpus,
                   is_official_language=0,   # English translation; authentic language = Chinese
                   version_label="WIPO Lex (EN translation, 2020 Amendment, in force 2021-06-01)",
                   fts_title="Copyright Law (China)")
    print(f"instrument #{s['instrument_id']}  China Copyright Law 2020 — {s['provisions']} "
          f"provisions ({s['by_kind'].get('article', 0)} articles, "
          f"{s['by_kind'].get('chapter', 0)} chapters, {s['by_kind'].get('subchapter', 0)} "
          f"sections); versions new {s['versions_new']}, unchanged {s['versions_unchanged']} "
          f"(is_official_language=0)")


if __name__ == "__main__":
    main()
