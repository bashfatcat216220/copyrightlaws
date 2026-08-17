"""Migration 003 — Wave C of the 2f/2g audit (2026-08-16): metadata relabels + honesty fixes.

Idempotent and re-runnable; apply IDENTICALLY to both corpus.db and corpus-demo.db. Metadata
only — NO law text is added, changed, or re-ingested (CLAUDE rule 7: CDPA carries point-in-time
versions + fired alerts; this migration never touches version content or sha256). Completeness
and label-honesty improve; authority does not — the tool stays a finding aid (prime rule 2).

What it does (each guarded + idempotent):
  1. Extends the provisions.status CHECK with 'reserved' (table rebuild — SQLite can't ALTER a
     CHECK). Skipped when already applied.
  2. source_edition relabels (2f audit, gated on Bing's confirmation):
       CA  Copyright Act (ca-c-42)            finding_aid → official
           — Justice Laws consolidations are official for evidentiary purposes since
             2009-06-01 (the site's own Important Note).
       AU  Copyright Act 1968 (au-copyright-1968) finding_aid → official
           — the Federal Register of Legislation is the authoritative register (Legislation
             Act 2003 (Cth) ss 15B/15ZA); corpus holds the current registered compilation.
       UK  CDPA 1988 (ukpga/1988/48)          finding_aid → consolidated
           — TNA's official revised edition: an official consolidation, not a mere finding
             aid (and not the as-enacted authentic text). METADATA-ONLY — no re-ingest.
     SG (sg-copyright-2021) is deliberately NOT relabeled: PENDING a manual check of the SSO
     authority statement (sso.agc.gov.sg 403s scripted fetch). IN (in-copyright-1957) stays
     finding_aid (Gazette of India controls); its caveat note lives in src/app.py
     INSTRUMENT_NOTES (the app's existing per-instrument note mechanism).
  3. 37 C.F.R. (us-37cfr-copyright): genuinely '[Reserved]' provisions (official bracket-note
     in the heading, empty body) get status='reserved' (was 'in_force' — overstated); the
     instrument title 'Parts 201–212' → 'Parts 200–235' (what Chapter II actually holds).
  4. UK CDPA has_unapplied_effects (the real bug, prime rule 3): the retained CLML snapshot
     (spike/artifacts/cdpa.xml) carries ukm:UnappliedEffects with RequiresApplied="true" —
     SI 2026/103 art. 4(1) affecting Pt. 2, and Tribunals, Courts and Enforcement Act 2007
     Sch. 23 Pt. 6 repealing Sch. 3 para. 17 (not yet in force). Every stored version read 0
     because ingest_clml never parsed that metadata. This step reuses the FIXED ingest's own
     resolver (src/store/ingest_clml._parse_unapplied_effects/_apply_unapplied_effects) as a
     TARGETED update on current versions only — identical scope to what a future re-ingest
     would produce, with no re-ingest.

    python db/migrations/003_wave_c.py --db db/corpus.db \
        [--cdpa-xml spike/artifacts/cdpa.xml]   # default; pass --skip-cdpa-effects to omit step 4
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "src" / "store"))

# (ext_id, expected_old, new, one-line rationale) — ext_id-guarded, never a bare row id.
RELABELS = [
    ("ca-c-42", "finding_aid", "official",
     "Justice Laws is official for evidentiary purposes since 2009-06-01"),
    ("au-copyright-1968", "finding_aid", "official",
     "Federal Register of Legislation is the authoritative register (Legislation Act 2003 ss 15B/15ZA)"),
    ("ukpga/1988/48", "finding_aid", "consolidated",
     "TNA official revised edition (metadata-only; CDPA is never re-ingested here)"),
]

CFR_TITLE_OLD = "37 C.F.R. — Copyright Office (Parts 201–212)"
CFR_TITLE_NEW = "37 C.F.R. — Copyright Office (Parts 200–235)"


def _extend_status_check(c: sqlite3.Connection) -> str:
    """Rebuild `provisions` with 'reserved' added to the status CHECK. Idempotent: skipped when
    the live DDL already allows it. Same forward-only rebuild pattern as migration 001's
    versions rebuild; provision ids are preserved (versions/case_treatment/provisions_fts all
    key on them), so nothing downstream moves."""
    ddl = c.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='provisions'"
                    ).fetchone()
    if ddl is None:
        raise SystemExit("target DB has no `provisions` table — apply migration 001 first")
    if "'reserved'" in ddl[0]:
        return "already-applied"
    c.executescript("""
      PRAGMA foreign_keys = OFF;
      BEGIN;
      -- this trigger (migration 001) references `provisions`; it must not exist while the
      -- table is mid-rebuild (the RENAME re-parses the schema) — recreated verbatim below.
      DROP TRIGGER IF EXISTS version_provision_same_instrument;
      CREATE TABLE provisions_new (
        id            INTEGER PRIMARY KEY,
        instrument_id INTEGER NOT NULL REFERENCES instruments(id),
        parent_id     INTEGER REFERENCES provisions(id),
        sort_int      INTEGER NOT NULL,
        sort_suffix   TEXT NOT NULL DEFAULT '' COLLATE BINARY,
        label         TEXT NOT NULL,
        heading       TEXT,
        kind          TEXT NOT NULL CHECK (kind IN
                        ('title','part','subpart','chapter','subchapter','section','subsection',
                         'paragraph','subparagraph','clause','subclause','item','subitem',
                         'article','schedule','schedule_para','recital')),
        role          TEXT NOT NULL DEFAULT 'enacting'
                        CHECK (role IN ('enacting','schedule','recital','quoted')),
        citation      TEXT NOT NULL,
        -- migration 003: + 'reserved' (a placeholder the source's editors hold open with the
        -- official bracket-note '[Reserved]' — not in-force text, not a repeal)
        status        TEXT NOT NULL DEFAULT 'in_force'
                        CHECK (status IN ('in_force','repealed','prospective','unknown','reserved')),
        UNIQUE (instrument_id, citation)
      );
      INSERT INTO provisions_new (id, instrument_id, parent_id, sort_int, sort_suffix, label,
                                  heading, kind, role, citation, status)
        SELECT id, instrument_id, parent_id, sort_int, sort_suffix, label,
               heading, kind, role, citation, status FROM provisions;
      DROP TABLE provisions;
      ALTER TABLE provisions_new RENAME TO provisions;
      CREATE INDEX idx_provisions_instrument ON provisions(instrument_id, sort_int, sort_suffix);
      CREATE INDEX idx_provisions_parent     ON provisions(parent_id);
      CREATE INDEX idx_provisions_role       ON provisions(instrument_id, role);
      -- recreate the migration-001 invariant trigger verbatim
      CREATE TRIGGER version_provision_same_instrument
      BEFORE INSERT ON versions
      WHEN NEW.provision_id IS NOT NULL
       AND (SELECT instrument_id FROM provisions WHERE id = NEW.provision_id) <> NEW.instrument_id
      BEGIN
        SELECT RAISE(ABORT, 'version.provision_id must belong to the same instrument');
      END;
      COMMIT;
      PRAGMA foreign_keys = ON;
    """)
    bad = c.execute("PRAGMA foreign_key_check").fetchall()
    if bad:
        raise SystemExit(f"foreign_key_check failed after provisions rebuild: {bad[:5]}")
    return "applied"


def _iid(c, ext_id):
    row = c.execute("SELECT id FROM instruments WHERE ext_id=?", (ext_id,)).fetchone()
    return row[0] if row else None


def migrate(db_path: str, cdpa_xml: str | None) -> None:
    c = sqlite3.connect(db_path)
    c.row_factory = sqlite3.Row
    print(f"== migration 003 (Wave C) on {db_path} ==")

    # 1 — status CHECK gains 'reserved'
    print(f"  [1] provisions.status CHECK + 'reserved': {_extend_status_check(c)}")

    # 2 — source_edition relabels (SG untouched by construction: not in RELABELS)
    for ext_id, old, new, why in RELABELS:
        row = c.execute("SELECT id, source_edition FROM instruments WHERE ext_id=?",
                        (ext_id,)).fetchone()
        if row is None:
            print(f"  [2] {ext_id}: NOT FOUND — skipped")
            continue
        if row["source_edition"] == new:
            print(f"  [2] {ext_id}: already '{new}'")
            continue
        if row["source_edition"] != old:
            raise SystemExit(f"{ext_id}: source_edition is '{row['source_edition']}', "
                             f"expected '{old}' — refusing to relabel blind")
        c.execute("UPDATE instruments SET source_edition=?, last_updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now') "
                  "WHERE id=?", (new, row["id"]))
        print(f"  [2] {ext_id}: {old} -> {new}  ({why})")

    # 3 — 37 C.F.R. reserved statuses + title
    cfr = _iid(c, "us-37cfr-copyright")
    if cfr:
        cur = c.execute(
            "UPDATE provisions SET status='reserved' WHERE instrument_id=? AND status='in_force' "
            "AND heading IS NOT NULL AND upper(heading) LIKE '%[RESERVED]%' "
            "AND NOT EXISTS (SELECT 1 FROM versions v WHERE v.provision_id=provisions.id "
            "                AND v.is_current=1 AND v.content IS NOT NULL AND v.content <> '')",
            (cfr,))
        print(f"  [3] 37 C.F.R.: {cur.rowcount} '[Reserved]' provisions -> status='reserved'")
        cur = c.execute("UPDATE instruments SET title=? WHERE id=? AND title=?",
                        (CFR_TITLE_NEW, cfr, CFR_TITLE_OLD))
        print(f"  [3] 37 C.F.R. title: {'updated to Parts 200–235' if cur.rowcount else 'already correct'}")

    # 4 — CDPA has_unapplied_effects, from the snapshot's own ukm metadata (no re-ingest)
    uk = _iid(c, "ukpga/1988/48")
    if uk and cdpa_xml:
        if not Path(cdpa_xml).exists():
            print(f"  [4] CDPA artifact not found at {cdpa_xml} — SKIPPED (flag not set); "
                  f"re-run with --cdpa-xml or let the next refresh re-ingest set it")
        else:
            import xml.etree.ElementTree as ET
            import ingest_clml
            root = ET.parse(cdpa_xml).getroot()
            effects = ingest_clml._parse_unapplied_effects(root)
            for e in effects:
                print(f"  [4] live RequiresApplied effect: {e['desc']} -> {e['paths']}")
            n = ingest_clml._apply_unapplied_effects(c, uk, effects)
            print(f"  [4] CDPA: has_unapplied_effects=1 on {n} current versions "
                  f"(historic versions untouched)")
    elif uk:
        print("  [4] CDPA effects step skipped (--skip-cdpa-effects)")

    c.commit()

    # verification (read-only) — printed so the run is its own review record
    print("  -- verify --")
    for ext_id in ("ca-c-42", "au-copyright-1968", "ukpga/1988/48", "sg-copyright-2021",
                   "in-copyright-1957", "us-37cfr-copyright"):
        r = c.execute("SELECT id, source_edition, title FROM instruments WHERE ext_id=?",
                      (ext_id,)).fetchone()
        if r:
            print(f"     {ext_id}: source_edition={r['source_edition']}")
    sg = c.execute("SELECT source_edition FROM instruments WHERE ext_id='sg-copyright-2021'").fetchone()
    assert sg is None or sg[0] == "finding_aid", "SG must stay finding_aid (pending manual check)"
    if cfr:
        n_res = c.execute("SELECT COUNT(*) FROM provisions WHERE instrument_id=? AND status='reserved'",
                          (cfr,)).fetchone()[0]
        print(f"     37 C.F.R.: {n_res} reserved provisions; title={c.execute('SELECT title FROM instruments WHERE id=?', (cfr,)).fetchone()[0]!r}")
    if uk:
        tot, flagged = c.execute("SELECT COUNT(*), SUM(has_unapplied_effects) FROM versions "
                                 "WHERE instrument_id=?", (uk,)).fetchone()
        print(f"     CDPA: {flagged or 0}/{tot} versions carry has_unapplied_effects=1")
    c.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Wave C metadata relabels + honesty fixes (migration 003).")
    ap.add_argument("--db", required=True)
    ap.add_argument("--cdpa-xml", default=str(REPO / "spike" / "artifacts" / "cdpa.xml"),
                    help="retained CLML snapshot for the ukm effects scope (default: spike/artifacts/cdpa.xml)")
    ap.add_argument("--skip-cdpa-effects", action="store_true")
    a = ap.parse_args()
    migrate(a.db, None if a.skip_cdpa_effects else a.cdpa_xml)
