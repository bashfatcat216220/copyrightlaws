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

    for i, m in enumerate(heads):
        unit, num, title = m.group(1), m.group(2), _clean(m.group(3)) or None
        kind = KIND[unit]
        si, su = ordinal(num, i)
        if kind == "section":
            body = _clean(html[m.end(): heads[i + 1].start() if i + 1 < len(heads) else m.end() + 4000])
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
    return rs


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
