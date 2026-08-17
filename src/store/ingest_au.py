"""Tier-2 ingest — Australia, Copyright Act 1968 (Cth).

Follows the Tier-2 template (ingest_de_urhg.py): an INSTRUMENT dict + a `parse()`
that returns a `_common.RecordSet` + a thin `main()`. All DB/versioning/idempotency
lives in `_common`.

Source: the OFFICIAL, consolidated English text from the Federal Register of
Legislation (legislation.gov.au) — the current compilation, published by the Office
of Parliamentary Counsel. This is Australia's authentic language (English), so
`run_ingest(..., is_official_language=1)`, and the register compilation is authentic
and consolidated (`is_authentic=1, is_consolidated=1`).

The fetched artifact is the EPUB-frame body document of the compilation
(`.../text/original/epub/OEBPS/document_1/document_1.html`), which carries the full
operative text (the `/latest/text` page is only the table of contents). Retained at
spike/artifacts/au_copyright.html. NO fake law: every `content` is from the fetched page.

Structure (source-derived from the OPC EPUB HTML classes):
  ActHead2 (CharPartNo/CharPartText) → Part            → kind='part'
  ActHead3 (CharDivNo/CharDivText)   → Division         → kind='chapter'
  ActHead4 (CharSubdNo/CharSubdText) → Subdivision      → kind='subchapter'
  ActHead5 (CharSectno)              → Section (citable) → kind='section'  (RAILs)
Sections carry letter runs (10AA, 195AB, 248SA) → _common.ordinal handles the suffix.
Parts are roman-numeralled with letter suffixes (I, IVA, VAA) → ordinal falls back to
document order for non-numeric tokens, which keeps them in source order.

Run:
    python src/store/ingest_au.py --db db/corpus.db --allow-corpus \
        --html spike/artifacts/au_copyright.html \
        --source-url https://www.legislation.gov.au/C1968A00063/latest/text
"""
from __future__ import annotations

import argparse
import html as htmlmod
import re

from _common import RecordSet, ordinal, run_ingest

INSTRUMENT = dict(jurisdiction="AU", type="statute",
                  official_citation="Copyright Act 1968",
                  ext_id_scheme="NATIONAL", ext_id="au-copyright-1968",
                  title="Copyright Act 1968 (Cth)")

# ActHead level → (structural kind, the Char*No span class that holds the ordinal token,
#                  the Char*Text span class that holds the container heading)
LEVEL = {
    "ActHead2": ("part",       "CharPartNo", "CharPartText"),
    "ActHead3": ("chapter",    "CharDivNo",  "CharDivText"),
    "ActHead4": ("subchapter", "CharSubdNo", "CharSubdText"),
    "ActHead5": ("section",    "CharSectno", None),
}

HEAD = re.compile(r'<p\b[^>]*class="(ActHead[2-5])"[^>]*>(.*?)</p>', re.S)

# The Schedule (Oath and Affirmation, s. 144) is the Act's only Schedule — an OPERATIVE
# ActHead1 block near anchor _Toc226988647. It is NOT an ActHead2-5, so the HEAD loop never
# touches it; we capture it separately AND bound it hard so it stops before the compilation
# Endnotes (editorial apparatus that must stay excluded — see CLAUDE ingest rule 3).
SCHED_START = re.compile(
    r'<p\b[^>]*class="ActHead1"[^>]*>.*?<span class="CharChapNo">\s*The Schedule\s*</span>', re.S)
# End of the Schedule = the Endnotes block. In the artifact this is the <p class="ENotesHeading1">
# ("Endnotes") that immediately precedes "Endnote 1—About the endnotes". Bound on either.
SCHED_END = re.compile(r'<p\b[^>]*class="ENotesHeading1"|Endnote\s*1\s*[—-]\s*About the endnotes', re.S)


def _text(frag: str) -> str:
    """Strip tags/entities and collapse whitespace (also the U+2011 non-breaking hyphen)."""
    frag = re.sub(r"<[^>]+>", " ", frag or "")
    frag = htmlmod.unescape(frag).replace("‑", "-").replace("\xa0", " ")
    return re.sub(r"\s+", " ", frag).strip()


def _spans(frag: str, cls: str) -> str:
    """Concatenated text of all <span class="cls"> in frag (tags/entities stripped)."""
    return _text(" ".join(re.findall(r'<span class="' + cls + r'">(.*?)</span>', frag, re.S)))


def _part_token(no_text: str) -> str:
    """'Part I' / 'Part IVA' → 'I' / 'IVA' (drop the leading 'Part'/'Division' word)."""
    t = re.sub(r"^(Part|Division|Subdivision)\b", "", no_text).strip()
    return t or no_text


def _add_schedule(html: str, rs: RecordSet, sort_base: int) -> None:
    """Capture 'The Schedule' — Oath and Affirmation (Section 144), OPERATIVE (s. 144 requires the
    oath be 'in accordance with the form ... in the Schedule to this Act'). Bounded from the
    ActHead1 'The Schedule' heading up to the Endnotes block so the editorial endnotes NEVER bleed
    in. Modelled as a kind='schedule' container (role='schedule', TRIPS-annex precedent) with two
    kind='schedule_para' children — the Oath and the Affirmation forms — carrying verbatim text."""
    sm = SCHED_START.search(html)
    if not sm:
        return
    em = SCHED_END.search(html, sm.end())
    block = html[sm.start(): em.start() if em else len(html)]
    body = _text(block)
    if not body:
        return
    sched = rs.add(kind="schedule", label="The Schedule",
                   heading="The Schedule — Oath and Affirmation (Section 144)",
                   sort_int=sort_base, sort_suffix="", role="schedule",
                   citation="Copyright Act 1968 (Australia) The Schedule", content=body)
    # Decompose into the OATH and AFFIRMATION forms (the two headed sub-parts of the Schedule).
    # Both markers are present verbatim in the block; if either is missing we keep only the
    # container (never invent structure).
    om = re.search(r"<p[^>]*><span>\s*OATH\s*</span></p>", block)
    am = re.search(r"<p[^>]*><span>\s*AFFIRMATION\s*</span></p>", block)
    if om and am and om.start() < am.start():
        oath = _text(block[om.start():am.start()])
        affirm = _text(block[am.start():])
        if oath:
            rs.add(parent_local=sched, kind="schedule_para", label="Oath",
                   heading="Oath", sort_int=sort_base + 1, sort_suffix="", role="schedule",
                   citation="Copyright Act 1968 (Australia) The Schedule — Oath", content=oath)
        if affirm:
            rs.add(parent_local=sched, kind="schedule_para", label="Affirmation",
                   heading="Affirmation", sort_int=sort_base + 2, sort_suffix="", role="schedule",
                   citation="Copyright Act 1968 (Australia) The Schedule — Affirmation",
                   content=affirm)


def parse(html_path: str) -> RecordSet:
    html = open(html_path, encoding="utf-8", errors="replace").read()
    heads = list(HEAD.finditer(html))
    rs = RecordSet()
    # local ids of the currently-open containers
    container = {"part": None, "chapter": None, "subchapter": None}

    for i, m in enumerate(heads):
        cls, frag = m.group(1), m.group(2)
        kind, no_cls, text_cls = LEVEL[cls]
        no_text = _spans(frag, no_cls)

        if kind == "section":
            # CharSectno holds the bare number; the heading is the text after that span.
            secno = no_text
            after = frag.split("</span>", 1)[1] if "</span>" in frag else ""
            heading = _text(after) or None
            si, su = ordinal(secno, i)
            body_html = html[m.end(): heads[i + 1].start() if i + 1 < len(heads) else len(html)]
            if i + 1 >= len(heads):     # LAST section: don't swallow The Schedule + the Endnotes
                endm = re.search(r'<p\b[^>]*class="ActHead1"|>Endnotes?<', body_html)
                if endm:
                    body_html = body_html[:endm.start()]
            body = _text(body_html)
            parent = container["subchapter"] or container["chapter"] or container["part"]
            rs.add(parent_local=parent, kind="section", label=f"s. {secno}", heading=heading,
                   sort_int=si, sort_suffix=su,
                   citation=f"Copyright Act 1968 (Australia) s. {secno}",
                   content=body or None)
            continue

        # container node (Part / Division / Subdivision)
        token = _part_token(no_text)
        heading = _spans(frag, text_cls) or None
        si, su = ordinal(token, i)
        # Container citations key on document position (@i) so re-numbered / duplicated
        # container labels across Parts (e.g. every Part has a "Division 1") never collide.
        if kind == "part":
            container["chapter"] = container["subchapter"] = None
            parent = None
            label, cite = f"Part {token}", f"Copyright Act 1968 (Australia) Part {token}"
        elif kind == "chapter":
            container["subchapter"] = None
            parent = container["part"]
            label, cite = f"Division {token}", f"Copyright Act 1968 (Australia) Div {token} @{i}"
        else:  # subchapter
            parent = container["chapter"] or container["part"]
            label, cite = f"Subdivision {token}", f"Copyright Act 1968 (Australia) Subdiv {token} @{i}"
        container[kind] = rs.add(parent_local=parent, kind=kind, label=label, heading=heading,
                                 sort_int=si, sort_suffix=su, citation=cite)
    # The Schedule is a top-level ActHead1 (not in the HEAD loop). Sort it AFTER every section
    # (numeric sort_ints top out at s. 249) with a base beyond any real section number.
    _add_schedule(html, rs, sort_base=100000)
    return rs


def main() -> None:
    ap = argparse.ArgumentParser(description="Ingest Australia Copyright Act 1968 (legislation.gov.au).")
    ap.add_argument("--db", required=True)
    ap.add_argument("--html", required=True)
    ap.add_argument("--source-url", required=True)
    ap.add_argument("--point-in-time", default=None)
    ap.add_argument("--allow-corpus", action="store_true")
    a = ap.parse_args()
    s = run_ingest(a.db, INSTRUMENT, parse(a.html), a.source_url, point_in_time=a.point_in_time,
                   allow_corpus=a.allow_corpus,
                   is_official_language=1, is_authentic=1, is_consolidated=1,  # official English, register compilation
                   version_label="legislation.gov.au (current compilation)",
                   fts_title="Copyright Act 1968 (Cth)")
    print(f"instrument #{s['instrument_id']}  Australia Copyright Act 1968 — {s['provisions']} provisions "
          f"({s['by_kind'].get('section', 0)} sections, {s['by_kind'].get('part', 0)} parts, "
          f"{s['by_kind'].get('chapter', 0)} divisions, {s['by_kind'].get('subchapter', 0)} subdivisions); "
          f"versions new {s['versions_new']}, unchanged {s['versions_unchanged']} (is_official_language=1)")


if __name__ == "__main__":
    main()
