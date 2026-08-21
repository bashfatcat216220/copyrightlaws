"""009 — Dedupe duplicate case instruments (same opinion, multiple CourtListener clusters).

`ingest_cases.py` keys a case instrument on its CourtListener `cluster_id` (`ext_id='cl-<n>'`).
CourtListener sometimes carries the SAME opinion under more than one cluster, so the same case was
minted as several `instruments` rows (e.g. *Gamma v. Ean-Chea* ids 40/41, *American Geophysical*
60 F.3d 913 ids 59/61, *Forward v. Thorogood* 70/72, *Mometrix* 103/104). In the reader's case rail
this reads as duplicate, un-authoritative rows.

This is a SURGICAL cleanup of an existing DB — metadata only, no re-fetch:
  * merge key = (title, official_citation) BOTH non-null. Conservative: it merges true duplicate
    opinions but NEVER collapses distinct cases that only share a court+year fallback pseudo-cite
    (verified: "Court of Appeals for the First Circuit 1998" is three DIFFERENT cases — different
    titles — so they never group together),
  * for each dup group keep the lowest `id` as canonical: repoint `case_treatment.case_instrument`
    to it, drop any now-identical (provision_id, case_instrument) links, then DELETE the redundant
    `instruments` rows,
  * touches only `case_treatment` + the redundant case `instruments` rows — no versions, no
    provisions, no alerts, no statutory law,
  * idempotent: a re-run finds no dup groups and makes no change.

Validate on a sqlite-backup CLONE first (CLAUDE.md rule 9), then apply to BOTH DBs:
    python db/migrations/009_dedupe_cases.py --db db/corpus.db
    python db/migrations/009_dedupe_cases.py --db db/corpus-demo.db
"""
from __future__ import annotations

import argparse
import sqlite3


def _merge_key(title: str, cite: str):
    """A real reporter/neutral citation ('60 F.3d 913') uniquely identifies an opinion, so key on
    the cite ALONE — this catches the same opinion minted under slightly different party-string
    titles. A court+year FALLBACK pseudo-cite ('Court of Appeals for the First Circuit 1998') is
    NOT an identifier, so require the title too — distinct same-court/year cases then never merge."""
    if cite and cite.strip()[:1].isdigit():
        return ("cite", cite.strip())
    return ("titlecite", title, cite)


def _dup_groups(conn) -> list[tuple[str, str, list[int]]]:
    """(title, official_citation, [ids sorted]) for each duplicate case group, grouped by
    _merge_key. official_citation must be non-null so a null-cite pair is never merged."""
    groups: dict = {}
    for cid, title, cite in conn.execute(
            "SELECT id, title, official_citation FROM instruments "
            "WHERE type='case' AND official_citation IS NOT NULL ORDER BY id"):
        groups.setdefault(_merge_key(title, cite), []).append((cid, title, cite))
    out = []
    for members in groups.values():
        if len(members) > 1:
            idlist = sorted(m[0] for m in members)
            out.append((members[0][1], members[0][2], idlist))     # representative title/cite
    return out


def _snapshot(conn) -> dict:
    return {
        "cases": conn.execute("SELECT COUNT(*) FROM instruments WHERE type='case'").fetchone()[0],
        "treatments": conn.execute("SELECT COUNT(*) FROM case_treatment").fetchone()[0],
        "distinct_links": conn.execute(
            "SELECT COUNT(*) FROM (SELECT DISTINCT provision_id, case_instrument FROM case_treatment)"
        ).fetchone()[0],
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
    groups = _dup_groups(conn)
    merged_ids: list[int] = []
    for title, cite, ids in groups:
        canonical, dups = ids[0], ids[1:]
        for dup in dups:
            conn.execute("UPDATE case_treatment SET case_instrument=? WHERE case_instrument=?",
                         (canonical, dup))
            merged_ids.append(dup)
    # a repoint can create identical (provision_id, case_instrument) rows — keep the lowest id each
    conn.execute(
        "DELETE FROM case_treatment WHERE id NOT IN "
        "(SELECT MIN(id) FROM case_treatment GROUP BY provision_id, case_instrument)")
    # now the redundant case instruments are unreferenced — remove them (FK ON guards against any
    # stray reference; cases carry no versions/amendments/matrix rows)
    for dup in merged_ids:
        conn.execute("DELETE FROM instruments WHERE id=? AND type='case'", (dup,))
    conn.commit()

    after = _snapshot(conn)
    orphans = conn.execute(
        "SELECT COUNT(*) FROM case_treatment ct "
        "LEFT JOIN instruments i ON i.id=ct.case_instrument WHERE i.id IS NULL").fetchone()[0]
    fk_ok = not conn.execute("PRAGMA foreign_key_check").fetchall()
    integ = conn.execute("PRAGMA integrity_check").fetchone()[0]

    print(f"dup groups: {len(groups)} · redundant case rows merged: {len(merged_ids)}")
    for title, cite, ids in groups:
        print(f"  keep {ids[0]:>3}  drop {ids[1:]}  {cite}  ·  {title[:44]}")
    print(f"case instruments: {before['cases']} -> {after['cases']}")
    print(f"case_treatment rows: {before['treatments']} -> {after['treatments']}  "
          f"(distinct links {before['distinct_links']} -> {after['distinct_links']})")
    print(f"invariant (provisions/versions/alerts unchanged): "
          f"{before['provisions']==after['provisions']} / "
          f"{before['versions']==after['versions']} / {before['alerts']==after['alerts']}")
    print(f"orphaned case_treatment rows: {orphans}  ·  foreign_key_check ok: {fk_ok}  ·  "
          f"integrity_check: {integ}")
    conn.close()


if __name__ == "__main__":
    main()
