"""Copyright Corpus — web shell (FastAPI + Jinja2 + HTMX).

Reads ONLY from the DB. Every page renders the standing finding-aid caveat and, on any
instrument/version, its source_url + retrieved_at (the two fields that matter most — the
tool is a finding aid, never a citation). Works empty (no data yet) with honest empty-states.
"""
from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

sys.path.insert(0, str(Path(__file__).resolve().parent))
import db  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(REPO_ROOT / "templates"))

CAVEAT = ("Internal research aid. Not verified for currency. Confirm against the official "
          "source before relying on it in client work.")

app = FastAPI(title="Copyright Corpus")


@app.on_event("startup")
def _startup() -> None:
    db.init_db()  # idempotent; makes an empty but valid DB on first boot


def _conn() -> sqlite3.Connection:
    return db.connect()


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    conn = _conn()
    tiers = {}
    for r in conn.execute(
        "SELECT j.tier, j.code, j.name, "
        "  (SELECT COUNT(*) FROM instruments i WHERE i.jurisdiction=j.code) AS n "
        "FROM jurisdictions j ORDER BY j.tier, j.name"):
        tiers.setdefault(r["tier"], []).append(dict(r))
    stats = {
        "instruments": conn.execute("SELECT COUNT(*) FROM instruments").fetchone()[0],
        "versions": conn.execute("SELECT COUNT(*) FROM versions").fetchone()[0],
        "jurisdictions": conn.execute("SELECT COUNT(*) FROM jurisdictions").fetchone()[0],
    }
    return templates.TemplateResponse(request, "index.html",
                                      {"tiers": tiers, "stats": stats, "caveat": CAVEAT})


@app.get("/search", response_class=HTMLResponse)
def search(request: Request, q: str = ""):
    conn = _conn()
    results = []
    if q.strip():
        toks = " ".join(t for t in "".join(c if c.isalnum() else " " for c in q).split())
        if toks:
            results = [dict(r) for r in conn.execute(
                "SELECT v.id, v.instrument_id, i.title, i.official_citation, i.jurisdiction, "
                "  snippet(versions_fts, 2, '[', ']', '…', 12) AS snip "
                "FROM versions_fts f JOIN versions v ON v.id=f.rowid "
                "JOIN instruments i ON i.id=v.instrument_id "
                "WHERE versions_fts MATCH ? ORDER BY rank LIMIT 50", (toks,)).fetchall()]
    return templates.TemplateResponse(request, "search.html",
                                      {"q": q, "results": results, "caveat": CAVEAT})


@app.get("/instrument/{iid}", response_class=HTMLResponse)
def instrument(request: Request, iid: int):
    conn = _conn()
    inst = conn.execute("SELECT * FROM instruments WHERE id=?", (iid,)).fetchone()
    ver = conn.execute("SELECT * FROM versions WHERE instrument_id=? AND is_current=1 "
                       "ORDER BY point_in_time DESC LIMIT 1", (iid,)).fetchone()
    versions = [dict(r) for r in conn.execute(
        "SELECT id, point_in_time, retrieved_at, is_authentic, is_official_language "
        "FROM versions WHERE instrument_id=? ORDER BY point_in_time DESC", (iid,))]
    return templates.TemplateResponse(request, "instrument.html",
                                      {"inst": dict(inst) if inst else None,
                                       "ver": dict(ver) if ver else None,
                                       "versions": versions, "caveat": CAVEAT})
