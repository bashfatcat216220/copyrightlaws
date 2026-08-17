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

# Title says 200–235: Chapter II as ingested spans Parts 200–235 (incl. the reserved Part 200
# and the Copyright Claims Board parts) — the old "Parts 201–212" undersold what we hold (F-CFR2).
INSTRUMENT = dict(jurisdiction="US", type="regulation", official_citation="37 C.F.R.",
                  ext_id_scheme="CFR", ext_id="us-37cfr-copyright",
                  title="37 C.F.R. — Copyright Office (Parts 200–235)")

# Chapter II = the U.S. Copyright Office, Library of Congress.
COPYRIGHT_CHAPTER = "II"


def loc(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _text(el) -> str:
    return " ".join("".join(el.itertext()).split())


def _head(el):
    h = el.find("./{*}HEAD")
    return _text(h) if h is not None else None


# A section/part whose HEAD carries the official bracket-note '[Reserved]' and no body is a
# placeholder the CFR editors hold open — it is not in-force text. status='reserved' (allowed
# by the provisions CHECK since migration 003) so the metadatum stops overstating (F-CFR audit
# 2026-08-16). The bracket-note is the SIGNAL — a section that merely mentions "[Reserved]" in
# a real body keeps status='in_force'. Returns None otherwise (RecordSet.add applies defaults).
_RESERVED = re.compile(r"\[\s*Reserved\s*\]", re.I)


def _reserved_status(heading: str | None, body: str | None) -> str | None:
    return "reserved" if (heading and _RESERVED.search(heading) and not (body or "").strip()) else None


def _split_head(raw: str) -> tuple[str, str | None]:
    """A section HEAD is like '§ 201.1   Communication with the Copyright Office.' — split the
    '§ N' label from the heading. A reserved RANGE reads '§§ 201.19-201.21   [Reserved]': the
    number token is 'N.N-N.N' — capture the WHOLE range (F-CFR1; the old single-number pattern
    stopped inside the 2nd dotted number, leaving '.21 [Reserved]' as the heading) and keep the
    source's '§'/'§§' sigil. Falls back to the whole string as the label."""
    m = re.match(r"^\s*(§+)\s*([0-9]+\.[0-9A-Za-z]+(?:-[0-9]+\.[0-9A-Za-z]+)?)\s*(.*)$", raw or "")
    if m:
        heading = m.group(3).strip().rstrip(".") or None
        return f"{m.group(1)} {m.group(2)}", heading
    return raw.strip(), None


# Section body: everything under the DIV8 except its HEAD and the trailing CITA/source note
# (eCFR authority/source credits — provenance metadata, not operative text). NOTE: SECAUTH is
# deliberately NOT skipped here — several existing DIV8 sections (e.g. § 201.10) already carry a
# SECAUTH credit in their stored body; changing that would re-version in-force sections. SECAUTH
# is skipped only for APPENDIX bodies (see _APPX_SKIP_BODY), where it is the closing credit.
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


# ── Appendices (DIV9 TYPE="APPENDIX") — the schedule model ────────────────────
# eCFR appendices carry no DIV8 sections; their operative text sits directly in <P>/<HD2>
# children. The current walk() descends through them (they hit the `else` branch) and drops
# every word. We model an appendix as kind='schedule' (the container, holding the FULL appendix
# text — searchable + versioned) with kind='schedule_para' children, role='schedule' — mirroring
# the TRIPS annex (ingest_treaty._parse_trips_annex). Where the source marks internal sections
# with <HD2> headers (Appendix B to Part 202: "I. Printed Textual Matter" … "X. Works Existing
# in More Than One Medium"), each becomes an addressable schedule_para keyed on the source's own
# roman marker; the leading un-headed paragraphs (a.–e.) file as an "Introductory" child. Where
# there are NO <HD2> headers (Appendix A to Part 202) the appendix has no source sub-sections, so
# the whole body lives on the container with no fabricated segmentation. Segmentation stops at the
# structural boundary — SECAUTH/CITA credits and the next DIV5/DIV9 are excluded (rule 3).
# Appendix bodies additionally drop SECAUTH (the closing statutory-authority credit) — it is
# provenance, not operative appendix text, and the structural boundary of the appendix (rule 3).
_APPX_SKIP_BODY = _SKIP_BODY | {"SECAUTH"}
_HD2_MARK = re.compile(r"^\s*([IVXLC]+|[A-Z0-9]+)[.)]\s*(.*)$")


def _appendix_body(el) -> str:
    """Full appendix text: every child except HEAD and the trailing SECAUTH/CITA credit."""
    parts: list[str] = []
    for c in el:
        if loc(c.tag) in _APPX_SKIP_BODY:
            continue
        t = _text(c)
        if t:
            parts.append(t)
    return " ".join(parts).strip()


def _appendix_children(el):
    """Segment an appendix into (marker, heading, body) schedule_para blocks at <HD2> section
    headers. Returns [] when the appendix has no <HD2> headers (no source sub-sections)."""
    kids = list(el)
    hd2_idx = [i for i, c in enumerate(kids) if loc(c.tag) == "HD2"]
    if not hd2_idx:
        return []
    blocks: list[tuple[str | None, str | None, str]] = []
    # leading paragraphs before the first HD2 (skip HEAD) → an "Introductory" block
    lead: list[str] = []
    for c in kids[:hd2_idx[0]]:
        if loc(c.tag) in _APPX_SKIP_BODY:
            continue
        t = _text(c)
        if t:
            lead.append(t)
    if lead:
        blocks.append((None, "Introductory", " ".join(lead).strip()))
    for k, start in enumerate(hd2_idx):
        end = hd2_idx[k + 1] if k + 1 < len(hd2_idx) else len(kids)
        raw_head = _text(kids[start])
        m = _HD2_MARK.match(raw_head)
        marker = m.group(1) if m else None
        heading = (m.group(2).strip() if m else raw_head).rstrip(".") or None
        body_parts: list[str] = []
        for c in kids[start + 1:end]:
            if loc(c.tag) in _APPX_SKIP_BODY:       # stop at trailing SECAUTH/CITA credit
                continue
            t = _text(c)
            if t:
                body_parts.append(t)
        blocks.append((marker, heading, " ".join(body_parts).strip()))
    return blocks


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
                             citation=f"37 C.F.R. Part {num}",
                             status=_reserved_status(heading, None))
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
                    mm = re.match(r"§+\s*([0-9.]+)", label)
                    num = mm.group(1) if mm else str(i)
                si, su = ordinal(num, i)
                body = _section_body(c) or None
                # A reserved RANGE (N='201.19-201.21') labels with the source's '§§' sigil;
                # the citation keeps the single-'§' form (the stable provision key).
                sig = "§§" if "-" in num else "§"
                rs.add(kind="section", label=f"{sig} {num}", heading=heading,
                       sort_int=si, sort_suffix=su,
                       parent_local=subpart_local or part_local,
                       citation=f"37 C.F.R. § {num}", content=body,
                       status=_reserved_status(heading, body))
            elif c.get("TYPE") == "APPENDIX":                    # APPENDIX (DIV9) — schedule model
                # N = "Appendix A to Part 202"; derive the App letter + part for the citation.
                n = c.get("N") or ""
                am = re.search(r"Appendix\s+([A-Za-z0-9]+)\s+to\s+Part\s+(\d+)", n)
                app_letter = am.group(1) if am else None
                app_part = am.group(2) if am else _part_num(part_local, rs)
                head = _head(c) or n
                # citation: "37 C.F.R. Part 202, App. A" (the source's stable appendix key).
                cite = (f"37 C.F.R. Part {app_part}, App. {app_letter}" if app_letter
                        else f"37 C.F.R. Part {app_part} {n}")
                si, su = ordinal(app_letter or str(i), i)
                si = 90000 + si                                  # file appendices after the sections
                aid = rs.add(kind="schedule", label=(f"Appendix {app_letter}" if app_letter else n),
                             heading=head, sort_int=si, sort_suffix=su, role="schedule",
                             parent_local=part_local, citation=cite,
                             content=_appendix_body(c) or None)
                # addressable sub-sections at the source's <HD2> boundaries (none → no children).
                for j, (marker, sub_head, body) in enumerate(_appendix_children(c)):
                    child_cite = f"{cite}, § {marker}" if marker else f"{cite} (Introductory)"
                    rs.add(kind="schedule_para", label=(f"§ {marker}" if marker else "Introductory"),
                           heading=sub_head, sort_int=j, role="schedule",
                           parent_local=aid, citation=child_cite, content=body or None)
                # Descend through the appendix's leaf children (P/HD2/…) WITHOUT adding them: they
                # match no DIV5-8/APPENDIX branch, so this only advances counters["idx"] exactly as
                # the pre-change code did — keeping the doc-order fallback of later, non-appendix
                # provisions' sort_int byte-stable (dotted section numbers like '203.1' fall back to
                # doc-index; shifting the counter here would re-sort every Part 203+ provision).
                walk(c, part_local, subpart_local)
            else:                                                # other structural node — descend
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
