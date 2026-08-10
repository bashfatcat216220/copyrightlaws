"""Daily entrypoint — orchestrates connectors -> store -> monitor (the ai-law-portal shape).

STUB until Phase 0. When connectors land, this walks connectors.REGISTRY: for each,
discover(since) -> fetch(ref) -> store.store_version(...), then runs the change monitor and
a staleness report. Missing-credential connectors skip cleanly; one source's error never
stops the others.
"""
from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import db  # noqa: E402
import store  # noqa: E402
from connectors import REGISTRY  # noqa: E402


def main() -> None:
    conn = db.init_db()
    if not REGISTRY:
        print("no connectors registered yet — see src/connectors/ (Phase 0)")
        return
    for module_name, env_key in REGISTRY:
        if env_key and not os.environ.get(env_key):
            print(f"  {module_name:18} skipped: no credential ({env_key})")
            continue
        try:
            mod = importlib.import_module(f"connectors.{module_name}")
            new = 0
            for ref in mod.discover(None):
                fv = mod.fetch(ref)
                if fv is None:
                    continue
                if store.store_version(conn, fv)["outcome"] == "new":
                    new += 1
            print(f"  {module_name:18} {new} new/changed versions")
        except Exception as exc:  # one source's failure never stops the rest
            print(f"  {module_name:18} ERROR: {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    main()
