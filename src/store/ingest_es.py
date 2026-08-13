"""Tier-2 ingest — Spain, Consolidated Text of the Law on Intellectual Property (TRLPI).

Per the Tier-2 fan-out contract (see ingest_de_urhg.py / ingest_fr.py): an INSTRUMENT dict
+ a `parse()` returning a `_common.RecordSet` + a thin `main()`. All DB/versioning/idempotency
lives in `_common`. NEVER originates text — every article body is lifted from the fetched source.

Source: WIPO Lex "Spain — Consolidated Text of the Law on Intellectual Property" (record
14311 / details page 20049; signed English PDF es177en.pdf). The English is an OFFICIAL
Spanish Ministry of Justice translation ("Traducciones del derecho español", NIPO
051-12-014-X) that itself states it "no tiene carácter oficial" — i.e. an unofficial
TRANSLATION of an authentic, consolidated Spanish original. So:
    is_official_language=0 (authentic language = Spanish; flagged in the UI)
    is_authentic=1, is_consolidated=1 (a consolidated statutory text)
Consolidated as approved by Royal Legislative Decree 1/1996 and amended up to RDL 20/2011.

Structure (from the PDF, converted via `pdftotext -layout`):
    BOOK → TITLE → CHAPTER → SECTION → Article N
Articles are the RAIL unit (kind='article'; they get the operative content + version + FTS).
Containers → part (Book/Title), chapter (Chapter), subchapter (Section). Article numbers are
mostly plain integers with the odd bis/ter (31 bis, 40 bis, 40 ter); glued footnote digits
(pdftotext artifacts like "Article 2410." = Art. 24 + footnote 10) are stripped off the
number. `_common.ordinal` handles the suffixes (bis/ter fall to document order — fine).
Citations: "TRLPI Art. 32". Container citations: "TRLPI Book I", "TRLPI Art. 31 bis", etc.

Parse guards (pdftotext realities):
  * A REAL article header is preceded by a BLANK line; mid-sentence cross-references that
    happen to start a wrapped line ("Article 40." carried over from "...provisions of /
    Article 40.", "Article 12 of this Act ...", "Article 20.2.i) ...") are NOT — the
    blank-before rule + a strict header regex exclude them.
  * Containers are centre-indented (leading whitespace); articles are flush-left.
  * Trailing footnote numbers on headings ("Authors66.", "CHAPTER III 22") are stripped.

Run:
    python src/store/ingest_es.py --db db/corpus.db --allow-corpus \
        --html spike/artifacts/es_lpi.txt \
        --source-url https://www.wipo.int/wipolex/en/legislation/details/14311
"""
from __future__ import annotations

import argparse
import re

from _common import RecordSet, ordinal, run_ingest

INSTRUMENT = dict(jurisdiction="ES", type="statute",
                  official_citation="TRLPI (RDL 1/1996)",
                  ext_id_scheme="NATIONAL", ext_id="es-trlpi-1996",
                  title="Consolidated Text of the Law on Intellectual Property (Spain)")

# Structural containers → provisions.kind. Book & Title both nest as 'part' (Title under
# Book), Chapter → 'chapter', Section → 'subchapter'. All addressable but shareless.
_KIND = {"BOOK": "part", "TITLE": "part", "CHAPTER": "chapter", "SECTION": "subchapter"}

# A container header is a CENTRE-INDENTED whole line: keyword + roman (BOOK/TITLE/CHAPTER) or
# an arabic number for SECTION, then an optional inline title (SECTION) / trailing footnote #.
_CONTAINER = re.compile(
    r"^\s+(BOOK|TITLE|CHAPTER)\s+([IVXLC]+)\b\s*\d*\s*$"
    r"|^\s+(SECTION)\s+(\d+)\.\s*(.*?)\s*\d*\s*$")

# A REAL article header (flush-left): "Article <digits>[ bis|ter|quater]." then an optional
# inline title. Excludes cross-refs like "Article 12 of this Act" (no dot after the number)
# and "Article 20.2.i)" (a dotted sub-number, not a header period). The digit run may have a
# footnote number GLUED to it (pdftotext artifact: "Article 2410." = Art. 24 + footnote 10);
# `_split_article_num` peels that off using document-order monotonicity.
_ARTICLE = re.compile(r"^Article\s+(\d+)(\s+bis|\s+ter|\s+quater)?\.\s*(.*)$")


def _split_article_num(digits: str, last_num: int) -> int:
    """Article numbers are monotonic; a header's digit run may carry a glued footnote number
    (e.g. '2410' after Art. 23 → article 24, footnote 10). Take the shortest leading prefix
    that is strictly greater than the previous article number — that is the article number;
    the rest is footnote noise. Falls back to the full run if nothing beats last_num."""
    full = int(digits)
    if full > last_num and full - last_num < 100:      # already a clean, plausible next number
        return full
    for k in range(1, len(digits)):
        cand = int(digits[:k])
        if cand > last_num:
            return cand
    return full

# A lone-digit line is pdftotext footnote-apparatus noise (a page-bottom reference marker or
# a footnote-body number), NOT a legislative list item (those read "1. text" on one line).
# Such lines break paragraph flow: they must be dropped from bodies AND treated as
# blank-equivalent when testing whether an article header follows a blank line.
_FN_LINE = re.compile(r"^\s*\d{1,3}\s*$")


def _strip_fn(text: str | None) -> str | None:
    """Drop a trailing footnote number some headings carry ('Authors66.' → 'Authors')."""
    if not text:
        return None
    t = text.strip()
    t = re.sub(r"(\D)\d+\.?$", r"\1", t).strip()     # 'Authors66.' → 'Authors'
    return t.rstrip(".").strip() or None


def _lines(path: str) -> list[str]:
    text = open(path, encoding="utf-8", errors="replace").read().replace("\f", "")
    return [ln.rstrip() for ln in text.split("\n")]


def parse(path: str) -> RecordSet:
    lines = _lines(path)
    rs = RecordSet()
    # open container ids by slot; a shallower container clears the deeper ones below it
    container = {"book": None, "title": None, "chapter": None, "section": None}
    doc_i = 0
    n = len(lines)
    started = False        # only start emitting once BOOK I (the operative body) is reached
    last_art = 0           # last article integer seen — monotonic; disambiguates glued footnotes

    def blank_before(idx: int) -> bool:
        """A header 'follows a blank line' if the preceding non-noise line is blank — lone
        footnote-number lines (pdftotext apparatus) count as blank for this test."""
        k = idx - 1
        while k >= 0 and _FN_LINE.match(lines[k]):
            k -= 1
        return k < 0 or lines[k].strip() == ""

    def parent_for_article() -> int | None:
        return (container["section"] or container["chapter"] or
                container["title"] or container["book"])

    def next_nonblank_heading(i: int) -> str | None:
        j = i + 1
        while j < n and not lines[j].strip():
            j += 1
        if j >= n:
            return None
        cand = lines[j].strip()
        if _CONTAINER.match(lines[j]) or _ARTICLE.match(cand):
            return None
        return _strip_fn(cand)

    for i in range(n):
        raw = lines[i]
        line = raw.strip()
        if not line:
            continue

        cm = _CONTAINER.match(raw)
        if cm:
            if cm.group(1):                       # BOOK / TITLE / CHAPTER (roman)
                unit, num, inline = cm.group(1), cm.group(2), None
            else:                                 # SECTION (arabic, inline title)
                unit, num, inline = cm.group(3), cm.group(4), _strip_fn(cm.group(5))
            if unit == "BOOK":
                started = True
            doc_i += 1
            si, su = ordinal(num, doc_i)          # roman → falls back to doc order
            heading = inline or next_nonblank_heading(i)
            kind = _KIND[unit]
            label = f"{unit.title()} {num}"
            if unit == "BOOK":
                container["title"] = container["chapter"] = container["section"] = None
                parent, slot = None, "book"
            elif unit == "TITLE":
                container["chapter"] = container["section"] = None
                parent, slot = container["book"], "title"
            elif unit == "CHAPTER":
                container["section"] = None
                parent = container["title"] or container["book"]
                slot = "chapter"
            else:  # SECTION
                parent = container["chapter"] or container["title"] or container["book"]
                slot = "section"
            container[slot] = rs.add(parent_local=parent, kind=kind, label=label,
                                     heading=heading, sort_int=si, sort_suffix=su,
                                     citation=f"TRLPI {label}")
            continue

        if not started:
            continue

        if _FN_LINE.match(raw):                   # footnote-apparatus noise line — skip
            continue

        am = _ARTICLE.match(raw)
        if am and blank_before(i):                # real header ⇒ preceded by a blank line
            num = _split_article_num(am.group(1), last_art)   # peel any glued footnote number
            last_art = num
            suffix = (am.group(2) or "").strip()  # 'bis' / 'ter' / ''
            art_key = f"{num} {suffix}".strip()   # "31 bis" / "24"
            title = _strip_fn(am.group(3))
            # body = lines until the next header/container, dropping footnote-apparatus noise
            body: list[str] = []
            j = i + 1
            while j < n:
                nxt_raw = lines[j]
                nxt = nxt_raw.strip()
                if _CONTAINER.match(nxt_raw):
                    break
                am2 = _ARTICLE.match(nxt_raw)
                if am2 and blank_before(j):        # next real article header ⇒ stop
                    break
                if nxt and not _FN_LINE.match(nxt_raw):
                    body.append(nxt)
                j += 1
            content = "\n".join(body).strip() or None
            doc_i += 1
            si, su = ordinal(art_key, doc_i)       # bis/ter → doc-order fallback
            rs.add(parent_local=parent_for_article(), kind="article",
                   label=f"Article {art_key}", heading=title, sort_int=si, sort_suffix=su,
                   citation=f"TRLPI Art. {art_key}", content=content)
    return rs


def main() -> None:
    ap = argparse.ArgumentParser(description="Ingest Spain TRLPI (WIPO Lex EN translation).")
    ap.add_argument("--db", required=True)
    ap.add_argument("--html", required=True, help="path to es_lpi.txt (pdftotext of es177en.pdf)")
    ap.add_argument("--source-url", required=True)
    ap.add_argument("--point-in-time", default=None)
    ap.add_argument("--allow-corpus", action="store_true")
    a = ap.parse_args()
    s = run_ingest(a.db, INSTRUMENT, parse(a.html), a.source_url, point_in_time=a.point_in_time,
                   allow_corpus=a.allow_corpus,
                   is_official_language=0,        # unofficial English translation
                   is_authentic=1, is_consolidated=1,
                   version_label="WIPO Lex (EN translation, consolidated up to RDL 20/2011)",
                   fts_title="TRLPI")
    print(f"instrument #{s['instrument_id']}  Spain TRLPI — {s['provisions']} provisions "
          f"({s['by_kind'].get('article', 0)} articles); versions new {s['versions_new']}, "
          f"unchanged {s['versions_unchanged']} (is_official_language=0)")


if __name__ == "__main__":
    main()
