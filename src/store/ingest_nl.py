"""Tier-2 ingest — Netherlands, Copyright Act 1912 (Auteurswet).

Part of the Tier-2 jurisdiction fan-out: an INSTRUMENT dict + a `parse()` returning a
`_common.RecordSet` + a thin `main()`. All DB/versioning/idempotency lives in `_common`.

Source: the UNOFFICIAL English translation by Mireille van Eechoud (Institute for
Information Law, IViR, University of Amsterdam), rendering the official Auteurswet into
English. Authentic language is Dutch → `run_ingest(..., is_official_language=0)` (flagged
in the UI). It is a consolidated, faithful text → is_consolidated=1, is_authentic=1.
NO fake law: every provision's text comes from the fetched IViR PDF (retained at
spike/artifacts/nl_auteurswet.pdf, extracted to nl_auteurswet.txt via pdftotext -layout).

Structure: Chapters (roman I–VIII, containers) hold Articles (Article 1, 12, 15a, 45a…);
Chapter I additionally groups Articles under thematic "Section N" sub-headers (skipped as
non-citable display groupings — Articles are the citable RAILs). Letter-suffixed articles
(15a, 16ga, 50a) fit `_common.ordinal`. Article headers stand ALONE on a line; wrapped
body lines that merely reference "Article Nx" mid-sentence are not headers.

Run:
    python src/store/ingest_nl.py --db db/corpus.db --allow-corpus \
        --html spike/artifacts/nl_auteurswet.txt \
        --source-url https://www.ivir.nl/syscontent/pdfs/119.pdf
"""
from __future__ import annotations

import argparse
import re

from _common import RecordSet, ordinal, run_ingest

INSTRUMENT = dict(jurisdiction="NL", type="statute",
                  official_citation="Auteurswet (Copyright Act)",
                  ext_id_scheme="NATIONAL", ext_id="nl-auteurswet",
                  title="Copyright Act 1912 (Auteurswet), Netherlands")

# A chapter header: "Chapter <roman>", title on the following non-blank line(s).
CHAPTER = re.compile(r"^Chapter ([IVX]+)\b\s*(.*)$")
# An article header stands ALONE on a line: "Article 1", "Article 15a", "Article 16ga".
# A trailing "to"/"," etc. means it is a wrapped body line referencing an article, not a header.
ARTICLE = re.compile(r"^Article (\d+[a-z]*)\s*$")
# Sub-grouping display headers within Chapter I (non-citable): "Section 1 The nature ...".
SECTION_GROUP = re.compile(r"^Section \d+\b")
# Page-break noise from pdftotext: a bare 3-digit page number, or the running header/footer.
PAGE_NUM = re.compile(r"^\s*\d{2,3}\s*$")
RUNNING = re.compile(r"^\s*(Copyright Act . Auteurswet|Mireille van Eechoud)\s*$")


def _is_noise(line: str) -> bool:
    return bool(PAGE_NUM.match(line) or RUNNING.match(line))


def _clean(lines: list[str]) -> str:
    """Join an article's body lines, dropping page-break noise, into operative text."""
    kept = [ln.rstrip() for ln in lines if not _is_noise(ln)]
    return re.sub(r"\s+", " ", " ".join(kept)).strip()


def parse(path: str) -> RecordSet:
    raw = open(path, encoding="utf-8", errors="replace").read().splitlines()
    rs = RecordSet()
    chapter_local: int | None = None
    ch_idx = 0

    # Locate every header line first (chapters + article headers), in document order.
    headers: list[tuple[int, str, str]] = []   # (line_no, kind, token)
    for i, line in enumerate(raw):
        cm = CHAPTER.match(line)
        if cm:
            headers.append((i, "chapter", cm.group(1)))
            continue
        if ARTICLE.match(line):
            headers.append((i, "article", ARTICLE.match(line).group(1)))

    for h, (line_no, kind, token) in enumerate(headers):
        # Body of this header runs to the next header line.
        next_line = headers[h + 1][0] if h + 1 < len(headers) else len(raw)
        if kind == "chapter":
            # Chapter title: text on the header line, plus following non-blank, non-Section,
            # non-noise lines until the first Article/blank block.
            title_bits: list[str] = []
            first = CHAPTER.match(raw[line_no]).group(2).strip()
            if first:
                title_bits.append(first)
            for ln in raw[line_no + 1:next_line]:
                if not ln.strip() or SECTION_GROUP.match(ln) or _is_noise(ln):
                    break
                title_bits.append(ln.strip())
            ch_idx += 1
            si, su = ordinal(str(ch_idx), ch_idx)
            heading = _clean_title(" ".join(title_bits)) or None
            chapter_local = rs.add(kind="chapter", label=f"Chapter {token}", heading=heading,
                                   sort_int=si, sort_suffix=su,
                                   citation=f"Auteurswet Ch. {token}")
        else:  # article
            body = _clean(raw[line_no + 1:next_line])
            si, su = ordinal(token, line_no)
            rs.add(parent_local=chapter_local, kind="article", label=f"Article {token}",
                   heading=None, sort_int=si, sort_suffix=su,
                   citation=f"Auteurswet Art. {token}", content=body or None)
    return rs


def _clean_title(t: str) -> str:
    return re.sub(r"\s+", " ", t).strip()


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Ingest Netherlands Auteurswet (IViR unofficial EN translation).")
    ap.add_argument("--db", required=True)
    ap.add_argument("--html", required=True, help="extracted text (pdftotext -layout) of the IViR PDF")
    ap.add_argument("--source-url", required=True)
    ap.add_argument("--point-in-time", default=None)
    ap.add_argument("--allow-corpus", action="store_true")
    a = ap.parse_args()
    s = run_ingest(a.db, INSTRUMENT, parse(a.html), a.source_url, point_in_time=a.point_in_time,
                   allow_corpus=a.allow_corpus, is_official_language=0,   # EN translation; Dutch is authentic
                   is_consolidated=1, is_authentic=1,
                   version_label="IViR (van Eechoud) unofficial EN translation", fts_title="Auteurswet")
    print(f"instrument #{s['instrument_id']}  Netherlands Auteurswet — {s['provisions']} provisions "
          f"({s['by_kind'].get('article', 0)} articles, {s['by_kind'].get('chapter', 0)} chapters); "
          f"versions new {s['versions_new']}, unchanged {s['versions_unchanged']} (is_official_language=0)")


if __name__ == "__main__":
    main()
