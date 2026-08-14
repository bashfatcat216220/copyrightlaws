"""Case-treatment ingest — real US opinions that cite a copyright section (CourtListener).

Populates the reader's Cases tab with GROUNDED case law: for a curated set of the most-cited
17 U.S.C. sections, it queries the Free Law Project's CourtListener API for opinions that cite
that section, and records each as a `case_treatment` row linked to the provision. Each cited
case is stored as an instrument (type='case') so it carries its own identity + provenance.

Honesty: CourtListener tells us a case CITES a section (a fact) — so treatment='cited'. We do
NOT assert editorial treatment (followed / distinguished / criticized): that is a Shepard's/
KeyCite-style judgment we can't source freely and must not originate. The stored `holding` is
the opinion EXCERPT CourtListener returns (real text), shown as citing context, not a headnote.

Run:  python src/store/ingest_cases.py --db db/corpus.db --allow-corpus [--per 5]
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

CL = "https://www.courtlistener.com"
UA = "copyright-corpus/1.0 (finding aid; contact via repo)"

# Most-litigated 17 U.S.C. sections — the Cases tab is worth most here.
CURATED = ["102", "103", "106", "106A", "107", "108", "109", "110", "115", "201",
           "203", "204", "301", "302", "411", "412", "501", "504", "505", "512", "1201", "1202"]


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _search(section: str, per: int) -> list[dict]:
    q = urllib.parse.quote(f'"17 U.S.C. {section}"')
    url = f"{CL}/api/rest/v4/search/?q={q}&type=o&order_by=score+desc"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for attempt in range(4):                               # back off on CourtListener rate limits
        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                d = json.load(resp)
            break
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 3:
                time.sleep(5 * (attempt + 1))
                continue
            raise
    out = []
    for r in (d.get("results") or [])[:per]:
        op = (r.get("opinions") or [{}])[0]
        snip = (op.get("snippet") or r.get("snippet") or "").strip()
        snip = " ".join(snip.split())[:600]
        cite = (r.get("citation") or [None])[0]
        out.append({
            "cluster_id": r.get("cluster_id") or r.get("id"),
            "name": r.get("caseName") or "(unreported)",
            "cite": cite, "year": (r.get("dateFiled") or "")[:4],
            "court": r.get("court"),
            "url": CL + r["absolute_url"] if r.get("absolute_url") else CL,
            "excerpt": snip,
        })
    return out


def _upsert_case(conn, c) -> int:
    ext = f"cl-{c['cluster_id']}"
    row = conn.execute("SELECT id FROM instruments WHERE jurisdiction='US' AND ext_id_scheme='COURTLISTENER' "
                       "AND ext_id=?", (ext,)).fetchone()
    if row:
        return row[0]
    cur = conn.execute(
        "INSERT INTO instruments (jurisdiction, type, title, official_citation, ext_id, "
        "ext_id_scheme, status, enacted_date, first_seen_at, last_updated_at) "
        "VALUES ('US','case',?,?,?,'COURTLISTENER','in_force',?,?,?)",
        (c["name"], c["cite"] or (c["court"] or "") + (" " + c["year"] if c["year"] else ""),
         ext, c["year"] or None, now_iso(), now_iso()))
    return cur.lastrowid


def ingest(db_path, per=5, allow_corpus=False) -> dict:
    if os.path.basename(db_path) == "corpus.db" and not allow_corpus:
        raise SystemExit("refusing to write the live corpus.db — pass --allow-corpus.")
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 15000")
    usc = conn.execute("SELECT id FROM instruments WHERE jurisdiction='US' AND ext_id='t17'").fetchone()
    if not usc:
        raise SystemExit("17 U.S.C. not loaded — ingest it first.")
    usc = usc[0]
    stats = {"sections": 0, "cases": 0, "links_new": 0, "links_existing": 0, "no_hits": 0}
    for section in CURATED:
        prov = conn.execute("SELECT id FROM provisions WHERE instrument_id=? AND citation=?",
                            (usc, f"17 U.S.C. § {section}")).fetchone()
        if not prov:
            continue
        pid = prov[0]
        stats["sections"] += 1
        try:
            hits = _search(section, per)
        except Exception as e:
            print(f"  § {section}: search failed — {type(e).__name__}: {e}")
            continue
        if not hits:
            stats["no_hits"] += 1
        for c in hits:
            cid = _upsert_case(conn, c)
            stats["cases"] += 1
            exists = conn.execute("SELECT 1 FROM case_treatment WHERE provision_id=? AND case_instrument=?",
                                  (pid, cid)).fetchone()
            if exists:
                stats["links_existing"] += 1
                continue
            conn.execute("INSERT INTO case_treatment (provision_id, case_instrument, treatment, "
                         "holding, source_url, retrieved_at) VALUES (?,?, 'cited', ?,?,?)",
                         (pid, cid, c["excerpt"] or None, c["url"], now_iso()))
            stats["links_new"] += 1
        conn.commit()
        time.sleep(0.6)                                    # be gentle to CourtListener
    conn.close()
    return stats


def main() -> None:
    ap = argparse.ArgumentParser(description="Ingest US case treatment for 17 U.S.C. (CourtListener).")
    ap.add_argument("--db", required=True)
    ap.add_argument("--per", type=int, default=5, help="cases per section")
    ap.add_argument("--allow-corpus", action="store_true")
    a = ap.parse_args()
    s = ingest(a.db, a.per, a.allow_corpus)
    print(f"cases: {s['sections']} sections queried · {s['cases']} case citations · "
          f"{s['links_new']} new links ({s['links_existing']} existing, {s['no_hits']} sections with no hits)")


if __name__ == "__main__":
    main()
