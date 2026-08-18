"""006 — CDPA sub-paragraphs repealed IN PLACE: record them as sub-item metadata.

A sub-paragraph repealed in place (s.205B(1)(cc), s.9(2)(c), Sch. 2 para. 3A, …) prints in
legislation.gov.uk's consolidated text as a dotted leader after its label ("cc . . . ."),
while the actual repeal notice is keyed to the sub-item's <CommentaryRef>
("S. 205B(1)(cc) repealed (31.7.2017) by Digital Economy Act 2017 …"). The original ingest
kept the dots but dropped that note, so ~70 sub-items across ~50 sections rendered as bare
dot-runs in an otherwise in-force section, with no citation or date.

This is the SURGICAL fix for an EXISTING db (CLAUDE.md ingest rule 7 — CDPA is point-in-time
monitored, no full re-ingest). It is METADATA-ONLY, exactly like migration 004:
  * sets `provisions.status='repealed'` on the repealed-in-place SUB-ITEM rows, and stores
    the source's own repeal notice in the sub-item's `heading` (a non-versioned column the
    reader splices in where the dots are — `_annotate_repealed_subitems`),
  * touches NOTHING versioned — no `content`, no `content_sha256`, no version rows, no
    `is_current` — so the change monitor and the 91 fired alerts are unaffected (the section
    body keeps the source's VERBATIM dots; prime rule 1: never blank / never fabricate),
  * scope + notice text are taken from the SOURCE artifact `spike/artifacts/cdpa.xml` (rule 9)
    by re-parsing it with the fixed detector in `src/store/ingest_clml.py`,
  * 2 sub-items whose source keys no repeal notice (Sch. 4 para. 37(1)/48(1)) get status only
    (heading stays NULL) — the reader leaves their verbatim dots as-is,
  * idempotent: a re-run finds the rows already set and makes no change.

Run:
    python db/migrations/006_cdpa_subitem_repeals.py --db db/corpus.db
    python db/migrations/006_cdpa_subitem_repeals.py --db db/corpus-demo.db
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import sqlite3

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
DEFAULT_XML = os.path.join(REPO, "spike", "artifacts", "cdpa.xml")

SUBITEM_KINDS = ("subsection", "paragraph", "subparagraph", "clause", "subclause")


def _load_ingest():
    path = os.path.join(REPO, "src", "store", "ingest_clml.py")
    spec = importlib.util.spec_from_file_location("_ingest_clml_006", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def source_subitem_repeals(xml_path: str) -> dict[str, str | None]:
    """citation -> repeal notice (or None) for every sub-item the SOURCE marks repealed
    in place, per the fixed detector in ingest_clml."""
    mod = _load_ingest()
    _title, records, *_ = mod.parse(xml_path)
    return {r["citation"]: r.get("heading") for r in records
            if r.get("status") == "repealed" and r["kind"] in SUBITEM_KINDS}


def _snapshot(conn, iid):
    """Invariants that MUST be identical after (we only write provisions.status/heading)."""
    return {
        "provisions": conn.execute("SELECT COUNT(*) FROM provisions").fetchone()[0],
        "versions": conn.execute("SELECT COUNT(*) FROM versions").fetchone()[0],
        "alerts": conn.execute("SELECT COUNT(*) FROM alerts").fetchone()[0],
        # a fingerprint of ALL current CDPA version text — proves no content/sha write
        "sha_fingerprint": conn.execute(
            "SELECT COUNT(*), COALESCE(GROUP_CONCAT(content_sha256),'') FROM versions "
            "WHERE instrument_id=? AND is_current=1", (iid,)).fetchone(),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", required=True)
    ap.add_argument("--xml", default=DEFAULT_XML)
    a = ap.parse_args()
    if not os.path.exists(a.xml):
        raise SystemExit(f"source artifact not found: {a.xml} (rule 9 — cannot confirm scope)")

    src = source_subitem_repeals(a.xml)
    n_note = sum(1 for v in src.values() if v)
    print(f"source artifact: {len(src)} repealed-in-place sub-items ({n_note} with a notice, "
          f"{len(src) - n_note} verbatim-dots only)")

    conn = sqlite3.connect(a.db)
    conn.execute("PRAGMA foreign_keys = ON")
    iid = conn.execute(
        "SELECT id FROM instruments WHERE jurisdiction='GB' AND ext_id='ukpga/1988/48'").fetchone()
    if not iid:
        raise SystemExit("CDPA 1988 instrument not found in this DB")
    iid = iid[0]

    before = _snapshot(conn, iid)
    base_repealed = conn.execute(
        "SELECT COUNT(*) FROM provisions WHERE instrument_id=? AND status='repealed'", (iid,)).fetchone()[0]

    changed, missing = 0, []
    for cit, note in sorted(src.items()):
        row = conn.execute(
            "SELECT id, status, heading FROM provisions WHERE instrument_id=? AND citation=?",
            (iid, cit)).fetchone()
        if not row:
            missing.append(cit)
            continue
        pid, status, heading = row
        if status == "repealed" and (heading or None) == (note or None):
            continue                                       # already applied — idempotent
        conn.execute("UPDATE provisions SET status='repealed', heading=? WHERE id=?", (note, pid))
        changed += 1
    conn.commit()

    if missing:
        print(f"NOTE: {len(missing)} source sub-items not found in this DB (citation drift?): {missing}")

    after = _snapshot(conn, iid)
    now_repealed = conn.execute(
        "SELECT COUNT(*) FROM provisions WHERE instrument_id=? AND status='repealed'", (iid,)).fetchone()[0]
    print(f"updated {changed} sub-item rows -> status='repealed' (+ notice in heading)")
    print(f"CDPA repealed provisions: {base_repealed} -> {now_repealed}")

    # ── invariants: metadata-only, monitor untouched ──────────────────────────
    assert after["provisions"] == before["provisions"], "provision count changed"
    assert after["versions"] == before["versions"], "version count changed"
    assert after["alerts"] == before["alerts"], "alert count changed"
    assert after["sha_fingerprint"] == before["sha_fingerprint"], \
        "CDPA current-version text/sha changed — NOT metadata-only!"
    print(f"  invariants: provisions {after['provisions']}, versions {after['versions']}, "
          f"alerts {after['alerts']} unchanged; CDPA current-version SHAs byte-identical "
          f"(no content/version/is_current write)")

    # spot-check the flagship
    cc = conn.execute(
        "SELECT status, heading FROM provisions WHERE instrument_id=? AND citation=?",
        (iid, "CDPA 1988 s. 205B(1)(cc)")).fetchone()
    if cc:
        print(f"  s.205B(1)(cc): status={cc[0]}, note={cc[1]!r}")
    conn.close()


if __name__ == "__main__":
    main()
