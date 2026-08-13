"""Tier-2 ingest — Singapore, Copyright Act 2021.

Part of the Tier-2 jurisdiction fan-out (see PROJECT_STATE.md). Like every ingest it is
just an INSTRUMENT dict + a `parse()` returning a `_common.RecordSet` + a thin `main()`;
all DB/versioning/idempotency lives in `_common`. NEVER originates text.

Source: Singapore Statutes Online (sso.agc.gov.sg), the OFFICIAL government legislation
portal, Copyright Act 2021 (current in-force version). The Act is in ENGLISH, which is the
authentic legislative language of Singapore — so this is NOT a translation:
`is_official_language=1, is_authentic=1, is_consolidated=1`.

Structure (from the SSO markup):
  * Parts    — `<div class="sgHead partHdr"><b>Part N TITLE</b></div>`      -> kind='part'
  * Divisions— `<div class="sgHead divHdr"><b>Division N — title</b></div>` -> kind='chapter'
  * Subdivs  — `<div class="sgHead subHdr"><b>Subdivision N title</b></div>` -> kind='subchapter'
  * Sections — `<div class="prov1">` with `<td class="prov1Hdr" id="prN-">heading</td>`
               and body in `<td class="prov1Txt"><strong>N.</strong> ...>`  -> kind='section'
Sections are the citable/versioned RAIL unit (~541 of them, e.g. fair use = s. 190).
Letter-suffixed sections (e.g. 168A) fit the `_common.ordinal` (int, SUFFIX) model.

The retained artifact `spike/artifacts/sg_copyright.html` was assembled from SSO's
`?ProvIds=` provision-fetch endpoint (batched) because the default page materializes only
the first Part; the assembler walked SSO's own whole-document TOC for the Part/Division/
Subdivision spine and filled each section body from the fetched provisions. NO fake law —
every heading and body byte is from the fetched SSO responses.

Run:
    python src/store/ingest_sg.py --db db/corpus.db --allow-corpus \
        --html spike/artifacts/sg_copyright.html \
        --source-url https://sso.agc.gov.sg/Act/CA2021
"""
from __future__ import annotations

import argparse
import html as htmlmod
import re

from _common import RecordSet, ordinal, run_ingest

INSTRUMENT = dict(jurisdiction="SG", type="statute", official_citation="Copyright Act 2021",
                  ext_id_scheme="NATIONAL", ext_id="sg-copyright-2021",
                  title="Copyright Act 2021 (Singapore)")

CITE = "Copyright Act 2021 (Singapore)"

# Container headings (Part / Division / Subdivision) and section blocks, in document order.
_HEAD = re.compile(
    r'<div class="sgHead (?P<cls>partHdr|divHdr|subHdr)">\s*<b>\s*'
    r'(?:Part|Division|Subdivision)\s+(?P<num>\d+[A-Za-z]?)\s*(?:&#151;|—|—)?\s*'
    r'(?P<title>.*?)</b>', re.S)
_SEC = re.compile(
    r'<td class="prov1Hdr" id="pr(?P<num>\d+[A-Za-z]*)-">.*?'
    r'<span class="">(?P<heading>.*?)</span>\s*</td>.*?'
    r'<td class="prov1Txt">(?P<body>.*?)</td></tr></table></div>', re.S)

_KIND = {"partHdr": "part", "divHdr": "chapter", "subHdr": "subchapter"}


def _clean(frag: str) -> str:
    frag = re.sub(r'<a\b[^>]*>.*?</a>', ' ', frag or "", flags=re.S)   # drop anchors
    frag = re.sub(r"<[^>]+>", " ", frag)
    frag = frag.replace("\xa0", " ").replace("‑", "-")            # nbsp, non-breaking hyphen
    return re.sub(r"\s+", " ", htmlmod.unescape(frag)).strip()


def parse(html_path: str) -> RecordSet:
    html = open(html_path, encoding="utf-8", errors="replace").read()
    # One ordered stream of headings + sections; a section's parent is the last opened container.
    events = []
    for m in _HEAD.finditer(html):
        events.append((m.start(), "head", m))
    for m in _SEC.finditer(html):
        events.append((m.start(), "sec", m))
    events.sort(key=lambda e: e[0])

    rs = RecordSet()
    container = {"part": None, "chapter": None, "subchapter": None}
    for i, (_pos, typ, m) in enumerate(events):
        if typ == "head":
            cls, num, title = m.group("cls"), m.group("num"), _clean(m.group("title")) or None
            kind = _KIND[cls]
            si, su = ordinal(num, i)
            if kind == "part":
                container["chapter"] = container["subchapter"] = None
                parent = None
                label = f"Part {num}"
            elif kind == "chapter":                                   # Division
                container["subchapter"] = None
                parent = container["part"]
                label = f"Division {num}"
            else:                                                     # Subdivision
                parent = container["chapter"] or container["part"]
                label = f"Subdivision {num}"
            container[kind] = rs.add(parent_local=parent, kind=kind, label=label, heading=title,
                                     sort_int=si, sort_suffix=su,
                                     citation=f"{CITE} {label}")
        else:
            num = m.group("num")
            heading = _clean(m.group("heading")) or None
            body = _clean(m.group("body")) or None
            si, su = ordinal(num, i)
            parent = container["subchapter"] or container["chapter"] or container["part"]
            rs.add(parent_local=parent, kind="section", label=f"s. {num}", heading=heading,
                   sort_int=si, sort_suffix=su, citation=f"{CITE} s. {num}", content=body)
    return rs


def main() -> None:
    ap = argparse.ArgumentParser(description="Ingest Singapore Copyright Act 2021 (SSO HTML).")
    ap.add_argument("--db", required=True)
    ap.add_argument("--html", required=True)
    ap.add_argument("--source-url", required=True)
    ap.add_argument("--point-in-time", default=None)
    ap.add_argument("--allow-corpus", action="store_true")
    a = ap.parse_args()
    s = run_ingest(a.db, INSTRUMENT, parse(a.html), a.source_url, point_in_time=a.point_in_time,
                   allow_corpus=a.allow_corpus,
                   is_official_language=1, is_authentic=1, is_consolidated=1,  # English = authentic
                   version_label="Singapore Statutes Online (current in force)",
                   fts_title="Copyright Act 2021 (Singapore)")
    print(f"instrument #{s['instrument_id']}  Singapore Copyright Act 2021 — {s['provisions']} "
          f"provisions ({s['by_kind'].get('section', 0)} sections, "
          f"{s['by_kind'].get('part', 0)} parts, {s['by_kind'].get('chapter', 0)} divisions, "
          f"{s['by_kind'].get('subchapter', 0)} subdivisions); versions new {s['versions_new']}, "
          f"unchanged {s['versions_unchanged']} (is_official_language=1, is_authentic=1)")


if __name__ == "__main__":
    main()
