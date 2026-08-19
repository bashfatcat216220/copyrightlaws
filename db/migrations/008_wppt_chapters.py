"""008 — WPPT: restore the real Chapter structure.

Like TRIPS (migration 007), the WIPO Performances and Phonograms Treaty was ingested as a
flat list of 33 articles, so its landing page had no chapter rail. WPPT is in fact divided
into five Chapters (I General Provisions, II Rights of Performers, III Rights of Producers
of Phonograms, IV Common Provisions, V Administrative and Final Clauses). This inserts those
Chapter containers and re-parents the articles, so WPPT rails like every chaptered instrument.

Structure is taken from the SOURCE artifact `spike/artifacts/wppt_wipolex.txt` (rule 9), not
memory (prime rule 1): chapter titles from the table-of-contents block, article→chapter
assignment from the body's chapter markers, with a sequential expected-counter (ingest rule 1)
so a cross-reference like a bare "Article 5" inside Chapter IV is not mistaken for a heading.
It ABORTS unless the parse covers the stored articles exactly.

STRUCTURE-ONLY (see 007): inserts kind='chapter' rows + updates article parent_id; writes NO
content/sha/version rows, so the change monitor and alerts are untouched. The Agreed Statements
(stored as recitals) surface as the trailing "Recitals" rail entry once chapters exist.
Idempotent (containers matched by citation).

Run:
    python db/migrations/008_wppt_chapters.py --db db/corpus.db
    python db/migrations/008_wppt_chapters.py --db db/corpus-demo.db
"""
from __future__ import annotations

import argparse
import os
import re
import sqlite3

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
DEFAULT_TXT = os.path.join(REPO, "spike", "artifacts", "wppt_wipolex.txt")


def parse_chapters(txt_path: str):
    """Return ordered [(roman, title, [art_no,...])] from the WPPT artifact."""
    raw = open(txt_path, encoding="utf-8", errors="replace").read()
    lines = [re.sub(r"[ \t]+", " ", l).strip() for l in raw.splitlines() if l.strip()]
    titles: dict = {}
    for l in lines:                                          # titles from the TOC block
        m = re.match(r"(?i)^chapter\s+([IVX]+)\s*[:\.]\s*(.+)$", l)
        if m and len(l) < 70:
            titles.setdefault(m.group(1).upper(), m.group(2).strip())
    order: list = []
    seen: dict = {}
    cur = None
    expected = 1
    for l in lines:
        mc = re.match(r"(?i)^chapter\s+([IVX]+)\b\s*(?:[:\.]\s*(.+))?$", l)
        ma = re.match(r"(?i)^article\s+(\d+)\b", l)
        if mc and len(l) < 70:
            cur = mc.group(1).upper()
            if cur not in seen:
                seen[cur] = []
                order.append(cur)
        elif ma and cur is not None:
            n = int(ma.group(1))
            if n == expected:                               # sequential only (drops cross-refs)
                seen[cur].append(n)
                expected += 1
    return [(r, titles.get(r, r), seen[r]) for r in order if seen[r]]


def _snapshot(conn, iid):
    return {
        "versions": conn.execute("SELECT COUNT(*) FROM versions").fetchone()[0],
        "alerts": conn.execute("SELECT COUNT(*) FROM alerts").fetchone()[0],
        "articles": conn.execute(
            "SELECT COUNT(*) FROM provisions WHERE instrument_id=? AND kind='article'",
            (iid,)).fetchone()[0],
        "sha_fingerprint": conn.execute(
            "SELECT COUNT(*), COALESCE(GROUP_CONCAT(content_sha256),'') FROM versions "
            "WHERE instrument_id=? AND is_current=1", (iid,)).fetchone(),
    }


def _upsert_container(conn, iid, parent_id, sort_int, label, heading, kind, citation):
    row = conn.execute(
        "SELECT id FROM provisions WHERE instrument_id=? AND citation=? AND kind=?",
        (iid, citation, kind)).fetchone()
    if row:
        conn.execute(
            "UPDATE provisions SET parent_id=?, sort_int=?, sort_suffix='', label=?, "
            "heading=?, role='enacting', status='in_force' WHERE id=?",
            (parent_id, sort_int, label, heading, row[0]))
        return row[0]
    cur = conn.execute(
        "INSERT INTO provisions (instrument_id, parent_id, sort_int, sort_suffix, label, "
        "heading, kind, role, citation, status) "
        "VALUES (?,?,?,'',?,?,?, 'enacting', ?, 'in_force')",
        (iid, parent_id, sort_int, label, heading, kind, citation))
    return cur.lastrowid


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", required=True)
    ap.add_argument("--txt", default=DEFAULT_TXT)
    a = ap.parse_args()
    if not os.path.exists(a.txt):
        raise SystemExit(f"source artifact not found: {a.txt} (rule 9 — cannot confirm structure)")

    chapters = parse_chapters(a.txt)
    src_arts = [n for _, _, arts in chapters for n in arts]
    if len(src_arts) != len(set(src_arts)):
        raise SystemExit(f"artifact parse produced duplicate articles: {sorted(src_arts)}")

    conn = sqlite3.connect(a.db)
    conn.execute("PRAGMA foreign_keys = ON")
    row = conn.execute(
        "SELECT id FROM instruments WHERE ext_id_scheme='TREATY' AND ext_id='wppt-1996'").fetchone()
    if not row:                                             # fall back to a title match
        row = conn.execute(
            "SELECT id FROM instruments WHERE jurisdiction='INT' AND title LIKE '%Performances and Phonograms%'"
        ).fetchone()
    if not row:
        raise SystemExit("WPPT instrument not found in this DB")
    iid = row[0]

    before = _snapshot(conn, iid)
    art_id = {}
    for pid, label in conn.execute(
            "SELECT id, label FROM provisions WHERE instrument_id=? AND kind='article'", (iid,)):
        m = re.match(r"(?i)article\s+(\d+)\b", label)
        if m:
            art_id[int(m.group(1))] = pid
    if set(src_arts) != set(art_id):
        only_src = sorted(set(src_arts) - set(art_id))
        only_db = sorted(set(art_id) - set(src_arts))
        raise SystemExit(f"artifact/DB article mismatch — only in source: {only_src}; "
                         f"only in DB: {only_db}; refusing to guess")
    print(f"source artifact: {len(chapters)} Chapters, {len(src_arts)} articles; "
          f"exact match to the {len(art_id)} stored articles")

    n_ch = n_reparent = 0
    for roman, title, arts in chapters:
        cid = _upsert_container(
            conn, iid, None, min(arts), f"Chapter {roman}", title, "chapter",
            f"WPPT Chapter {roman}")
        n_ch += 1
        for n in arts:
            conn.execute("UPDATE provisions SET parent_id=? WHERE id=?", (cid, art_id[n]))
            n_reparent += 1
    conn.commit()

    after = _snapshot(conn, iid)
    print(f"containers: {n_ch} Chapters; re-parented {n_reparent} articles")
    assert after["versions"] == before["versions"], "version count changed"
    assert after["alerts"] == before["alerts"], "alert count changed"
    assert after["articles"] == before["articles"], "article count changed"
    assert after["sha_fingerprint"] == before["sha_fingerprint"], \
        "WPPT current-version text/sha changed — NOT structure-only!"
    print(f"  invariants: versions {after['versions']}, alerts {after['alerts']} unchanged; "
          f"{after['articles']} articles intact; WPPT current-version SHAs byte-identical")
    for lbl, hd in conn.execute(
            "SELECT label, heading FROM provisions WHERE instrument_id=? AND kind='chapter' "
            "AND parent_id IS NULL ORDER BY sort_int", (iid,)):
        print(f"     {lbl:12} · {hd}")
    conn.close()


if __name__ == "__main__":
    main()
