"""Wave D (2f) — 37 C.F.R.: ADDITIVE official GPO annual-CFR baseline (pinned pit layer).

The corpus's 37 C.F.R. working text comes from the eCFR — a government FINDING AID, not the
official legal edition (CLAUDE prime rule 3a). The GPO annual CFR IS the official edition.
This ingest pins the GPO annual edition (bulk XML, e.g. CFR-2025-title37-vol1.xml, "Revised
as of July 1, 2025") as a point-in-time BASELINE alongside the eCFR rows:

  - versions pinned at the edition's revision date (--point-in-time 2025-07-01) with
    is_current=0 via `store_pinned_version` — the eCFR rows STAY the current working text.
  - provisions are MATCHED on existing citations ("37 C.F.R. § 201.1", "37 C.F.R. Part 202,
    App. A"); NO provision rows are created — a GPO section absent from the eCFR tree (or
    vice versa: eCFR sections newer than the annual edition) is REPORTED, never minted or
    silently dropped. The trees differ legitimately: the annual edition is a July-1 snapshot.
  - instruments.source_edition is NOT changed here: it describes the CURRENT working text
    (eCFR = finding_aid, honest). The official baseline is identified by its version_label.

GPO CFRDOC shape (differs from eCFR DIVx): CHAPTER elements carry LRH "37 CFR Ch. II" —
Chapter II (U.S. Copyright Office) spans TWO CHAPTER elements (Subchapter A parts 200-212,
Subchapter B parts 220-235). PART > SECTION (SECTNO/SUBJECT/P...) and APPENDIX elements.
Excluded from bodies (segmentation rules 3/4/5): the CONTENTS table-of-contents, AUTH/SOURCE/
EDNOTE/CITA credits, FTNT footnote bodies, SU/FTREF superscript footnote markers, PRTPAGE
page markers, and the appendix's own title HD.

Run (scratch first; artifact fetched from
https://www.govinfo.gov/bulkdata/CFR/2025/title-37/CFR-2025-title37-vol1.xml):
    python src/store/ingest_cfr_annual.py --db db/scratch-corpus.db \
        --xml spike/artifacts/us_37cfr_gpo_2025.xml --point-in-time 2025-07-01 \
        --source-url "https://www.govinfo.gov/bulkdata/CFR/2025/title-37/CFR-2025-title37-vol1.xml"
"""
from __future__ import annotations

import argparse
import os
import re
import sqlite3
import xml.etree.ElementTree as ET

from _common import require_migration, store_pinned_version

INSTRUMENT_KEY = ("US", "CFR", "us-37cfr-copyright")   # must already exist (id 19)
VERSION_LABEL_FMT = "GPO annual CFR (official ed., as of {pit})"
CH_LRH = "37 CFR Ch. II "    # trailing space: "Ch. III"/"Ch. IV" also start with "Ch. II"

# Elements whose text (and children) are NOT operative section/appendix body text.
SKIP = {"SECTNO", "SUBJECT", "CITA", "AUTH", "SOURCE", "EDNOTE", "FTNT", "PRTPAGE",
        "SU", "FTREF", "EAR", "LRH", "RRH", "CONTENTS", "TOC", "SECAUTH", "STARS", "EFFDNOT"}


def _text(el, skip=frozenset()) -> str:
    """Text of a subtree, pruning `skip` subtrees entirely (their tails still belong
    to the parent flow and are kept)."""
    parts: list[str] = []

    def rec(e, top: bool):
        if not top and e.tag in skip:
            return
        if e.text:
            parts.append(e.text)
        for c in e:
            rec(c, False)
            if c.tail:
                parts.append(c.tail)

    rec(el, True)
    return " ".join(" ".join(parts).split())


def parse(xml_path: str) -> list[dict]:
    """Return [{citation, content}] for Chapter II sections + appendices (verbatim GPO text)."""
    root = ET.parse(xml_path).getroot()
    chapters = [c for c in root.iter("CHAPTER")
                if (c.find("LRH") is not None and (c.find("LRH").text or "").startswith(CH_LRH))]
    if not chapters:
        raise SystemExit("no CHAPTER with LRH '37 CFR Ch. II' — wrong file?")
    out: list[dict] = []
    for ch in chapters:
        for sec in ch.iter("SECTION"):
            no = sec.find("SECTNO")
            num = re.sub(r"^§+\s*", "", (no.text or "").strip()) if no is not None else ""
            if not num:
                continue
            body = _text(sec, SKIP)
            if not body:                                  # reserved / empty — no blank versions
                continue
            out.append({"citation": f"37 C.F.R. § {num}", "content": body})
        for app in ch.iter("APPENDIX"):
            hd = app.find("HD")
            title = (hd.text or "").strip() if hd is not None else ""
            am = re.search(r"Appendix\s+([A-Za-z0-9]+)\s+to\s+Part\s+(\d+)", title)
            if not am:
                ear = app.find("EAR")
                am = re.search(r"Pt\.\s*(\d+),\s*App\.\s*([A-Za-z0-9]+)",
                               (ear.text or "") if ear is not None else "")
                if am:
                    cite = f"37 C.F.R. Part {am.group(1)}, App. {am.group(2)}"
                else:
                    print(f"  ! unidentifiable APPENDIX skipped: {title[:60]!r}")
                    continue
            else:
                cite = f"37 C.F.R. Part {am.group(2)}, App. {am.group(1)}"
            # Internal HDs (e.g. App. B "I. Printed Textual Matter") are operative structure;
            # only the appendix's own title HD is a label — skip just that one element.
            parts = []
            for child in app:
                if child.tag in SKIP or (child.tag == "HD" and child is hd):
                    continue
                t = _text(child, SKIP)
                if t:
                    parts.append(t)
            body = " ".join(parts).strip()
            if body:
                out.append({"citation": cite, "content": body})
    # duplicate-citation guard (a section must appear once per edition)
    seen: set[str] = set()
    for r in out:
        if r["citation"] in seen:
            raise SystemExit(f"duplicate citation in GPO parse: {r['citation']}")
        seen.add(r["citation"])
    return out


def ingest(db_path: str, xml_path: str, source_url: str, point_in_time: str,
           allow_corpus: bool = False) -> dict:
    if os.path.basename(db_path) == "corpus.db" and not allow_corpus:
        raise SystemExit("refusing to write the live corpus.db — pass --allow-corpus")
    recs = parse(xml_path)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    require_migration(conn)
    row = conn.execute("SELECT id FROM instruments WHERE jurisdiction=? AND ext_id_scheme=? "
                       "AND ext_id=?", INSTRUMENT_KEY).fetchone()
    if not row:
        raise SystemExit("37 C.F.R. instrument not found — this layer is additive only")
    iid = row[0]
    label = VERSION_LABEL_FMT.format(pit=point_in_time)
    stats = {"instrument_id": iid, "matched": 0, "new": 0, "unchanged": 0, "unmatched": []}
    for r in recs:
        prow = conn.execute("SELECT id FROM provisions WHERE instrument_id=? AND citation=?",
                            (iid, r["citation"])).fetchone()
        if not prow:                                      # additive: report, never mint
            stats["unmatched"].append(r["citation"])
            continue
        outcome = store_pinned_version(
            conn, iid, prow[0], r["citation"], r["content"], source_url=source_url,
            point_in_time=point_in_time, version_label=label, fts_title="37 C.F.R.",
            is_authentic=1, is_consolidated=1)
        stats["matched"] += 1
        stats["new" if outcome == "new" else "unchanged"] += 1
    conn.commit()
    conn.close()
    return stats


def main() -> None:
    ap = argparse.ArgumentParser(description="37 C.F.R. — additive official GPO annual-CFR "
                                             "baseline (pinned pit layer; eCFR stays current).")
    ap.add_argument("--db", required=True)
    ap.add_argument("--xml", required=True, help="GPO bulk CFR XML (CFR-<yr>-title37-vol1.xml)")
    ap.add_argument("--source-url", required=True)
    ap.add_argument("--point-in-time", required=True, help="the edition's revision date, e.g. 2025-07-01")
    ap.add_argument("--allow-corpus", action="store_true")
    a = ap.parse_args()
    s = ingest(a.db, a.xml, a.source_url, a.point_in_time, a.allow_corpus)
    print(f"instrument #{s['instrument_id']}  37 C.F.R. — GPO annual baseline @ {a.point_in_time}")
    print(f"  matched provisions : {s['matched']} (new {s['new']}, unchanged {s['unchanged']}; "
          f"is_current untouched — eCFR stays the working text)")
    if s["unmatched"]:
        print(f"  in GPO edition but NOT in the eCFR tree ({len(s['unmatched'])}) — reported, not minted:")
        for c in s["unmatched"]:
            print(f"    {c}")


if __name__ == "__main__":
    main()
