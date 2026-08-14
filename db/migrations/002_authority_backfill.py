"""Migration 002 backfill — set the legal-authority axis on every instrument.

Idempotent; run AFTER the ingests (the DBs rebuild from ingests, so authority must be
regenerable, not a one-off hand edit). Derives the per-instrument authority facts from
`type` + jurisdiction + the current version's authenticity/translation flags, plus a small
override map for the facts that aren't derivable (Title 17 positive-law status; the EU
directives re-based onto a consolidated edition).

    python db/migrations/002_authority_backfill.py --db db/corpus.db
"""
from __future__ import annotations

import argparse
import sqlite3

# Instruments re-based onto a consolidated (not-authentic) edition — see ingest_eu_consolidated.
_CONSOLIDATED = {"32001L0029", "32006L0116", "31996L0009"}


def backfill(db_path: str) -> None:
    c = sqlite3.connect(db_path)
    c.row_factory = sqlite3.Row
    cols = [r[1] for r in c.execute("PRAGMA table_info(instruments)")]
    if "authority" not in cols:                       # apply the ALTERs if migration 002 SQL hasn't run
        for col, decl in (("authority", "TEXT"), ("positive_law", "INTEGER"),
                          ("source_edition", "TEXT"), ("court_level", "TEXT")):
            c.execute(f"ALTER TABLE instruments ADD COLUMN {col} {decl}")
    n = 0
    for i in c.execute("SELECT id, jurisdiction, type, ext_id FROM instruments").fetchall():
        v = c.execute("SELECT is_official_language, is_consolidated, is_authentic FROM versions "
                      "WHERE instrument_id=? AND is_current=1 LIMIT 1", (i["id"],)).fetchone()
        offlang = v["is_official_language"] if v else None
        A = P = SE = CL = None
        t = i["type"]
        if t == "case":
            A, SE = "precedent", "official"
        elif t == "guidance":                          # copyright.gov IS the authentic Compendium — just not binding
            A, SE = "persuasive", "official"
        elif t == "regulation":                        # 37 C.F.R. — legislative rules (force of law); eCFR ≠ official edition
            A, SE = "binding", "finding_aid"
        elif t == "treaty":
            A, SE = "binding", "official"
        elif t == "directive":
            A = "binding"
            SE = "consolidated" if i["ext_id"] in _CONSOLIDATED else "original_act"
        elif t == "statute":
            A = "binding"
            if i["jurisdiction"] == "US" and i["ext_id"] == "t17":
                P, SE = 1, "finding_aid"               # enacted positive law → Code text = legal evidence
            else:
                SE = "translation" if offlang == 0 else "finding_aid"
        c.execute("UPDATE instruments SET authority=?, positive_law=?, source_edition=?, court_level=? "
                  "WHERE id=?", (A, P, SE, CL, i["id"]))
        n += 1
    c.commit()
    c.close()
    print(f"{db_path}: authority axis set on {n} instruments")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Backfill the legal-authority axis (migration 002).")
    ap.add_argument("--db", required=True)
    backfill(ap.parse_args().db)
