"""Auto-refresh — re-fetch monitored sources, re-ingest, and fire change alerts.

The connector half of change-monitoring. For each registered source it downloads the current
official text to the same retained artifact the ingest reads, re-runs that ingest (versioning
is idempotent BY CONTENT, so only genuinely-changed provisions get a new version), and then
runs `monitor.run` to write alerts + redlines. Designed to be run on a schedule (cron).

Only stable, directly-fetchable sources are auto-refreshed here; sources behind signed URLs /
PDFs / proxies (WIPO PDFs, national portals) need a per-source fetcher and are added over time.

Run:  python src/monitor/refresh.py --db db/corpus.db [--only <name>]
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import urllib.request
import zipfile
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
PY = sys.executable
ART = os.path.join(REPO, "spike", "artifacts")
UA = "Mozilla/5.0 (copyright-corpus change monitor)"

# Registry of auto-refreshable sources (stable, direct-fetch). name → how to pull + ingest.
SOURCES = [
    {"name": "GB CDPA 1988",
     "url": "https://www.legislation.gov.uk/ukpga/1988/48/data.xml",
     "artifact": "cdpa.xml", "ingest": "ingest_clml.py", "flag": "--xml"},
    # US 17 U.S.C. ships as a release-point ZIP → unzip usc17.xml before ingest.
    {"name": "US 17 U.S.C.",
     "url": "https://uscode.house.gov/download/releasepoints/us/pl/119/102/xml_usc17@119-102.zip",
     "artifact": "usc17.xml", "ingest": "ingest_uslm.py", "flag": "--xml",
     "unzip_member": "usc17.xml"},
]


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _fetch(url: str, dest: str, unzip_member: str | None = None) -> int:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=90) as resp:
        data = resp.read()
    if unzip_member:
        tmp = dest + ".zip"
        open(tmp, "wb").write(data)
        with zipfile.ZipFile(tmp) as z:
            member = next((n for n in z.namelist() if n.endswith(unzip_member)), None)
            if not member:
                raise RuntimeError(f"{unzip_member} not in zip")
            open(dest, "wb").write(z.read(member))
        os.remove(tmp)
    else:
        open(dest, "wb").write(data)
    return os.path.getsize(dest)


def refresh(db_path: str, only: str | None = None) -> dict:
    import importlib.util
    spec = importlib.util.spec_from_file_location("mon", os.path.join(HERE, "monitor.py"))
    mon = importlib.util.module_from_spec(spec); spec.loader.exec_module(mon)

    pit = _today()
    log = [f"[{datetime.now(timezone.utc).isoformat()}] refresh start (pit={pit})"]
    fetched = 0
    for s in SOURCES:
        if only and only.lower() not in s["name"].lower():
            continue
        dest = os.path.join(ART, s["artifact"])
        try:
            n = _fetch(s["url"], dest, s.get("unzip_member"))
            r = subprocess.run(
                [PY, os.path.join(REPO, "src", "store", s["ingest"]), "--db", db_path,
                 "--allow-corpus", s["flag"], dest, "--source-url", s["url"],
                 "--point-in-time", pit], capture_output=True, text=True, cwd=REPO)
            tail = (r.stdout.strip().splitlines() or [r.stderr.strip()[-200:]])[-1]
            log.append(f"  {s['name']}: fetched {n} bytes → {tail}")
            fetched += 1
        except Exception as e:                             # a source being down must not sink the run
            log.append(f"  {s['name']}: FETCH/INGEST FAILED — {type(e).__name__}: {e}")

    t = mon.run(db_path)
    log.append(f"  monitor: {t['alerts_new']} new alerts across {t['instruments']} instrument(s) "
               f"({t['provisions_changed']} provisions changed, {t['alerts_existing']} already recorded)")
    os.makedirs(os.path.join(REPO, "logs"), exist_ok=True)
    with open(os.path.join(REPO, "logs", "refresh.log"), "a") as f:
        f.write("\n".join(log) + "\n")
    return {"fetched": fetched, "alerts_new": t["alerts_new"], "log": log}


def main() -> None:
    ap = argparse.ArgumentParser(description="Auto-refresh monitored sources and fire alerts.")
    ap.add_argument("--db", required=True)
    ap.add_argument("--only", default=None, help="refresh only sources whose name contains this")
    a = ap.parse_args()
    r = refresh(a.db, a.only)
    print("\n".join(r["log"]))


if __name__ == "__main__":
    main()
