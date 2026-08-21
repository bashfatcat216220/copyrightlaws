"""Human sign-off gate for the comparative matrix (prime rule 4).

A drafted cell is shown as authority ONLY once a person verifies it here. The schema trigger
`matrix_verified_needs_source` refuses to verify a cell with no `source_version`, so a documented-gap
cell (source_version NULL) cannot be promoted — the gate is enforced in the DB, not just this script.

    python src/matrix/verify.py --db db/corpus.db --list                       # review before signing
    python src/matrix/verify.py --db db/corpus.db --by "Bing" --jurisdiction US --attribute term_individual
    python src/matrix/verify.py --db db/corpus.db --by "Bing" --all             # verify every grounded draft
"""
from __future__ import annotations

import argparse
import sqlite3
from datetime import datetime, timezone


def _list(conn) -> None:
    rows = conn.execute(
        "SELECT jurisdiction, attribute, value, source_citation, source_version, verified_by "
        "FROM matrix_cells ORDER BY attribute, jurisdiction").fetchall()
    if not rows:
        print("matrix_cells is empty — run load_cells.py first.")
        return
    for jur, attr, value, cite, sv, vby in rows:
        status = f"VERIFIED by {vby}" if vby else ("DRAFT" if sv else "DRAFT (gap — unsourced)")
        print(f"  [{status:24}] {attr:26} {jur:3} · {cite or '—'}\n      {value}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", required=True)
    ap.add_argument("--list", action="store_true", help="print every cell + status, make no change")
    ap.add_argument("--by", help="verifier name (sets verified_by)")
    ap.add_argument("--jurisdiction")
    ap.add_argument("--attribute")
    ap.add_argument("--all", action="store_true", help="verify every grounded draft")
    a = ap.parse_args()

    conn = sqlite3.connect(a.db)
    conn.execute("PRAGMA foreign_keys = ON")
    if a.list or not a.by:
        _list(conn)
        if not a.by:
            print("\n(pass --by \"<name>\" with --all or --jurisdiction/--attribute to verify.)")
        return

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if a.all:
        targets = conn.execute(
            "SELECT jurisdiction, attribute FROM matrix_cells WHERE verified_by IS NULL").fetchall()
    elif a.jurisdiction and a.attribute:
        targets = [(a.jurisdiction, a.attribute)]
    else:
        raise SystemExit("specify --all, or both --jurisdiction and --attribute")

    verified, blocked = 0, []
    for jur, attr in targets:
        try:
            cur = conn.execute(
                "UPDATE matrix_cells SET verified_by=?, verified_at=? "
                "WHERE jurisdiction=? AND attribute=?", (a.by, now, jur, attr))
            if cur.rowcount:
                verified += 1
        except sqlite3.IntegrityError as e:                # trigger: verified cell must cite a source
            blocked.append((jur, attr, str(e)))
    conn.commit()
    print(f"verified {verified} cell(s) as '{a.by}'")
    for jur, attr, err in blocked:
        print(f"  BLOCKED {jur}/{attr}: {err} (documented gap — source it first)")
    conn.close()


if __name__ == "__main__":
    main()
