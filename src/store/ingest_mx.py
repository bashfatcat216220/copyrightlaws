"""Tier-2 ingest — Mexico, Federal Law on Copyright (Ley Federal del Derecho de Autor, LFDA).

Per the Tier-2 fan-out contract (see ingest_de_urhg.py / ingest_fr.py): an INSTRUMENT dict +
a `parse()` returning a `_common.RecordSet` + a thin `main()`. All DB/versioning/idempotency
lives in `_common`. NEVER originates text — every article body is lifted from the fetched source.

Source: WIPO Lex English text-view of Mexico's Federal Law on Copyright
(https://www.wipo.int/wipolex/en/text/476907), the International Bureau of WIPO's English
translation of the law published in the Diario Oficial of 24 December 1996 (in force 24 March
1997). The body carries the note "Translation by the International Bureau of WIPO" — it is an
unofficial TRANSLATION (authentic language = Spanish), so `run_ingest(..., is_official_language=0)`
(flagged in the UI). WIPO no longer serves the legacy English `.pdf`; the servable clean-English
source is this server-rendered text-view HTML, retained as spike/artifacts/mx_lfda.html and
extracted to spike/artifacts/mx_lfda.txt (this ingest reads the .txt).

Structure (from the text-view): a dotted Table of Contents, then the body:
    Title <roman>          (heading on the next line)     → kind='part'
    Chapter <roman> / Sole Chapter  (heading on next line) → kind='chapter' (parent = the Title)
    Art. N.  <body...>     (RAIL, operative content)        → kind='article'
Articles run 1..238, contiguous, no bis/letter suffixes. Article bodies wrap across lines until
the next "Art. N." or the next structural header. Citations: "LFDA (Mexico) Art. N".

Run:
    python src/store/ingest_mx.py --db db/corpus.db --allow-corpus \
        --html spike/artifacts/mx_lfda.txt \
        --source-url https://www.wipo.int/wipolex/en/text/476907
"""
from __future__ import annotations

import argparse
import re

from _common import RecordSet, ordinal, run_ingest

INSTRUMENT = dict(jurisdiction="MX", type="statute",
                  official_citation="Ley Federal del Derecho de Autor",
                  ext_id_scheme="NATIONAL", ext_id="mx-lfda",
                  title="Federal Law on Copyright (Ley Federal del Derecho de Autor), Mexico")

# A body TITLE header is a WHOLE line "Title <roman>" (no TOC dotted leader / article range).
_TITLE = re.compile(r"^Title\s+([IVXLC]+)$")
# A body CHAPTER header is "Chapter <roman>" or the bare "Sole Chapter".
_CHAPTER = re.compile(r"^Chapter\s+([IVXLC]+)$|^Sole Chapter$")
# An article opens a line: "Art. 148. <text...>" — the number then a period.
_ARTICLE = re.compile(r"^Art\.\s*(\d+)\.\s*(.*)$")
# The closing "Transitional Provisions" block header (after Art. 238). Its clauses carry the
# repeal of the prior 1956/1963 law, so they are ingested as their own provisions (not dropped).
_TRANSITIONAL = re.compile(r"^Transitional Provisions$")
# Each transitory clause opens with an ORDINAL WORD then a period: "First. ...", "Second. ...".
# The source has no Arabic numbers here — the ordinal word IS the label (grounded verbatim).
_TRANSITORY_WORDS = ["First", "Second", "Third", "Fourth", "Fifth", "Sixth", "Seventh",
                     "Eighth", "Ninth", "Tenth", "Eleventh", "Twelfth"]
_TRANSITORY = re.compile(r"^(" + "|".join(_TRANSITORY_WORDS) + r")\.\s*(.*)$")


def _lines(path: str) -> list[str]:
    text = open(path, encoding="utf-8", errors="replace").read()
    return [ln.rstrip() for ln in text.split("\n")]


def _body_start(lines: list[str]) -> int:
    """Skip the dotted Table of Contents; the body begins at its whole-line "Title I" header
    (the TOC form is "Title I: General provisions ... 1—10", which _TITLE does not match), so
    the first Title/Chapter containers are captured. Fall back to the first "Art. 1." line."""
    for i, ln in enumerate(lines):
        if _TITLE.match(ln.strip()):
            return i
    for i, ln in enumerate(lines):
        if re.match(r"^Art\.\s*1\.", ln.strip()):
            return i
    return 0


def _parse_transitory(rs: RecordSet, body: list[str], start: int, n: int) -> None:
    """Ingest the closing "Transitional Provisions" clauses (First..Ninth) after Art. 238 as
    their own provisions. One clause opens with an ordinal word + period and runs (including any
    unlabelled continuation paragraph) until the next ordinal word. Grounded verbatim — the
    Second clause carries the repeal of the 1956/1963 Federal Law on Copyright."""
    container = rs.add(parent_local=None, kind="part", label="Transitional Provisions",
                       heading="Transitional Provisions",
                       sort_int=10_000, sort_suffix="", role="enacting",
                       citation="LFDA (Mexico) Transitional Provisions")
    seq = 0
    j = start
    while j < n:
        s = body[j].strip()
        m = _TRANSITORY.match(s)
        if not m:
            j += 1
            continue
        word, first = m.group(1), m.group(2).strip()
        seq += 1
        clause_lines: list[str] = [first] if first else []
        k = j + 1
        while k < n and not _TRANSITORY.match(body[k].strip()):
            clause_lines.append(body[k])
            k += 1
        content = "\n".join(clause_lines).strip() or None
        rs.add(parent_local=container, kind="article", label=f"Transitional Article {word}",
               heading=None, sort_int=seq, sort_suffix="", role="enacting",
               citation=f"LFDA (Mexico) Transitional Article {word}", content=content)
        j = k


def parse(path: str) -> RecordSet:
    lines = _lines(path)
    body = lines[_body_start(lines):]
    rs = RecordSet()
    part_local: int | None = None
    chapter_local: int | None = None
    doc_i = 0
    i, n = 0, len(body)

    def _heading_after(idx: int) -> str | None:
        """The container's heading is the next non-empty line, unless it's itself a header/article."""
        j = idx + 1
        while j < n and not body[j].strip():
            j += 1
        if j < n:
            cand = body[j].strip()
            if cand and not _TITLE.match(cand) and not _CHAPTER.match(cand) \
                    and not _ARTICLE.match(cand) and not _TRANSITIONAL.match(cand):
                return cand
        return None

    while i < n:
        line = body[i].strip()

        if _TRANSITIONAL.match(line):     # closing transitional block → ingest its clauses as provisions
            _parse_transitory(rs, body, i + 1, n)
            break

        tm = _TITLE.match(line)
        if tm:
            roman = tm.group(1)
            doc_i += 1
            si, su = ordinal(roman, doc_i)          # roman → falls back to doc order (authoritative)
            part_local = rs.add(parent_local=None, kind="part", label=f"Title {roman}",
                                heading=_heading_after(i), sort_int=si, sort_suffix=su,
                                citation=f"LFDA (Mexico) Title {roman}")
            chapter_local = None
            i += 1
            continue

        cm = _CHAPTER.match(line)
        if cm:
            roman = cm.group(1)                     # None for the bare "Sole Chapter"
            doc_i += 1
            si, su = ordinal(roman or "", doc_i)
            label = f"Chapter {roman}" if roman else "Sole Chapter"
            # citation must be unique across repeated "Sole Chapter"s / chapter numerals per-Title
            # → qualify by parent Title (RecordSet also de-dupes deterministically as a backstop).
            title_no = None
            for r in reversed(rs.records):
                if r["local_id"] == part_local:
                    title_no = r["label"].replace("Title ", "")
                    break
            cite = f"LFDA (Mexico) Title {title_no} {label}" if title_no else f"LFDA (Mexico) {label}"
            chapter_local = rs.add(parent_local=part_local, kind="chapter", label=label,
                                   heading=_heading_after(i), sort_int=si, sort_suffix=su,
                                   citation=cite)
            i += 1
            continue

        am = _ARTICLE.match(line)
        if am:
            num, first = am.group(1), am.group(2).strip()
            body_lines: list[str] = [first] if first else []
            j = i + 1
            while j < n:
                nxt = body[j].strip()
                if _ARTICLE.match(nxt) or _TITLE.match(nxt) or _CHAPTER.match(nxt) \
                        or _TRANSITIONAL.match(nxt):
                    break
                body_lines.append(body[j])          # preserve blank lines (subparagraph spacing)
                j += 1
            content = "\n".join(body_lines).strip() or None
            doc_i += 1
            si, su = ordinal(num, doc_i)
            rs.add(parent_local=chapter_local or part_local, kind="article",
                   label=f"Article {num}", heading=None, sort_int=si, sort_suffix=su,
                   citation=f"LFDA (Mexico) Art. {num}", content=content)
            i = j
            continue

        i += 1
    return rs


def main() -> None:
    ap = argparse.ArgumentParser(description="Ingest Mexico LFDA (WIPO Lex EN translation).")
    ap.add_argument("--db", required=True)
    ap.add_argument("--html", required=True, help="path to mx_lfda.txt (extracted WIPO text-view)")
    ap.add_argument("--source-url", required=True)
    ap.add_argument("--point-in-time", default=None)
    ap.add_argument("--allow-corpus", action="store_true")
    a = ap.parse_args()
    s = run_ingest(a.db, INSTRUMENT, parse(a.html), a.source_url, point_in_time=a.point_in_time,
                   allow_corpus=a.allow_corpus, is_official_language=0,   # English translation
                   version_label="WIPO Lex (EN translation, International Bureau of WIPO)",
                   fts_title="LFDA (Mexico)")
    print(f"instrument #{s['instrument_id']}  Mexico LFDA — {s['provisions']} provisions "
          f"({s['by_kind'].get('article', 0)} articles); versions new {s['versions_new']}, "
          f"unchanged {s['versions_unchanged']} (is_official_language=0)")


if __name__ == "__main__":
    main()
