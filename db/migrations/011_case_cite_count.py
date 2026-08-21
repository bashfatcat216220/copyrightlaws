"""011 — case_treatment.cite_count (additive column; re-fetch design rev. 2, finding S6).

CourtListener's citeCount at fetch time — source-given, dated by the row's retrieved_at.
Without it the reader rail orders cases newest-first and the citeCount ranking win never
reaches the screen (Harper & Row 1985 would sit at the bottom of § 107's rail). Rail order
becomes: cite_count DESC (NULLs last), then date.

ADDITIVE + idempotent: adds one nullable INTEGER column; no data writes (values land only
via the gated re-fetch apply). No versions/provisions/alerts/monitor impact.

Validate on a sqlite-backup CLONE first (CLAUDE.md rule 9), then apply to BOTH DBs:
    python db/migrations/011_case_cite_count.py --db db/corpus.db
    python db/migrations/011_case_cite_count.py --db db/corpus-demo.db
"""
from __future__ import annotations

import argparse
import sqlite3


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", required=True)
    a = ap.parse_args()

    conn = sqlite3.connect(a.db)
    conn.execute("PRAGMA foreign_keys = ON")
    cols = [r[1] for r in conn.execute("PRAGMA table_info(case_treatment)")]
    if "cite_count" in cols:
        print("cite_count already present — no change (idempotent).")
    else:
        conn.execute("ALTER TABLE case_treatment ADD COLUMN cite_count INTEGER")
        conn.commit()
        print("added case_treatment.cite_count (nullable INTEGER, all rows NULL).")
    n_null = conn.execute("SELECT COUNT(*) FROM case_treatment WHERE cite_count IS NULL").fetchone()[0]
    n = conn.execute("SELECT COUNT(*) FROM case_treatment").fetchone()[0]
    fk_ok = not conn.execute("PRAGMA foreign_key_check").fetchall()
    integ = conn.execute("PRAGMA integrity_check").fetchone()[0]
    print(f"rows: {n} (NULL cite_count: {n_null}) · foreign_key_check ok: {fk_ok} · "
          f"integrity_check: {integ}")
    conn.close()


if __name__ == "__main__":
    main()
