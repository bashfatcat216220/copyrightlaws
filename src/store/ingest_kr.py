"""Tier-2 ingest — Republic of Korea, Copyright Act.

Per the Tier-2 fan-out contract (see ingest_de_urhg.py): an INSTRUMENT dict + a `parse()`
returning a `_common.RecordSet` + a thin `main()`. All DB/versioning/idempotency lives in
`_common`. NEVER originates text — every article body is lifted from the fetched source.

Source: the Korea Law Translation Center (KLRI) English full text of the Copyright Act
(Act No. 432 of 1957, wholly amended; current), served at
elaw.klri.re.kr/eng_service/lawViewContent.do?hseq=32626. The English is a government-
provided TRANSLATION (authentic language = Korean) and KLRI labels its translations
"for reference only, neither official nor legally effective" → `run_ingest(...,
is_official_language=0)` (flagged in the UI).

Structure (from the KLRI HTML):
    CHAPTER (div.chapter) → SECTION (div.section) → SubSection (div.subsection)
      → Article N (div.JO / div.articletitle) — the operative, versioned unit.
Korea uses ARTICLES with "-N" insertions (e.g. Article 2-2, Article 35-3 fair use), which
`_common.ordinal` handles: "35-3" → (35, "") so it document-orders after 35 within the
single authoritative fetch. Articles RAIL in the reader (kind='article'); containers are
chapter / subchapter (Section) / subsection (SubSection). Citations: "Copyright Act (Korea)
Art. N".

Run:
    python src/store/ingest_kr.py --db db/corpus.db --allow-corpus \
        --html spike/artifacts/kr_copyright.html \
        --source-url https://elaw.klri.re.kr/eng_service/lawViewContent.do?hseq=32626
"""
from __future__ import annotations

import argparse
import html as htmlmod
import re

from _common import RecordSet, ordinal, run_ingest

INSTRUMENT = dict(jurisdiction="KR", type="statute",
                  official_citation="Copyright Act (Korea)",
                  ext_id_scheme="NATIONAL", ext_id="kr-copyright",
                  title="Copyright Act, Republic of Korea")

# Structural blocks in the KLRI HTML. Chapter → 'chapter', Section → 'subchapter',
# SubSection → 'subsection'; an Article (div.JO) is the operative provision.
_CHAPTER = re.compile(r'<div class="chapter"[^>]*>(.*?)</div>', re.S)
_SECTION = re.compile(r'<div class="section"[^>]*>(.*?)</div>', re.S)
_SUBSEC = re.compile(r'<div class="subsection"[^>]*>(.*?)</div>', re.S)
# A structural container or article block, in document order.
_BLOCK = re.compile(
    r'<div class="(chapter|section|subsection)"[^>]*>(.*?)</div>'
    r'|<div class="JO" id="\d+">(.*?)(?=<div class="(?:JO|CT|ST|UT|addenda)"|\Z)',
    re.S)
# The article header cell: "Article 35-3 (Fair Use of Works, etc.)".
_ARTTITLE = re.compile(r'<div class="articletitle">(.*?)</table>', re.S)
_ARTNUM = re.compile(r'Article\s+(\d+(?:-\d+)?)\s*(?:\((.*?)\))?', re.S)


def _clean(frag: str) -> str:
    frag = re.sub(r"<!--.*?-->", " ", frag or "", flags=re.S)   # drop HTML comments (incl. "-->")
    frag = re.sub(r"<[^>]+>", " ", frag)
    frag = frag.replace("법령보기 화면", " ")  # table caption "법령보기 화면"
    return re.sub(r"\s+", " ", htmlmod.unescape(frag)).strip()


def parse(html_path: str) -> RecordSet:
    html = open(html_path, encoding="utf-8", errors="replace").read()
    # Stop before the addenda (transitional/amendment history) — articles only.
    end = html.find('class="addenda"')
    if end != -1:
        html = html[:end]

    rs = RecordSet()
    container = {"chapter": None, "subchapter": None, "subsection": None}  # open container local ids
    doc_i = 0

    for m in _BLOCK.finditer(html):
        ctype, ctext, jobody = m.group(1), m.group(2), m.group(3)
        doc_i += 1

        if ctype == "chapter":
            heading = _clean(ctext)                       # "CHAPTER I GENERAL PROVISIONS"
            container["subchapter"] = container["subsection"] = None
            si, su = ordinal(str(doc_i), doc_i)
            container["chapter"] = rs.add(parent_local=None, kind="chapter", label=heading,
                                          heading=heading, sort_int=si, sort_suffix=su,
                                          citation=f"Copyright Act (Korea) — {heading}")
            continue
        if ctype == "section":
            heading = _clean(ctext)                       # "Section 1 Works"
            container["subsection"] = None
            si, su = ordinal(str(doc_i), doc_i)
            container["subchapter"] = rs.add(parent_local=container["chapter"], kind="subchapter",
                                             label=heading, heading=heading, sort_int=si,
                                             sort_suffix=su,
                                             citation=f"Copyright Act (Korea) — {heading}")
            continue
        if ctype == "subsection":
            heading = _clean(ctext)                       # "SubSection 1 Kinds of ..."
            si, su = ordinal(str(doc_i), doc_i)
            parent = container["subchapter"] or container["chapter"]
            container["subsection"] = rs.add(parent_local=parent, kind="subsection",
                                             label=heading, heading=heading, sort_int=si,
                                             sort_suffix=su,
                                             citation=f"Copyright Act (Korea) — {heading}")
            continue

        # else: an article block (jobody set)
        tm = _ARTTITLE.search(jobody or "")
        head = _clean(tm.group(1)) if tm else ""
        am = _ARTNUM.match(head)
        if not am:
            continue
        num, title = am.group(1), (am.group(2) or None)
        body = _clean(jobody[tm.end():]) if tm else _clean(jobody)
        si, su = ordinal(num, doc_i)                       # "35-3" → (35,"") → doc order within 35s
        parent = container["subsection"] or container["subchapter"] or container["chapter"]
        rs.add(parent_local=parent, kind="article", label=f"Article {num}",
               heading=title, sort_int=si, sort_suffix=su,
               citation=f"Copyright Act (Korea) Art. {num}", content=body or None)
    return rs


def main() -> None:
    ap = argparse.ArgumentParser(description="Ingest Korea Copyright Act (KLRI EN translation).")
    ap.add_argument("--db", required=True)
    ap.add_argument("--html", required=True, help="path to kr_copyright.html (KLRI lawViewContent)")
    ap.add_argument("--source-url", required=True)
    ap.add_argument("--point-in-time", default=None)
    ap.add_argument("--allow-corpus", action="store_true")
    a = ap.parse_args()
    s = run_ingest(a.db, INSTRUMENT, parse(a.html), a.source_url, point_in_time=a.point_in_time,
                   allow_corpus=a.allow_corpus, is_official_language=0,   # English translation
                   version_label="KLRI elaw.klri.re.kr (EN translation)",
                   fts_title="Copyright Act (Korea)")
    print(f"instrument #{s['instrument_id']}  Korea Copyright Act — {s['provisions']} provisions "
          f"({s['by_kind'].get('article', 0)} articles); versions new {s['versions_new']}, "
          f"unchanged {s['versions_unchanged']} (is_official_language=0)")


if __name__ == "__main__":
    main()
