"""Tier-2 ingest — Germany, Act on Copyright and Related Rights (UrhG).

REFERENCE TEMPLATE for the Tier-2 fan-out: a per-country ingest is just an INSTRUMENT dict +
a `parse()` that returns a `_common.RecordSet` + a thin `main()`. All DB/versioning/idempotency
lives in `_common`.

Source: the OFFICIAL English translation from the German Federal Ministry of Justice
(gesetze-im-internet.de) — cleaner than WIPO Lex (PDF-only here). It is a TRANSLATION, so
`run_ingest(..., is_official_language=0)` (authentic language = German; flagged in the UI).
Structure: Part/Division/Subdivision containers + `Section N<br/>title` + body <p>; letter-
suffixed sections (20a, 60a…) fit the ordinal. NO fake law: text is from the fetched page.

Run:
    python src/store/ingest_de_urhg.py --db db/corpus.db --allow-corpus \
        --html spike/artifacts/de_urhg.html \
        --source-url https://www.gesetze-im-internet.de/englisch_urhg/englisch_urhg.html
"""
from __future__ import annotations

import argparse
import html as htmlmod
import re

from _common import RecordSet, ordinal, run_ingest

INSTRUMENT = dict(jurisdiction="DE", type="statute", official_citation="UrhG",
                  ext_id_scheme="NATIONAL", ext_id="de-urhg",
                  title="Act on Copyright and Related Rights (Urheberrechtsgesetz, UrhG)")

KIND = {"Part": "part", "Division": "chapter", "Subdivision": "subchapter", "Section": "section"}
HEAD = re.compile(
    r'<a name="p\d+">(?:<!---->)?</a>\s*(Part|Division|Subdivision|Section)\s+(\d+[a-z]*)\b'
    r'\s*(?:<br\s*/?>\s*(.*?))?</p>', re.S)

# Operative Annex to section 61a ("Sources for diligent search"): § 61a(1) requires that "at
# the very least the sources set out in the Annex must be consulted", so it is enacting text, not
# back-matter — captured as a schedule container + its enumerated categories (TRIPS-annex
# precedent, see ingest_treaty). The heading <p> ends the file's numbered sections (§ 143 is last),
# so it also serves as the cut that keeps § 143 from swallowing the Annex + page footer.
ANNEX_HEAD = re.compile(
    r'<p[^>]*>\s*<a name="p\d+">(?:<!---->)?</a>\s*'
    r'Annex\s*\(to section 61a\)\s*(?:<br\s*/?>\s*(.*?))?</p>', re.S)
# Each top-level category is a `Liste1` paragraph ("1. …:"); its lettered sub-items are the
# following `Liste2` paragraphs. The list ends at the page footer <div id="fusszeile">.
ANNEX_CAT = re.compile(r'<p class="Liste1">.*?(?=<p class="Liste1">|<div id="fusszeile">|\Z)', re.S)
ANNEX_ITEM_NUM = re.compile(r'>\s*(\d+)\s*\.')
_ANNEX_SORT_BASE = 900000   # sort the schedule + its paras after all §§ 1–143


def _clean(frag: str) -> str:
    frag = re.sub(r'<a\b[^>]*>.*?</a>', ' ', frag or "", flags=re.S)   # drop anchors + TOC links
    frag = re.sub(r"<[^>]+>", " ", frag)
    frag = re.sub(r"\btable of contents\b", " ", frag, flags=re.I)
    return re.sub(r"\s+", " ", htmlmod.unescape(frag)).strip()


def parse(html_path: str) -> RecordSet:
    html = open(html_path, encoding="utf-8", errors="replace").read()
    heads = list(HEAD.finditer(html))
    rs = RecordSet()
    container = {"part": None, "chapter": None, "subchapter": None}   # local ids of open containers

    annex = ANNEX_HEAD.search(html)
    annex_start = annex.start() if annex else len(html)   # last section's body must stop here

    for i, m in enumerate(heads):
        unit, num, title = m.group(1), m.group(2), _clean(m.group(3)) or None
        kind = KIND[unit]
        si, su = ordinal(num, i)
        if kind == "section":
            # Last section body: cut at the Annex heading (not m.end()+4000) so § 143 does not
            # swallow the Annex + the page footer.
            end = heads[i + 1].start() if i + 1 < len(heads) else annex_start
            body = _clean(html[m.end(): end])
            parent = container["subchapter"] or container["chapter"] or container["part"]
            rs.add(parent_local=parent, kind="section", label=f"Section {num}", heading=title,
                   sort_int=si, sort_suffix=su, citation=f"UrhG § {num}", content=body or None)
        else:
            if kind == "part":
                container["chapter"] = container["subchapter"] = None
                parent = None
            elif kind == "chapter":
                container["subchapter"] = None
                parent = container["part"]
            else:
                parent = container["chapter"] or container["part"]
            container[kind] = rs.add(parent_local=parent, kind=kind, label=f"{unit} {num}",
                                     heading=title, sort_int=si, sort_suffix=su,
                                     citation=f"UrhG {unit} {num}")

    if annex:
        _add_annex(rs, html, annex)
    return rs


def _add_annex(rs: RecordSet, html: str, annex: "re.Match") -> None:
    """Capture the operative Annex to section 61a as a `schedule` container + one `schedule_para`
    per enumerated category (its lettered sub-items kept as the category's body). Body runs from
    the Annex heading to the page footer only — never into <div id="fusszeile">."""
    subtitle = _clean(annex.group(1)) or None   # "Sources for diligent search"
    footer = html.find('<div id="fusszeile">', annex.end())
    body_end = footer if footer != -1 else len(html)
    sched = rs.add(kind="schedule", label="Annex", heading=subtitle, role="schedule",
                   sort_int=_ANNEX_SORT_BASE, sort_suffix="",
                   citation="UrhG Annex (to § 61a)")
    for cat in ANNEX_CAT.finditer(html[annex.end():body_end]):
        text = _clean(cat.group(0))
        if not text:
            continue
        n = ANNEX_ITEM_NUM.search(cat.group(0))
        num = int(n.group(1)) if n else None
        cite = f"UrhG Annex (to § 61a) no. {num}" if num else "UrhG Annex (to § 61a)"
        rs.add(parent_local=sched, kind="schedule_para", label=f"{num}." if num else "—",
               role="schedule", sort_int=_ANNEX_SORT_BASE + (num or 0), sort_suffix="",
               citation=cite, content=text)


def main() -> None:
    ap = argparse.ArgumentParser(description="Ingest Germany UrhG (gesetze-im-internet.de EN).")
    ap.add_argument("--db", required=True)
    ap.add_argument("--html", required=True)
    ap.add_argument("--source-url", required=True)
    ap.add_argument("--point-in-time", default=None)
    ap.add_argument("--allow-corpus", action="store_true")
    a = ap.parse_args()
    s = run_ingest(a.db, INSTRUMENT, parse(a.html), a.source_url, point_in_time=a.point_in_time,
                   allow_corpus=a.allow_corpus, is_official_language=0,   # English translation
                   version_label="gesetze-im-internet.de (EN translation)", fts_title="UrhG")
    print(f"instrument #{s['instrument_id']}  Germany UrhG — {s['provisions']} provisions "
          f"({s['by_kind'].get('section', 0)} sections); versions new {s['versions_new']}, "
          f"unchanged {s['versions_unchanged']} (is_official_language=0)")


if __name__ == "__main__":
    main()
