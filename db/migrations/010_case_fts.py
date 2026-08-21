"""010 — Case full-text search: index case_treatment.holding into a case_fts table (issue 4).

Platform review 2026-08-21, issue 4: `/search?q=fair use` returned statute/treaty snippets only —
opinion text was unreachable because cases carry no `versions` rows (we never re-host opinion
text; finding aid, prime rule 2), so nothing about them was in versions_fts. This adds a
dedicated FTS5 table over exactly what the corpus RECORDS about each citing link: the case name,
its citation, and the CourtListener excerpt stored in `case_treatment.holding`. rowid =
case_treatment.id, so a hit resolves to both the case page and the provision it is recorded as
citing. Search honesty: the searchable surface is the recorded excerpt, NOT the full opinion —
the UI labels it that way and links out to the source for the full text.

ADDITIVE + rebuildable: creates/repopulates only `case_fts`. No writes to instruments, provisions,
versions, case_treatment, alerts, or matrix_cells; sha/monitor untouched. Idempotent (full
rebuild every run). The backfill calls the SAME `sync_case_fts` the ingest now runs
(src/store/ingest_cases.py), so migration and ingest cannot drift.

Validate on a sqlite-backup CLONE first (CLAUDE.md rule 9), then apply to BOTH DBs:
    python db/migrations/010_case_fts.py --db db/corpus.db
    python db/migrations/010_case_fts.py --db db/corpus-demo.db
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))
from store.ingest_cases import sync_case_fts  # noqa: E402


def _snapshot(conn) -> dict:
    return {
        "cases": conn.execute("SELECT COUNT(*) FROM instruments WHERE type='case'").fetchone()[0],
        "treatments": conn.execute("SELECT COUNT(*) FROM case_treatment").fetchone()[0],
        "provisions": conn.execute("SELECT COUNT(*) FROM provisions").fetchone()[0],
        "versions": conn.execute("SELECT COUNT(*) FROM versions").fetchone()[0],
        "alerts": conn.execute("SELECT COUNT(*) FROM alerts").fetchone()[0],
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", required=True)
    a = ap.parse_args()

    conn = sqlite3.connect(a.db)
    conn.execute("PRAGMA foreign_keys = ON")

    before = _snapshot(conn)
    indexed = sync_case_fts(conn)
    conn.commit()
    after = _snapshot(conn)

    probe = conn.execute("SELECT COUNT(*) FROM case_fts WHERE case_fts MATCH 'copyright'").fetchone()[0]
    fk_ok = not conn.execute("PRAGMA foreign_key_check").fetchall()
    integ = conn.execute("PRAGMA integrity_check").fetchone()[0]

    print(f"case_fts rows indexed: {indexed}  (case_treatment rows: {after['treatments']})")
    print(f"probe MATCH 'copyright': {probe} hits")
    print(f"invariant (cases/treatments/provisions/versions/alerts unchanged): "
          f"{before == after}")
    print(f"foreign_key_check ok: {fk_ok}  ·  integrity_check: {integ}")
    conn.close()


if __name__ == "__main__":
    main()
