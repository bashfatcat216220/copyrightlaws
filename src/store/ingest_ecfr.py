"""Tier-1 completion — US 37 C.F.R., U.S. Copyright Office regulations (eCFR).

Retrieval-first: a connector FETCHES the eCFR full-title XML; this store step SCOPES to
Title 37, Chapter II (the U.S. Copyright Office) and parses it into a provision tree —
Parts (containers) and Sections (the citable, versioned RAIL unit, e.g. § 201.1). It NEVER
originates text: every section body comes from the fetched eCFR content.

eCFR full-title XML nests: DIV1=title, DIV3=chapter (Chapter II N="II" = Copyright Office),
DIV5=part, DIV6=subpart, DIV7=subject-group (hash id, not citable — pass-through), DIV8=
section. Section HEADs read like "§ 201.1   Communication with the Copyright Office." and the
DIV8 N attribute is the clean number ("201.1"). Sections are the citable unit.

Chapter II copyright parts span 200–235: Parts 201–212 are the classic Copyright Office regs
(§ 201.x general/DMCA, § 202.x registration, § 210.x mechanical license, § 211 mask works,
§ 212 vessel designs); Parts 220–235 are the Copyright Claims Board (CASE Act) rules. This
ingest takes the WHOLE of Chapter II (all copyright parts) — no fake law, reserved sections
(no body) become addressable part/section nodes without a version.

37 C.F.R. is OFFICIAL, authentic, consolidated US regulatory text → is_official_language=1,
is_authentic=1, is_consolidated=1.

Run (scratch DB with schema.sql + seed_jurisdictions.sql + migration 001 applied):
    python src/store/ingest_ecfr.py --db /tmp/cfr.db \
        --xml spike/artifacts/us_37cfr.xml \
        --source-url https://www.ecfr.gov/api/versioner/v1/full/2026-07-20/title-37.xml

Load into the live corpus.db (only after review):
    python src/store/ingest_ecfr.py --db db/corpus.db --allow-corpus \
        --xml spike/artifacts/us_37cfr.xml \
        --source-url https://www.ecfr.gov/api/versioner/v1/full/2026-07-20/title-37.xml
"""
from __future__ import annotations

import argparse
import re

from _common import RecordSet, ordinal, run_ingest

INSTRUMENT = dict(jurisdiction="US", type="regulation", official_citation="37 C.F.R.",
                  ext_id_scheme="CFR", ext_id="us-37cfr-copyright",
                  title="37 C.F.R. — Copyright Office (Parts 201–212)")

# Chapter II = the U.S. Copyright Office, Library of Congress.
COPYRIGHT_CHAPTER = "II"


def loc(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _text(el) -> str:
    return " ".join("".join(el.itertext()).split())


def _head(el):
    h = el.find("./{*}HEAD")
    return _text(h) if h is not None else None


def _split_head(raw: str) -> tuple[str, str | None]:
    """A section HEAD is like '§ 201.1   Communication with the Copyright Office.' — split the
    '§ N' label from the heading. Falls back to the whole string as the heading."""
    m = re.match(r"^\s*§+\s*([0-9]+\.[0-9A-Za-z\-]+)\s*(.*)$", raw or "")
    if m:
        heading = m.group(2).strip().rstrip(".") or None
        return f"§ {m.group(1)}", heading
    return raw.strip(), None


# Section body: everything under the DIV8 except its HEAD and the trailing CITA/source note
# (eCFR authority/source credits — provenance metadata, not operative text).
_SKIP_BODY = {"HEAD", "CITA", "AUTH", "SOURCE", "EDNOTE", "FTNT"}


def _section_body(el) -> str:
    parts: list[str] = []
    for c in el:
        if loc(c.tag) in _SKIP_BODY:
            continue
        t = _text(c)
        if t:
            parts.append(t)
    return " ".join(parts).strip()


def parse(xml_path: str) -> RecordSet:
    import xml.etree.ElementTree as ET

    root = ET.parse(xml_path).getroot()
    chapter = None
    for el in root.iter():
        if loc(el.tag) == "DIV3" and el.get("N") == COPYRIGHT_CHAPTER:
            chapter = el
            break
    if chapter is None:
        raise SystemExit(f"Title 37 Chapter {COPYRIGHT_CHAPTER} (Copyright Office) not found in XML")

    rs = RecordSet()
    ch_head = _head(chapter) or "U.S. Copyright Office, Library of Congress"
    ch_local = rs.add(kind="chapter", label=f"Chapter {COPYRIGHT_CHAPTER}", heading=ch_head,
                      sort_int=0, citation="37 C.F.R. ch. II")

    counters = {"idx": 0}

    def walk(el, part_local: int | None, subpart_local: int | None):
        for c in el:
            name = loc(c.tag)
            counters["idx"] += 1
            i = counters["idx"]
            if name == "DIV5":                                   # PART
                num = c.get("N")
                heading = (_head(c) or "").split("—", 1)[-1].strip() or None
                si, su = ordinal(num, i)
                lid = rs.add(kind="part", label=f"Part {num}", heading=heading,
                             sort_int=si, sort_suffix=su, parent_local=ch_local,
                             citation=f"37 C.F.R. Part {num}")
                walk(c, lid, None)
            elif name == "DIV6":                                 # SUBPART (letter N, citable)
                letter = c.get("N")
                heading = (_head(c) or "").split("—", 1)[-1].strip() or None
                si, su = ordinal(letter, i)
                lid = rs.add(kind="subpart", label=f"Subpart {letter}", heading=heading,
                             sort_int=si, sort_suffix=su, parent_local=part_local,
                             citation=f"37 C.F.R. Part {_part_num(part_local, rs)} Subpart {letter}")
                walk(c, part_local, lid)
            elif name == "DIV7":                                 # SUBJGRP (hash id) — pass through
                walk(c, part_local, subpart_local)
            elif name == "DIV8":                                 # SECTION — the citable unit
                num = c.get("N")
                label, heading = _split_head(_head(c) or f"§ {num}")
                if not num:                                      # defensive: derive from label
                    mm = re.match(r"§\s*([0-9.]+)", label)
                    num = mm.group(1) if mm else str(i)
                si, su = ordinal(num, i)
                body = _section_body(c) or None
                rs.add(kind="section", label=f"§ {num}", heading=heading,
                       sort_int=si, sort_suffix=su,
                       parent_local=subpart_local or part_local,
                       citation=f"37 C.F.R. § {num}", content=body)
            else:                                                # APPENDIX / other — descend
                walk(c, part_local, subpart_local)

    walk(chapter, None, None)
    return rs


def _part_num(part_local: int | None, rs: RecordSet) -> str:
    if part_local is None:
        return ""
    for r in rs.records:
        if r["local_id"] == part_local:
            return r["label"].replace("Part ", "")
    return ""


def main() -> None:
    ap = argparse.ArgumentParser(description="Ingest US 37 C.F.R. Copyright Office regs (eCFR XML).")
    ap.add_argument("--db", required=True)
    ap.add_argument("--xml", required=True, help="eCFR full-title-37 XML")
    ap.add_argument("--source-url", required=True)
    ap.add_argument("--point-in-time", default=None)
    ap.add_argument("--allow-corpus", action="store_true")
    a = ap.parse_args()
    s = run_ingest(a.db, INSTRUMENT, parse(a.xml), a.source_url, point_in_time=a.point_in_time,
                   allow_corpus=a.allow_corpus, is_official_language=1, is_authentic=1,
                   is_consolidated=1, version_label="eCFR (govinfo)", fts_title="37 C.F.R.")
    print(f"instrument #{s['instrument_id']}  37 C.F.R. (Copyright Office) — {s['provisions']} "
          f"provisions: {s['by_kind'].get('part', 0)} parts, "
          f"{s['by_kind'].get('subpart', 0)} subparts, {s['by_kind'].get('section', 0)} sections; "
          f"versions new {s['versions_new']}, unchanged {s['versions_unchanged']}")


if __name__ == "__main__":
    main()
