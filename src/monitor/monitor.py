"""Change monitor — detect per-provision text changes and fire alerts with a redline.

The versioning already does the hard part: when a re-fetch brings changed text, the store
inserts a NEW version for that provision (is_current=1) and demotes the prior one. This module
reads that history — for each provision whose current version differs from its immediately
prior version, it writes an `alerts` row (old_version → new_version) with a word-level redline
summary. Idempotent: an alert for a given (old_version, new_version) pair is written once.

No fake law: it only compares text already fetched + stored; it never originates anything.

Run:  python src/monitor/monitor.py --db <db> [--instrument <id>]   (default: all instruments)
"""
from __future__ import annotations

import argparse
import difflib
import sqlite3
from datetime import datetime, timezone


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def redline(old: str, new: str, maxlen: int = 600) -> tuple[str, float]:
    """Word-level redline: '− removed  + added' spans, plus a change ratio (0..1)."""
    ow, nw = (old or "").split(), (new or "").split()
    sm = difflib.SequenceMatcher(None, ow, nw)
    spans: list[str] = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        if tag in ("replace", "delete") and i2 > i1:
            spans.append("− " + " ".join(ow[i1:i2]))
        if tag in ("replace", "insert") and j2 > j1:
            spans.append("+ " + " ".join(nw[j1:j2]))
    s = "   ".join(spans)
    if len(s) > maxlen:
        s = s[:maxlen].rsplit(" ", 1)[0] + " …"
    return s, round(1 - sm.ratio(), 3)


def _versions(conn, iid):
    """provision_id -> [versions oldest→newest] (only provision-scoped, text-bearing)."""
    out: dict = {}
    for r in conn.execute(
        "SELECT provision_id, id, content, content_sha256, retrieved_at, point_in_time, is_current "
        "FROM versions WHERE instrument_id=? AND provision_id IS NOT NULL AND content IS NOT NULL "
        "ORDER BY provision_id, retrieved_at, id", (iid,)):
        out.setdefault(r["provision_id"], []).append(dict(r))
    return out


def detect_and_alert(conn, iid) -> dict:
    """For each provision with a changed current version vs its prior, write an alert."""
    stats = {"provisions_changed": 0, "alerts_new": 0, "alerts_existing": 0}
    for pid, vers in _versions(conn, iid).items():
        if len(vers) < 2:
            continue
        cur = next((v for v in reversed(vers) if v["is_current"]), vers[-1])
        prior = [v for v in vers if v["id"] != cur["id"]]
        if not prior:
            continue
        prev = prior[-1]                                   # immediately-prior version
        if prev["content_sha256"] == cur["content_sha256"]:
            continue
        stats["provisions_changed"] += 1
        exists = conn.execute("SELECT 1 FROM alerts WHERE old_version=? AND new_version=?",
                              (prev["id"], cur["id"])).fetchone()
        if exists:
            stats["alerts_existing"] += 1
            continue
        summary, ratio = redline(prev["content"], cur["content"])
        pit = cur.get("point_in_time")
        rule = f"content-change · {int(ratio*100)}% · {prev['retrieved_at'][:10]}→{cur['retrieved_at'][:10]}"
        conn.execute("INSERT INTO alerts (rule, instrument_id, old_version, new_version, summary, "
                     "notified_at) VALUES (?,?,?,?,?,?)",
                     (rule, iid, prev["id"], cur["id"], summary, now_iso()))
        stats["alerts_new"] += 1
    conn.commit()
    return stats


def run(db_path, instrument_id=None) -> dict:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    ids = ([instrument_id] if instrument_id else
           [r[0] for r in conn.execute("SELECT id FROM instruments ORDER BY id")])
    total = {"instruments": 0, "provisions_changed": 0, "alerts_new": 0, "alerts_existing": 0}
    for iid in ids:
        s = detect_and_alert(conn, iid)
        if s["provisions_changed"]:
            total["instruments"] += 1
        for k in ("provisions_changed", "alerts_new", "alerts_existing"):
            total[k] += s[k]
    conn.close()
    return total


def main() -> None:
    ap = argparse.ArgumentParser(description="Change monitor — fire alerts on per-provision text changes.")
    ap.add_argument("--db", required=True)
    ap.add_argument("--instrument", type=int, default=None)
    a = ap.parse_args()
    t = run(a.db, a.instrument)
    print(f"monitor: {t['instruments']} instrument(s) changed · {t['provisions_changed']} provisions "
          f"· {t['alerts_new']} new alerts ({t['alerts_existing']} already recorded)")


if __name__ == "__main__":
    main()
