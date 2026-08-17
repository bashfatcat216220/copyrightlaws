#!/usr/bin/env python3
"""005 — NULL out CDPA dotted-leader "headings" (surgical, metadata-only).

Six repealed CDPA sections (s.265/268/282/283/284/300) stored the source's dotted-leader
"no heading" marker (". . . .") in `provisions.heading`, while the real repeal notice
("S. 265 repealed (9.12.2001) by S.I. 2001/3949…") sits in the body. Because they *have* a
heading, the reader railed the dots instead of the notice → a wall of dots in the sidebar.

Fix: set heading=NULL on any CDPA provision whose heading is only a dotted leader, so the
reader falls back to the repeal-notice incipit. Metadata-only — no version/content/sha/
is_current writes, so the change monitor + the 91 alerts are untouched (CLAUDE rule 7).
Durably prevented at ingest by `ingest_clml._heading`. Idempotent; no-op on re-run.

Usage: python db/migrations/005_cdpa_dotted_headings.py --db db/corpus.db
"""
import argparse
import re
import sqlite3

DOTS_ONLY = re.compile(r"[.\s]*(\.\s*){4,}\.?\s*")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", required=True)
    a = ap.parse_args()
    conn = sqlite3.connect(a.db)
    iid = conn.execute("SELECT id FROM instruments WHERE ext_id='ukpga/1988/48'").fetchone()
    if not iid:
        raise SystemExit("CDPA instrument not found")
    iid = iid[0]
    rows = conn.execute(
        "SELECT id, citation, heading FROM provisions WHERE instrument_id=? AND heading IS NOT NULL",
        (iid,)).fetchall()
    targets = [(pid, cit) for pid, cit, h in rows if h and DOTS_ONLY.fullmatch(h.strip())]
    for pid, cit in targets:
        conn.execute("UPDATE provisions SET heading=NULL WHERE id=?", (pid,))
        # keep the FTS heading column in sync (its rowid is the provision id)
        conn.execute("UPDATE provisions_fts SET heading='' WHERE rowid=?", (pid,))
        print(f"  heading NULLed: {cit}")
    conn.commit()
    remaining = sum(1 for _, _, h in conn.execute(
        "SELECT id, citation, heading FROM provisions WHERE instrument_id=? AND heading IS NOT NULL",
        (iid,)).fetchall() if h and DOTS_ONLY.fullmatch(h.strip()))
    print(f"{a.db}: {len(targets)} dotted headings NULLed; {remaining} remaining (expect 0)")
    conn.close()


if __name__ == "__main__":
    main()
