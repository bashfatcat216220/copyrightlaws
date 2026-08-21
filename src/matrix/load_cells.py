"""Load the comparative-matrix seed (`seed_cells.CELLS`) into `matrix_cells` as DRAFTS.

Resolves each cell's (instrument_ext_id, source_citation) -> the provision's is_current version id
(= `source_version`, the grounding). A cell whose citation does NOT resolve is REFUSED (never a fake
cell). A cell with `source_citation=None` is a documented gap -> loaded with source_version=NULL
(can never be verified until sourced). Every cell is stored drafted_by='model:claude-opus-4-8',
verified_by=NULL — shown as authority only after `verify.py` (prime rule 4).

Idempotent: re-running upserts on UNIQUE (jurisdiction, attribute) but NEVER clobbers a cell a human
has already verified (the ON CONFLICT update is gated on verified_by IS NULL).

    python src/matrix/load_cells.py --db db/corpus.db --allow-corpus
"""
from __future__ import annotations

import argparse
import os
import sqlite3
from datetime import datetime, timezone

from seed_cells import CELLS  # noqa: E402  (run as a script from this dir or via -m)

DRAFTED_BY = "model:claude-opus-4-8"


def _resolve(conn, ext_id, citation):
    """(instrument_ext_id, citation) -> is_current version id, or None. Returns (version_id, err)."""
    if not ext_id or not citation:
        return None, None                                  # documented gap — source_version NULL
    inst = conn.execute("SELECT id FROM instruments WHERE ext_id=?", (ext_id,)).fetchone()
    if not inst:
        return None, f"instrument ext_id '{ext_id}' not found"
    prov = conn.execute("SELECT id FROM provisions WHERE instrument_id=? AND citation=?",
                        (inst[0], citation)).fetchone()
    if not prov:
        return None, f"provision '{citation}' not found in {ext_id}"
    ver = conn.execute("SELECT id FROM versions WHERE provision_id=? AND is_current=1", (prov[0],)).fetchone()
    if not ver:
        return None, f"'{citation}' has no current version (subsection with no standalone text?)"
    return ver[0], None


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", required=True)
    ap.add_argument("--allow-corpus", action="store_true")
    a = ap.parse_args()
    if os.path.basename(a.db) == "corpus.db" and not a.allow_corpus:
        raise SystemExit("refusing to write the live corpus.db — pass --allow-corpus.")

    conn = sqlite3.connect(a.db)
    conn.execute("PRAGMA foreign_keys = ON")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    loaded = gaps = refused = 0
    for jur, attr, ext_id, citation, value in CELLS:
        ver, err = _resolve(conn, ext_id, citation)
        if err:
            print(f"  REFUSED {jur}/{attr}: {err}")
            refused += 1
            continue
        if ver is None:
            gaps += 1
        else:
            loaded += 1
        conn.execute(
            "INSERT INTO matrix_cells (jurisdiction, attribute, value, source_version, "
            "  source_citation, drafted_by, verified_by, verified_at) "
            "VALUES (?,?,?,?,?,?,NULL,NULL) "
            "ON CONFLICT(jurisdiction, attribute) DO UPDATE SET "
            "  value=excluded.value, source_version=excluded.source_version, "
            "  source_citation=excluded.source_citation, drafted_by=excluded.drafted_by "
            "WHERE matrix_cells.verified_by IS NULL",              # never clobber a verified cell
            (jur, attr, value, ver, citation, DRAFTED_BY))
    conn.commit()

    total = conn.execute("SELECT COUNT(*) FROM matrix_cells").fetchone()[0]
    verified = conn.execute("SELECT COUNT(*) FROM matrix_cells WHERE verified_by IS NOT NULL").fetchone()[0]
    print(f"seed: {loaded} grounded + {gaps} documented-gap loaded, {refused} refused")
    print(f"matrix_cells now: {total} total · {verified} verified · {total - verified} draft")
    conn.close()


if __name__ == "__main__":
    main()
