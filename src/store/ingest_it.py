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
# / "Article 110bis". It may carry an inline repeal notice after the number
# ("Article 1828 (repealed)" — the "8" is a glued footnote marker, peeled by _split_article_num).
# CASE-SENSITIVE (only title-case "Article"/"Art.") so the ALL-CAPS "ART. 7" — the header of a
# QUOTED decree (D.Lgs 419/1999) embedded in a footnote — is NOT parsed as an LDA article (F-IT3).
# The number run tolerates a pdftotext letter-for-digit misread (the sole case: "Article l01" =
# letter-'l' + "01" = Art. 101, else absent) — normalised by _ocr_digits before use.
# Trailing prose (footnotes citing "Art. 39 of Decree ...") is excluded by the whole-line anchor.
_ARTICLE = re.compile(
    rf"^\s+(?:Article|Art\.)\s+([\dlIoO]*\d[\dlIoO]*)\s*((?:{_SUFFIX}))?\s*(\([^)]*\))?\s*$")


def _ocr_digits(tok: str) -> str:
    """Repair a pdftotext letter-for-digit misread in an article number ('l01' → '101'):
    l/I→1, O/o→0. Only ever applied to the article-number capture, which the regex already
    requires to hold at least one real digit."""
    return tok.translate(str.maketrans({"l": "1", "I": "1", "O": "0", "o": "0"}))


# A repealed-RANGE tombstone header: "Arts 175-179 [Repealed]" (F-IT4 — the range carries no
# body; source itself shows only this notice).
_ARTRANGE = re.compile(r"^\s*Arts?\s+(\d+)\s*[-–]\s*(\d+)\s*\[?\s*(Repealed)\s*\]?\s*$", re.I)
# Page-footer noise: a bare page number on its own (right-padded) line.
_PAGENO = re.compile(r"^\s*\d{1,3}\s*$")


def _norm_num(n: str, suffix: str | None) -> str:
    """'64' + 'bis' → '64bis'; '20' + None → '20'. Compact form → stable citation."""
    return f"{n}{suffix.lower()}" if suffix else n


def _split_article_num(digits: str, last_num: int) -> int:
    """LDA article numbers run monotonically; a header's digit run may carry a footnote number
    GLUED to it by pdftotext ("Article 182" + footnote "8" → "1828", which had dropped Art. 182
    entirely — F-IT1). Take the shortest leading prefix strictly greater than the previous article
    integer; the rest is footnote noise. Falls back to the full run if nothing beats last_num.
    (Ported from ingest_es._split_article_num.)"""
    full = int(digits)
    if full > last_num and full - last_num < 100:      # already a clean, plausible next number
        return full
    for k in range(1, len(digits)):
        cand = int(digits[:k])
        if cand > last_num:
            return cand
    return full


def _dehyphenate(body: list[str]) -> list[str]:
    """PDF line-break hyphenation: a body line ending in "<word char>-" continues on the next
    line ("73-\\nbis" → "73-bis"; "re-\\nutilization" → "re-utilization"; F-IT5, arts 16bis,
    102bis, 163, 171ter, 174ter). Join such a line to the next with NO break, keeping the hyphen
    (every affected case here is a real hyphenated compound / cross-ref, not a broken single word).
    Also collapse an intra-line "<word>- <word>" split ("art. 102- quater" → "art. 102-quater",
    Art. 71quinquies)."""
    out: list[str] = []
    i = 0
    while i < len(body):
        cur = re.sub(r"(\w)-\s+(\w)", r"\1-\2", body[i])   # "102- quater" → "102-quater"
        while re.search(r"\w-$", cur) and i + 1 < len(body):
            i += 1
            cur = cur + body[i]                            # keep the hyphen, drop the line break
        out.append(cur)
        i += 1
    return out


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

    last_art = 0        # last article INTEGER emitted — monotonic; peels glued footnote digits

    def parent_for_article() -> int | None:
        return (container["subchapter"] or container["chapter"] or container["part"])

    # --- Footnote-8 / quoted-decree block (F-IT2, F-IT3) -------------------------------------
    # pdftotext dropped footnote 8 between the "Article 182 bis" header and the REAL Art. 182-bis
    # text: a footnote body ("see article 7 of the legislative Decree ... 419 ...") followed by
    # the QUOTED text of D.Lgs 419/1999 Art. 7 ("ART. 7 / THE ITALIAN SOCIETY OF AUTHORS AND
    # PUBLISHERS / 1. ... The following articles have been suppressed: - art. 182 ... - art. 57
    # ..."). None of that is enacting LDA text. This block is dropped from any article body it
    # falls into (it lands in Art. 182-bis, whose real text — the AGCOM/SIAE supervision ¶¶1–3 —
    # follows it and is preserved).
    _FN8_START = re.compile(r"^\s*see article 7 of the legislative Decree.*419", re.I)
    _FN8_END = re.compile(r"^\s*-\s*art\.\s*57 of Regulations", re.I)

    def _strip_fn8(body: list[str]) -> list[str]:
        out, skip = [], False
        for s in body:
            if not skip and _FN8_START.match(s):
                skip = True
                continue
            if skip:
                if _FN8_END.match(s):
                    skip = False
                continue
            out.append(s)
        return out

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

        # A repealed article RANGE: "Arts 175-179 [Repealed]" (F-IT4). Emit each article in the
        # range as its own repealed provision, carrying the source's own tombstone notice.
        rm = _ARTRANGE.match(lines[i])
        if rm:
            lo, hi = int(rm.group(1)), int(rm.group(2))
            notice = f"[{rm.group(3).title()}]"          # the SOURCE's own notice, verbatim shape
            for k in range(lo, hi + 1):
                doc_i += 1
                si, su = ordinal(str(k), doc_i)
                rs.add(parent_local=parent_for_article(), kind="article",
                       label=f"Article {k}", heading=None, sort_int=si, sort_suffix=su,
                       citation=f"LDA Art. {k}", content=notice, status="repealed")
            last_art = hi
            i += 1
            continue

        am = _ARTICLE.match(lines[i])
        if am:
            art_int = _split_article_num(_ocr_digits(am.group(1)), last_art)  # OCR-fix + peel glued fn digit
            last_art = art_int
            num = _norm_num(str(art_int), am.group(2))   # "64bis" / "182" / "20"
            notice = (am.group(3) or "").strip()         # inline "(repealed)" tombstone, if any
            body: list[str] = []
            j = i + 1
            while j < n:
                if _HEADER.match(lines[j]) or _ARTICLE.match(lines[j]) or _ARTRANGE.match(lines[j]):
                    break
                s = lines[j].strip()
                if s and not _PAGENO.match(lines[j]):
                    body.append(s)
                j += 1
            body = _dehyphenate(_strip_fn8(body))        # F-IT2/F-IT3 block out, F-IT5 hyphens joined
            content = "\n".join(body).strip() or None
            status = None
            if notice:                                   # a repealed-in-header article (F-IT1)
                content = notice if not content else f"{notice}\n{content}"
                status = "repealed"
            doc_i += 1
            si, su = ordinal(num, doc_i)                 # '64bis'→(64,'BIS'); space form→doc order
            rs.add(parent_local=parent_for_article(), kind="article",
                   label=f"Article {num}", heading=None, sort_int=si, sort_suffix=su,
                   citation=f"LDA Art. {num}", content=content, status=status)
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
