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
    ... then BACK MATTER after the last article (Art. 167):
    Additional Provisions (First–Fifth) · Transitional Provisions (First–Twentieth) ·
    Sole Repealing Provision · Sole Final Provision.
Articles are the RAIL unit (kind='article'; they get the operative content + version + FTS).
Containers → part (Book/Title), chapter (Chapter), subchapter (Section). Article numbers are
mostly plain integers with the odd bis/ter (31 bis, 40 bis, 40 ter); glued footnote digits
(pdftotext artifacts like "Article 2410." = Art. 24 + footnote 10) are stripped off the
number. `_common.ordinal` handles the suffixes (bis/ter fall to document order — fine).
Citations: "TRLPI Art. 32". Container citations: "TRLPI Book I", "TRLPI Art. 31 bis", etc.

Back matter (F-ES2 fix): each Additional/Transitional/Repealing/Final Provision is its OWN
addressable provision (kind='article', grounded verbatim from the source), grouped under a
container 'part' per family. Art. 167's body is cut at the FIRST back-matter heading so it no
longer swallows the ~15k-char tail. Headings are ordinal-word based ("First Additional
Provision.", "Twentieth Transitional Provision76.", "Sole Repealing Provision.") and may carry
a glued footnote number + a wrapped title line. Citations: "TRLPI Additional Provision 1",
"TRLPI Transitional Provision 12", "TRLPI Repeal Provision", "TRLPI Final Provision".

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

# Back matter (after the last article). Each provision heading is flush-left and opens with an
# ordinal WORD ("First".."Twentieth", or "Sole") + a family word (Additional/Transitional/
# Repealing/Final) + "Provision". It may carry a glued footnote number and an inline/wrapped
# title. group(1)=ordinal word, group(2)=family, group(3)=inline title remainder.
_BACKMATTER = re.compile(
    r"^(First|Second|Third|Fourth|Fifth|Sixth|Seventh|Eighth|Ninth|Tenth|Eleventh|Twelfth|"
    r"Thirteenth|Fourteenth|Fifteenth|Sixteenth|Seventeenth|Eighteenth|Nineteenth|Twentieth|"
    r"Sole)\s+(Additional|Transitional|Repealing|Final)\s+Provision\d*\.?\s*(.*)$")

_ORDINAL_WORD = {
    "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6, "seventh": 7,
    "eighth": 8, "ninth": 9, "tenth": 10, "eleventh": 11, "twelfth": 12, "thirteenth": 13,
    "fourteenth": 14, "fifteenth": 15, "sixteenth": 16, "seventeenth": 17, "eighteenth": 18,
    "nineteenth": 19, "twentieth": 20, "sole": 1,
}

# Back-matter families → (container part label, container citation, per-provision citation stem,
# per-provision label stem). The Repealing/Final families are single "Sole" provisions.
_BM_FAMILY = {
    "Additional": ("Additional Provisions", "TRLPI Additional Provisions",
                   "TRLPI Additional Provision", "Additional Provision"),
    "Transitional": ("Transitional Provisions", "TRLPI Transitional Provisions",
                     "TRLPI Transitional Provision", "Transitional Provision"),
    "Repealing": ("Repealing and Final Provisions", "TRLPI Repealing and Final Provisions",
                  "TRLPI Repeal Provision", "Repeal Provision"),
    "Final": ("Repealing and Final Provisions", "TRLPI Repealing and Final Provisions",
              "TRLPI Final Provision", "Final Provision"),
}


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

# A translator FOOTNOTE-DEFINITION line (amendment provenance on its own line) — these are meta
# notes, not operative text: "Subparagraph f) pursuant to … Act 23/2006, dated …", "Article
# repealed by …", "New name pursuant to …". Operative text never opens this way (real repeal
# stubs are captured as the whole article's content, not mid-body).
_FN_DEF = re.compile(
    r"^(Subparagraph|Paragraph)\b.{0,60}?\bpursuant to\b"
    r"|^(Article|Section)\b.{0,30}?\brepealed\b"
    r"|^Repealed by\b|^New (name|wording)\b|^Renamed\b|^Added by\b", re.I)


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
    # back-matter containers, opened lazily & deduped by container citation (Repealing + Final
    # share one "Repealing and Final Provisions" container).
    backmatter: dict[str, int] = {}
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
        if _CONTAINER.match(lines[j]) or _ARTICLE.match(cand) or _BACKMATTER.match(cand):
            return None
        return _strip_fn(cand)

    def is_body_stop(idx: int) -> bool:
        """True when line `idx` opens a new addressable unit — a container, a real article
        header, or a back-matter provision heading — where a running body must stop."""
        raw2 = lines[idx]
        if _CONTAINER.match(raw2):
            return True
        stripped = raw2.strip()
        if _ARTICLE.match(raw2) and blank_before(idx):
            return True
        if _BACKMATTER.match(stripped) and blank_before(idx):
            return True
        return False

    def collect_body(start: int) -> tuple[list[str], int]:
        """Gather a provision's body from line `start` until the next unit boundary, dropping
        footnote-apparatus noise (lone footnote numbers + their indented footnote text) and
        standalone footnote-definition lines. Returns (body_lines, index_after_body)."""
        body: list[str] = []
        j = start
        while j < n:
            if is_body_stop(j):
                break
            nxt_raw = lines[j]
            nxt = nxt_raw.strip()
            if _FN_LINE.match(nxt_raw):            # a footnote NUMBER — skip it AND its indented
                j += 1                             # footnote-TEXT line(s) (operative text is flush-left,
                while j < n and lines[j][:1].isspace() and lines[j].strip():   # so leading-space = footnote)
                    j += 1
                continue
            if nxt and not _FN_DEF.match(nxt):     # skip standalone footnote-definition lines
                body.append(nxt)
            j += 1
        return body, j

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
            # body = lines until the next unit boundary (incl. the FIRST back-matter heading, so
            # Art. 167 stops at "First Additional Provision." instead of swallowing the tail)
            body, _ = collect_body(i + 1)
            content = "\n".join(body).strip() or None
            doc_i += 1
            # ordinal needs the suffix UNSPACED ("31bis") — the spaced form "31 bis" fails the
            # numeric regex and collapses to doc order, colliding with real Arts 44/54/56.
            si, su = ordinal(f"{num}{suffix}", doc_i)
            rs.add(parent_local=parent_for_article(), kind="article",
                   label=f"Article {art_key}", heading=title, sort_int=si, sort_suffix=su,
                   citation=f"TRLPI Art. {art_key}", content=content)
            continue

        bm = _BACKMATTER.match(line)
        if bm and blank_before(i):                # a back-matter provision heading
            word, family, inline = bm.group(1), bm.group(2), bm.group(3)
            num = _ORDINAL_WORD[word.lower()]
            part_label, part_cit, prov_cit_stem, prov_label_stem = _BM_FAMILY[family]
            # open (once, deduped by citation) the family container, in first-seen order
            if part_cit not in backmatter:
                doc_i += 1
                backmatter[part_cit] = rs.add(
                    parent_local=None, kind="part", label=part_label,
                    heading=part_label, sort_int=doc_i, sort_suffix="",
                    citation=part_cit)
            container_lid = backmatter[part_cit]
            # heading = inline title + any wrapped continuation lines. The source separates the
            # title from the body with a BLANK line, so title-wrap = the non-blank lines that
            # immediately follow the heading (no intervening blank). Body starts after that blank.
            head_parts = [inline.strip()] if inline and inline.strip() else []
            b = i + 1
            while b < n and lines[b].strip() and not is_body_stop(b) \
                    and not _FN_LINE.match(lines[b]):
                head_parts.append(lines[b].strip())
                b += 1
            body, _ = collect_body(b)
            heading = _strip_fn(" ".join(head_parts).strip()) if head_parts else None
            content = "\n".join(body).strip() or None
            doc_i += 1
            # Sole Repealing / Sole Final are single provisions (no numeric suffix in citation).
            if family in ("Repealing", "Final"):
                citation, label = prov_cit_stem, prov_label_stem
            else:
                citation = f"{prov_cit_stem} {num}"
                label = f"{prov_label_stem} {num}"
            rs.add(parent_local=container_lid, kind="article", label=label,
                   heading=heading, sort_int=doc_i, sort_suffix="",
                   citation=citation, content=content)
            continue
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
