"""TARGETED backfill — CDPA 1988 Schedule 8 (Repeals) body text.  Wave E, 2f/2g audit #11.

Schedule 8 exists in the corpus as a CONTENT-LESS stub: `ingest_clml.py` walks
<P1>/<P2> paragraph structure, and Schedule 8's whole body is ONE `<Tabular>` (a
3-column repeals table: chapter / short title / extent of repeal), so no schedule_para
children and no version were ever created. The table IS in the retained CLML artifact —
this script extracts it verbatim and attaches it as the provision's version.

Why a separate script and not an `ingest_clml` change (rule 7): CDPA is point-in-time
monitored (fired alerts + a daily refresh re-ingest). Teaching the WHOLE CLML parser to
inline `<Tabular>` content would change the text of every table-carrying provision on the
next nightly refresh and fire dozens of false "amendment" alerts. This backfill touches
exactly one provision, which has no version history to disturb (0 versions today), so the
monitor can never diff it. Idempotent BY CONTENT: re-runs with unchanged text are no-ops.

Run (scratch first, then both central DBs):
    python src/store/backfill_cdpa_sch8.py --db db/corpus.db --allow-corpus \
        --xml spike/artifacts/cdpa.xml \
        --source-url https://www.legislation.gov.uk/ukpga/1988/48/data.xml
"""
from __future__ import annotations

import argparse
import html as htmlmod
import os
import re
import sqlite3
from datetime import datetime, timezone

from _common import sha256

CITATION = "CDPA 1988 Schedule 8"


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _cell(frag: str) -> str:
    txt = re.sub(r"<[^>]+>", " ", frag)
    return re.sub(r"\s+", " ", htmlmod.unescape(txt)).strip()


def extract(xml_path: str) -> str:
    """Schedule 8's repeals table, linearized verbatim: the <Reference> line ('Section
    303(2).'), then one line per <tr>, cells joined with ' — ' (a presentation separator
    only — every word is the source's). Empty spacer rows are dropped."""
    h = open(xml_path, encoding="utf-8", errors="replace").read()
    im = re.search(r'<Schedule\b[^>]*id="schedule-8"[^>]*>', h)
    if not im:
        raise SystemExit("schedule-8 element not found in the artifact — wrong file?")
    end = h.find("</Schedule>", im.end())
    seg = h[im.end():end if end != -1 else len(h)]
    lines: list[str] = []
    rm = re.search(r"<Reference\b[^>]*>(.*?)</Reference>", seg, re.S)
    if rm:
        ref = _cell(rm.group(1))
        if ref:
            lines.append(ref)
    for tr in re.finditer(r"<tr\b[^>]*>(.*?)</tr>", seg, re.S):
        cells = [_cell(m.group(1) or "") for m in
                 re.finditer(r"<td\b[^>]*>(.*?)</td>|<td\b[^>]*/>", tr.group(1), re.S)]
        row = " — ".join(c for c in cells if c)
        if row:
            lines.append(row)
    if len(lines) < 10:
        raise SystemExit(f"only {len(lines)} lines extracted — refusing (expected the "
                         "~78-row repeals table); artifact shape changed?")
    return "\n".join(lines)


def backfill(db_path: str, xml_path: str, source_url: str, point_in_time: str,
             allow_corpus: bool = False) -> None:
    if os.path.basename(db_path) == "corpus.db" and not allow_corpus:
        raise SystemExit("refusing to write the live corpus.db (pass --allow-corpus).")
    content = extract(xml_path)
    digest = sha256(content)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    row = conn.execute(
        "SELECT p.id, p.instrument_id, p.heading FROM provisions p "
        "JOIN instruments i ON i.id=p.instrument_id "
        "WHERE i.jurisdiction='GB' AND p.citation=?", (CITATION,)).fetchone()
    if not row:
        raise SystemExit(f"provision '{CITATION}' not found — nothing to backfill")
    pid, iid, heading = row
    cur = conn.execute("SELECT id, content_sha256 FROM versions WHERE provision_id=? "
                       "AND is_current=1", (pid,)).fetchone()
    if cur and cur[1] == digest:
        print(f"unchanged: {CITATION} already carries this text (version {cur[0]})")
    elif cur:                                       # correct the existing slot in place
        conn.execute("UPDATE versions SET content=?, content_sha256=?, source_url=?, "
                     "retrieved_at=? WHERE id=?",
                     (content, digest, source_url, now_iso(), cur[0]))
        conn.execute("DELETE FROM versions_fts WHERE rowid=?", (cur[0],))
        conn.execute("INSERT INTO versions_fts (rowid, title, citation, body) "
                     "VALUES (?,?,?,?)", (cur[0], "CDPA 1988", CITATION, content))
        print(f"updated in place: {CITATION} (version {cur[0]}, {len(content)} chars)")
    else:
        c2 = conn.execute(
            "INSERT INTO versions (instrument_id, provision_id, version_label, "
            "point_in_time, language, is_official_language, is_consolidated, is_authentic, "
            "content, content_sha256, source_url, retrieved_at, is_current) "
            "VALUES (?,?, 'legislation.gov.uk', ?, 'en', 1, 1, 1, ?,?,?,?, 1)",
            (iid, pid, point_in_time, content, digest, source_url, now_iso()))
        conn.execute("INSERT INTO versions_fts (rowid, title, citation, body) "
                     "VALUES (?,?,?,?)", (c2.lastrowid, "CDPA 1988", CITATION, content))
        print(f"attached: {CITATION} → new version {c2.lastrowid} "
              f"({len(content)} chars, {content.count(chr(10)) + 1} lines)")
    conn.execute("DELETE FROM provisions_fts WHERE rowid=?", (pid,))
    conn.execute("INSERT INTO provisions_fts (rowid, citation, heading, body) "
                 "VALUES (?,?,?,?)", (pid, CITATION, heading or "", content))
    conn.commit()
    conn.close()


def main() -> None:
    ap = argparse.ArgumentParser(description="Attach the CDPA Schedule 8 repeals-table text "
                                             "(targeted; never re-ingests CDPA).")
    ap.add_argument("--db", required=True)
    ap.add_argument("--xml", required=True, help="path to the retained cdpa.xml CLML artifact")
    ap.add_argument("--source-url", required=True)
    ap.add_argument("--point-in-time", default="2026-08-16",
                    help="date the artifact snapshot was current (default 2026-08-16)")
    ap.add_argument("--allow-corpus", action="store_true")
    a = ap.parse_args()
    backfill(a.db, a.xml, a.source_url, a.point_in_time, a.allow_corpus)


if __name__ == "__main__":
    main()
