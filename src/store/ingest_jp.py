"""Tier-2 ingest — Japan, Copyright Act (Act No. 48 of 1970, as amended).

Per the Tier-2 fan-out contract (see ingest_de_urhg.py): an INSTRUMENT dict + a `parse()`
returning a `_common.RecordSet` + a thin `main()`. All DB/versioning/idempotency lives in
`_common`. NEVER originates text — every article body is lifted from the fetched source.

Source: the Japanese Law Translation database (japaneselawtranslation.go.jp), the Japanese
government's official English-translation portal. This is a GOVERNMENT TRANSLATION (the
authentic language is Japanese; the site itself states only the Japanese text has legal
effect) → `run_ingest(..., is_official_language=0)` (flagged in the UI), but it is an
authentic, consolidated rendering of the Act as amended (is_authentic=1, is_consolidated=1).

Structure (from the clean HTML on view/3379/en):
    Chapter I..VIII → Section N → Subsection N → Article N
Not every chapter has sections/subsections; an article hangs off its nearest open container.
Articles carry hyphenated insertions (Article 30-2, Article 122-2) — handed to
`_common.ordinal`, which keys off the leading integer and falls back to document order for
the hyphen part (authoritative from the single fetch). Articles RAIL in the reader
(kind='article', operative content); containers are chapter/section/subsection.

Scope: the Act's OPERATIVE MAIN BODY only (Chapters I–VIII, Articles 1–124). The trailing
"Supplementary Provisions" blocks — one per amending act, each locally RE-numbering
"Article 1", "Article 2"… (transitional/effective-date text) — are deliberately excluded:
they are amendment scaffolding, not the operative Act, and their restarting numbering would
collide dozens of times over. The hard stop is the first `SupplProvision` block.

Citations: "Copyright Act (Japan) Art. 30" — stable, unique across the main body.

Run:
    python src/store/ingest_jp.py --db db/corpus.db --allow-corpus \
        --html spike/artifacts/jp_copyright.html \
        --source-url https://www.japaneselawtranslation.go.jp/en/laws/view/3379/en
"""
from __future__ import annotations

import argparse
import html as htmlmod
import re

from _common import RecordSet, ordinal, run_ingest

INSTRUMENT = dict(jurisdiction="JP", type="statute",
                  official_citation="Copyright Act (Act No. 48 of 1970)",
                  ext_id_scheme="NATIONAL", ext_id="jp-copyright-1970",
                  title="Copyright Act (Act No. 48 of 1970), Japan")

# Structural markers in document order. Each alternative captures either a container title
# (Chapter/Section/Subsection) or the opening of an Article div (whose number/caption we read
# from the segment that follows). japaneselawtranslation renders these as flat, labelled divs.
_MARK = re.compile(
    r'<div class="Chapter anchor"[^>]*>\s*<div class="ChapterTitle">([^<]*)</div>'
    r'|<div class="Section anchor"[^>]*>\s*<div class="SectionTitle">([^<]*)</div>'
    r'|<div class="Subsection anchor"[^>]*>\s*<div class="SubsectionTitle">([^<]*)</div>'
    r'|<div class="Article anchor" id="[^"]*">')
_ART_TITLE = re.compile(r'<span class="ArticleTitle">Article ([0-9]+(?:-[0-9]+)?)</span>')
_CAPTION = re.compile(r'<div class="ArticleCaption">([^<]*)</div>')
# Container title splits into a label ("Chapter I") + heading (the rest).
_CONTAINER = re.compile(r'^(Chapter|Section|Subsection)\s+(\S+)\s*(.*)$')


def _clean(frag: str) -> str:
    frag = re.sub(r"<[^>]+>", " ", frag or "")
    return re.sub(r"\s+", " ", htmlmod.unescape(frag)).strip()


def parse(html_path: str) -> RecordSet:
    html = open(html_path, encoding="utf-8", errors="replace").read()
    # Operative main body: first Chapter div → first Supplementary Provisions block.
    start = html.find('<div class="Chapter anchor"')
    end = html.find('<div class="SupplProvision anchor"')
    if start < 0:
        raise SystemExit("could not locate the Act body (no Chapter anchor) — wrong source file?")
    body = html[start: end if end > start else len(html)]

    marks = list(_MARK.finditer(body))
    rs = RecordSet()
    container = {"chapter": None, "section": None, "subsection": None}   # open container local ids

    for i, m in enumerate(marks):
        seg = body[m.end(): marks[i + 1].start() if i + 1 < len(marks) else len(body)]
        ch_t, sc_t, sb_t = m.group(1), m.group(2), m.group(3)

        if ch_t or sc_t or sb_t:                       # a container marker
            title = _clean(ch_t or sc_t or sb_t)
            cm = _CONTAINER.match(title)
            unit = (cm.group(1) if cm else ("Chapter" if ch_t else "Section" if sc_t else "Subsection"))
            num = cm.group(2) if cm else ""
            heading = (cm.group(3).strip() or None) if cm else title
            kind = {"Chapter": "chapter", "Section": "section", "Subsection": "subsection"}[unit]
            si, su = ordinal(num, i)                    # roman/int → falls back to doc order
            label = f"{unit} {num}".strip()
            if kind == "chapter":
                container["section"] = container["subsection"] = None
                parent = None
            elif kind == "section":
                container["subsection"] = None
                parent = container["chapter"]
            else:  # subsection
                parent = container["section"] or container["chapter"]
            container[kind] = rs.add(parent_local=parent, kind=kind, label=label,
                                     heading=heading, sort_int=si, sort_suffix=su,
                                     citation=f"Copyright Act (Japan) {label}")
            continue

        # an Article div — read its number (from the segment) and caption
        at = _ART_TITLE.search(seg)
        if not at:
            continue
        num = at.group(1)
        cap = _CAPTION.search(seg)
        heading = _clean(cap.group(1)).strip("() ") or None if cap else None
        # Body text = the segment with its leading caption + the Article-title span removed, so
        # the stored content reads as clean provision prose (no duplicated caption/label).
        inner = seg
        if cap:
            inner = inner.replace(cap.group(0), " ", 1)
        inner = _ART_TITLE.sub(" ", inner, count=1)
        content = _clean(inner) or None
        parent = container["subsection"] or container["section"] or container["chapter"]
        si, su = ordinal(num, i)                        # hyphenated (30-2) → int + doc-order fallback
        rs.add(parent_local=parent, kind="article", label=f"Article {num}", heading=heading,
               sort_int=si, sort_suffix=su, citation=f"Copyright Act (Japan) Art. {num}",
               content=content)
    return rs


def main() -> None:
    ap = argparse.ArgumentParser(description="Ingest Japan Copyright Act (Japanese Law "
                                             "Translation, government EN translation).")
    ap.add_argument("--db", required=True)
    ap.add_argument("--html", required=True, help="path to jp_copyright.html (view/3379/en)")
    ap.add_argument("--source-url", required=True)
    ap.add_argument("--point-in-time", default=None)
    ap.add_argument("--allow-corpus", action="store_true")
    a = ap.parse_args()
    s = run_ingest(a.db, INSTRUMENT, parse(a.html), a.source_url, point_in_time=a.point_in_time,
                   allow_corpus=a.allow_corpus, is_official_language=0,   # government EN translation
                   version_label="Japanese Law Translation (government EN translation)",
                   fts_title="Copyright Act (Japan)")
    print(f"instrument #{s['instrument_id']}  Japan Copyright Act — {s['provisions']} provisions "
          f"({s['by_kind'].get('article', 0)} articles, {s['by_kind'].get('chapter', 0)} chapters, "
          f"{s['by_kind'].get('section', 0)} sections, {s['by_kind'].get('subsection', 0)} "
          f"subsections); versions new {s['versions_new']}, unchanged {s['versions_unchanged']} "
          f"(is_official_language=0)")


if __name__ == "__main__":
    main()
