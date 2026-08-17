"""004 — CDPA whole-provision repeal tombstones: fix 32 mislabeled `status='in_force'` rows.

legislation.gov.uk (CLML) prints a FULLY repealed/omitted provision as its number followed
by a dotted leader ("5 . . . . . ."), sometimes with `Status="Repealed"` stamped on the
element (Sch. ZA1 paras).  The original CDPA ingest never read either signal, so 32 current
provisions whose ENTIRE body is a pure dotted leader carry `status='in_force'`.

This is the SURGICAL fix for an EXISTING db (CLAUDE.md ingest rule 7 — CDPA is
point-in-time monitored, no full re-ingest):
  * flips `provisions.status` -> 'repealed' on exactly the whole-provision tombstones,
  * scope is CONFIRMED against the source artifact `spike/artifacts/cdpa.xml` (rule 9)
    by re-parsing it with the fixed detector in `src/store/ingest_clml.py`,
  * touches NOTHING else — no `content` / `content_sha256`, no version rows, no
    `is_current` — so the change monitor and the fired alerts are unaffected,
  * keeps the dotted-leader text VERBATIM (rule 2 / prime rule 1: the pre-repeal text is
    not in the source; never blank, never fabricate),
  * does NOT flip partially-omitted live provisions (embedded ". . ." runs inside real
    text, e.g. s.29, s.72) — the body test is a fullmatch on `number + dots only`,
  * idempotent: a re-run finds nothing to flip and exits 0.

Run:
    python db/migrations/004_cdpa_repealed_tombstones.py --db db/corpus.db
    python db/migrations/004_cdpa_repealed_tombstones.py --db db/corpus-demo.db
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import re
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
DEFAULT_XML = os.path.join(REPO, "spike", "artifacts", "cdpa.xml")

# Same body test as ingest_clml.DOTTED_TOMBSTONE: the WHOLE body is number + dotted leader.
DOTTED = re.compile(r"\s*\d+[A-Za-z]*\.?\s*(\.\s*){4,}\.?\s*")

# Live provisions with EMBEDDED dotted runs (a few omitted words inside real text) — must
# remain in_force; asserted after the update as the no-over-flag canary.
PARTIAL_CANARIES = ("CDPA 1988 s. 29", "CDPA 1988 s. 72")


def _load_ingest_parse():
    """Import parse() from the fixed ingest without triggering src.store package imports."""
    path = os.path.join(REPO, "src", "store", "ingest_clml.py")
    spec = importlib.util.spec_from_file_location("_ingest_clml_004", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def source_tombstone_citations(xml_path: str) -> set[str]:
    """Citations the SOURCE artifact marks fully repealed (Status attr / dotted body /
    empty stub with a keyed repeal notice), per the fixed detector in ingest_clml."""
    mod = _load_ingest_parse()
    parsed = mod.parse(xml_path)          # (title, records) pre-Wave-C, (title, records, effects) after
    records = parsed[1]
    return {r["citation"] for r in records if r.get("status") == "repealed"}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", required=True)
    ap.add_argument("--xml", default=DEFAULT_XML,
                    help="CDPA CLML source artifact (default: spike/artifacts/cdpa.xml)")
    a = ap.parse_args()
    if not os.path.exists(a.xml):
        raise SystemExit(f"source artifact not found: {a.xml} (rule 9 — cannot confirm scope)")

    src_repealed = source_tombstone_citations(a.xml)
    print(f"source artifact confirms {len(src_repealed)} fully-repealed CDPA provisions")

    conn = sqlite3.connect(a.db)
    conn.execute("PRAGMA foreign_keys = ON")
    iid_row = conn.execute(
        "SELECT id FROM instruments WHERE jurisdiction='GB' AND ext_id='ukpga/1988/48'").fetchone()
    if not iid_row:
        raise SystemExit("CDPA 1988 instrument not found in this DB")
    iid = iid_row[0]

    # invariance baselines (must be identical after — we only touch provisions.status)
    base = {
        "repealed": conn.execute(
            "SELECT COUNT(*) FROM provisions WHERE instrument_id=? AND status='repealed'", (iid,)).fetchone()[0],
        "provisions": conn.execute("SELECT COUNT(*) FROM provisions").fetchone()[0],
        "versions": conn.execute("SELECT COUNT(*) FROM versions").fetchone()[0],
        "alerts": conn.execute("SELECT COUNT(*) FROM alerts").fetchone()[0],
    }

    # candidates: CDPA provisions whose ENTIRE current body is a pure dotted leader,
    # not yet marked repealed.
    rows = conn.execute(
        "SELECT p.id, p.citation, v.content FROM provisions p "
        "JOIN versions v ON v.provision_id=p.id AND v.is_current=1 "
        "WHERE p.instrument_id=? AND p.status!='repealed'", (iid,)).fetchall()
    flips: list[tuple[int, str]] = []
    unconfirmed: list[str] = []
    for pid, cit, content in rows:
        if content and DOTTED.fullmatch(content):
            if cit in src_repealed:
                flips.append((pid, cit))
            else:
                unconfirmed.append(cit)          # dotted in DB but NOT in the source → refuse
    if unconfirmed:
        raise SystemExit(f"REFUSING: dotted bodies not confirmed by the source artifact: {unconfirmed}")

    # source says repealed, DB says in_force, but the DB body is NOT a pure tombstone —
    # would risk flipping a live partially-omitted provision. Report; never flip.
    flip_cits = {c for _, c in flips}
    skipped = sorted(c for c in src_repealed
                     if c not in flip_cits
                     and conn.execute("SELECT 1 FROM provisions WHERE instrument_id=? AND citation=? "
                                      "AND status!='repealed'", (iid, c)).fetchone())
    if skipped:
        print(f"NOTE: {len(skipped)} source-repealed citations left untouched "
              f"(DB body is not a whole-provision tombstone): {skipped}")

    for pid, _ in flips:
        conn.execute("UPDATE provisions SET status='repealed' WHERE id=?", (pid,))
    conn.commit()

    # ── verification block ─────────────────────────────────────────────────────
    after = {
        "repealed": conn.execute(
            "SELECT COUNT(*) FROM provisions WHERE instrument_id=? AND status='repealed'", (iid,)).fetchone()[0],
        "provisions": conn.execute("SELECT COUNT(*) FROM provisions").fetchone()[0],
        "versions": conn.execute("SELECT COUNT(*) FROM versions").fetchone()[0],
        "alerts": conn.execute("SELECT COUNT(*) FROM alerts").fetchone()[0],
    }
    print(f"flipped {len(flips)} provisions -> status='repealed' "
          f"(CDPA repealed {base['repealed']} -> {after['repealed']}):")
    for _, cit in sorted(flips, key=lambda t: t[1]):
        print(f"  {cit}")
    if not flips:
        print("  (none — already applied; no-op)")

    # 0 partials flagged: every flipped row had a pure-dotted body by construction; the
    # embedded-dots canaries must still read in_force.
    partials_flagged = 0
    for cit in PARTIAL_CANARIES:
        st = conn.execute("SELECT status FROM provisions WHERE instrument_id=? AND citation=?",
                          (iid, cit)).fetchone()
        assert st and st[0] == "in_force", f"over-flag: {cit} is {st}"
        print(f"  canary {cit}: status={st[0]} (live, embedded dots — untouched)")
    print(f"  partials flagged: {partials_flagged} (assertion passed)")
    assert after["provisions"] == base["provisions"], "provision count changed"
    assert after["versions"] == base["versions"], "version count changed"
    assert after["alerts"] == base["alerts"], "alert count changed"
    print(f"  invariants: provisions {after['provisions']}, versions {after['versions']}, "
          f"alerts {after['alerts']} — all unchanged (no version/sha/is_current writes)")
    conn.close()


if __name__ == "__main__":
    main()
