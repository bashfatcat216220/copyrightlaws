"""Tier-2 ingest — India, The Copyright Act, 1957 (Act No. 14 of 1957).

A per-country ingest is an INSTRUMENT dict + a `parse()` returning a `_common.RecordSet`
+ a thin `main()`. All DB/versioning/idempotency lives in `_common`. NEVER originates text.

Source: the OFFICIAL consolidated English text from India Code (indiacode.nic.in), the
Government of India's authoritative repository — the full Act PDF "As on the 15th June, 2026",
converted with pdftotext -layout. English is an OFFICIAL, AUTHENTIC language of Indian
central legislation (Constitution Art. 348) → is_official_language=1, is_authentic=1,
is_consolidated=1.

Structure: Chapters (roman-numbered, e.g. CHAPTER I PRELIMINARY) contain Sections numbered
1..79 with letter-suffixed insertions (19A, 31D, 33A, 52A…). Each Section is the top-level
citable unit (kind='section'); Chapters are kind='chapter' containers. Sections carry their
operative body text (footnote apparatus and page furniture stripped). The trailing
"STATEMENT OF OBJECTS AND REASONS" (legislative history, not enacting law) is excluded.

Run:
    python src/store/ingest_in.py --db db/corpus.db --allow-corpus \
        --html spike/artifacts/in_copyright.txt \
        --source-url https://www.indiacode.nic.in/handle/123456789/1367
"""
from __future__ import annotations

import argparse
import re

from _common import RecordSet, ordinal, run_ingest

INSTRUMENT = dict(jurisdiction="IN", type="statute",
                  official_citation="Copyright Act, 1957",
                  ext_id_scheme="NATIONAL", ext_id="in-copyright-1957",
                  title="The Copyright Act, 1957")

# Chapter heading: centred "CHAPTER <roman>", optionally opened by an amendment "[".
CH = re.compile(r'^\s*\[?CHAPTER\s+([IVXL]+)\s*$')
# Section candidate: 1-8 leading spaces, optional footnote-superscript digit, optional "[",
# then N[A-Z]. and the heading/body. The sequence guard in parse() rejects false hits.
SEC = re.compile(r'^\s{1,8}(?:\d+\s+)?\[?\s*(\d+)([A-Z]*)\.\s+(\S.*)$')
# Footnote apparatus (page-bottom notes) — these start like a section but are amendment notes.
FOOT = re.compile(r'(Ins\.|Subs\.|omitted by|w\.e\.f|,\s*ibid|Cl\.,\s*cls|The word|The words|'
                  r'The Explanation|for\s+"|vide|notifin)', re.I)
# Page-furniture lines to drop from section bodies: a bare page number, or a lone footnote.
PAGENUM = re.compile(r'^\s*\d+\s*$')
FOOTLINE = re.compile(r'^\s{0,3}\d+\.\s+.*(Ins\.|Subs\.|omitted|w\.e\.f|ibid|vide|notifin|'
                      r'for\s+"|Rep\.|Earlier)', re.I)
# Footnote continuation lines that wrapped away from their "N. Subs. by…" head and stand alone:
# a bare "(w.e.f. <date>)." effective-date tail, or a lone amendment-apparatus fragment.
FOOTCONT = re.compile(r'^\s*\(?w\.e\.f\.[^)]*\)?\.?\s*$', re.I)


def _clean(text: str) -> str:
    """Collapse whitespace and strip Indian amendment apparatus. Indian statutes print amended
    text as 'N[current text]' (N = amending-act footnote) and omissions as 'N***'. Keep the
    operative text inside the brackets; drop the footnote number, the brackets, and the omission
    stars — e.g. '2[Appellate Board]' → 'Appellate Board', '5*** 6[Designs Act]' → 'Designs Act'."""
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\d+\s*\*+', '', text)     # 'N***' omitted-words marker → drop
    text = re.sub(r'\d*\[|\]', '', text)      # 'N[' / '[' / ']' amendment brackets → drop, keep inside
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def _chapter_title(body: list[str], idx: int) -> str | None:
    """The chapter title is the next non-blank, non-page-number line after 'CHAPTER <roman>'."""
    j = idx + 1
    while j < len(body) and (not body[j].strip() or PAGENUM.match(body[j])):
        j += 1
    if j < len(body):
        return _clean(body[j]) or None
    return None


def _section_body(body: list[str], seg: list[str], first_line_rest: str) -> str:
    """Assemble a section's operative text: its heading/first line plus following lines up to
    the next section/chapter, dropping page numbers, footnote lines, and chapter-title lines."""
    parts = [first_line_rest]
    for l in seg:
        s = l.strip()
        if not s:
            continue
        if PAGENUM.match(l):                      # page number furniture
            continue
        if FOOTLINE.match(l):                     # page-bottom amendment footnote
            continue
        if FOOTCONT.match(l):                     # wrapped footnote tail, e.g. "(w.e.f. 8-10-1984)."
            continue
        if CH.match(l):                           # a chapter header caught in the window
            continue
        # a chapter TITLE line (all-caps, short, no lowercase) that trails a chapter header
        if s.isupper() and len(s) < 60 and not any(c.isdigit() for c in s):
            continue
        parts.append(s)
    return _clean(" ".join(parts))


def parse(path: str) -> RecordSet:
    lines = open(path, encoding="utf-8", errors="replace").read().splitlines()

    # Body window: from the enacting clause through (but excluding) the Statement of Objects.
    enact = next((i for i, l in enumerate(lines) if l.strip().startswith("BE it enacted")), None)
    stop = next((i for i, l in enumerate(lines) if "STATEMENT OF OBJECTS AND REASONS" in l),
                len(lines))
    if enact is None:
        raise SystemExit("could not locate the enacting clause — source layout changed")
    body = lines[enact:stop]

    rs = RecordSet()
    cur_chapter = None                # local id of the open chapter
    last_key = (0, "")                # last accepted section number, for the sequence guard
    ci = 0                            # chapter document index (ordinal fallback)

    # First pass: record indices of chapter headers and section starts in document order.
    events: list[tuple[int, str, tuple]] = []
    for i, l in enumerate(body):
        m = CH.match(l)
        if m:
            events.append((i, "chapter", (m.group(1),)))
            continue
        m = SEC.match(l)
        if not m:
            continue
        n, suf, rest = int(m.group(1)), m.group(2), m.group(3)
        key = (n, suf)
        if key <= last_key:                       # sections only advance
            continue
        if key[0] > last_key[0] + 1:              # never jump >1 whole number (letters = inserts)
            continue
        if FOOT.match(rest):                       # footnote content masquerading as a section
            continue
        last_key = key
        events.append((i, "section", (f"{n}{suf}", rest)))

    # Second pass: emit provisions, slicing section bodies to the next event.
    starts = [e[0] for e in events]
    for e_idx, (line_i, etype, payload) in enumerate(events):
        next_start = starts[e_idx + 1] if e_idx + 1 < len(events) else len(body)
        if etype == "chapter":
            roman = payload[0]
            title = _chapter_title(body, line_i)
            si, su = ordinal(str(_roman(roman)), ci)
            ci += 1
            cur_chapter = rs.add(parent_local=None, kind="chapter",
                                 label=f"Chapter {roman}", heading=title,
                                 sort_int=si, sort_suffix=su,
                                 citation=f"Copyright Act 1957 (India) Chapter {roman}")
        else:
            num, rest = payload
            seg = body[line_i + 1: next_start]
            content = _section_body(body, seg, rest)
            # heading = text up to the first em-dash / full stop; body is the whole section text.
            heading = _section_heading(content)
            si, su = ordinal(num, e_idx)
            rs.add(parent_local=cur_chapter, kind="section",
                   label=f"s. {num}", heading=heading,
                   sort_int=si, sort_suffix=su,
                   citation=f"Copyright Act 1957 (India) s. {num}",
                   content=content or None)
    return rs


def _section_heading(content: str) -> str | None:
    """The marginal note: text before the first em-dash (India uses '.—' after the heading);
    fall back to the first sentence, capped so it stays a note, not a paragraph."""
    if not content:
        return None
    m = re.match(r"(.+?)\.?\s*[—–]", content)
    head = (m.group(1) if m else content.split(".")[0]).strip(" .[]")
    return (head[:200] or None)


_ROMAN = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}


def _roman(s: str) -> int:
    total, prev = 0, 0
    for ch in reversed(s):
        v = _ROMAN.get(ch, 0)
        total += -v if v < prev else v
        prev = v
    return total


def main() -> None:
    ap = argparse.ArgumentParser(description="Ingest India Copyright Act 1957 (India Code EN).")
    ap.add_argument("--db", required=True)
    ap.add_argument("--html", required=True, help="path to the retained source text/HTML")
    ap.add_argument("--source-url", required=True)
    ap.add_argument("--point-in-time", default=None)
    ap.add_argument("--allow-corpus", action="store_true")
    a = ap.parse_args()
    s = run_ingest(a.db, INSTRUMENT, parse(a.html), a.source_url, point_in_time=a.point_in_time,
                   allow_corpus=a.allow_corpus, is_official_language=1,   # English is official & authentic
                   is_authentic=1, is_consolidated=1,
                   version_label="India Code (official consolidated EN)",
                   fts_title="Copyright Act, 1957 (India)")
    print(f"instrument #{s['instrument_id']}  India Copyright Act 1957 — {s['provisions']} provisions "
          f"({s['by_kind'].get('section', 0)} sections, {s['by_kind'].get('chapter', 0)} chapters); "
          f"versions new {s['versions_new']}, unchanged {s['versions_unchanged']} "
          f"(is_official_language=1)")


if __name__ == "__main__":
    main()
