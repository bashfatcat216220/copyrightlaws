"""Copyright Corpus — web shell (FastAPI + Jinja2 + HTMX).

Reads ONLY from the DB. Every page renders the standing finding-aid caveat and, on any
instrument/version, its source_url + retrieved_at (the two fields that matter most — the
tool is a finding aid, never a citation). Works empty (no data yet) with honest empty-states.
Styling = the Article One design system (navy accent, ink-black surfaces, Caslon/Source
Serif/Franklin/Plex Mono) in a legal-research-terminal layout (rail + citation gutter).
"""
from __future__ import annotations

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

app = FastAPI(title="Copyright Corpus")


@app.on_event("startup")
def _startup() -> None:
    db.init_db()  # idempotent; an empty but valid DB on first boot


def _conn() -> sqlite3.Connection:
    return db.connect()


def _rail(conn: sqlite3.Connection) -> dict:
    """Jurisdiction rail: tier -> [{code,name,n}] with live instrument counts."""
    tiers: dict = {}
    for r in conn.execute(
        "SELECT j.tier, j.code, j.name, "
        "  (SELECT COUNT(*) FROM instruments i WHERE i.jurisdiction=j.code) AS n "
        "FROM jurisdictions j ORDER BY j.tier, j.name"):
        tiers.setdefault(r["tier"], []).append(dict(r))
    return tiers


def _counts(conn: sqlite3.Connection) -> dict:
    """Live corpus counts for the breadcrumb bar (honest, computed — never hardcoded)."""
    return {
        "jurisdictions": conn.execute("SELECT COUNT(*) FROM jurisdictions").fetchone()[0],
        "instruments": conn.execute("SELECT COUNT(*) FROM instruments").fetchone()[0],
        "versions": conn.execute("SELECT COUNT(*) FROM versions").fetchone()[0],
    }


def _ctx(conn, active_jur=None, active_nav=None, **extra) -> dict:
    return {"jurs": _rail(conn), "active_jur": active_jur, "active_nav": active_nav,
            "counts": _counts(conn), **extra}


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    conn = _conn()
    stats = {
        "instruments": conn.execute("SELECT COUNT(*) FROM instruments").fetchone()[0],
        "versions": conn.execute("SELECT COUNT(*) FROM versions").fetchone()[0],
        "jurisdictions": conn.execute("SELECT COUNT(*) FROM jurisdictions").fetchone()[0],
    }
    recent = [dict(r) for r in conn.execute(
        "SELECT id, title, official_citation, jurisdiction FROM instruments "
        "ORDER BY last_updated_at DESC LIMIT 12")]
    return templates.TemplateResponse(request, "index.html",
                                      _ctx(conn, active_nav="browse", stats=stats, recent=recent))


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
                                      _ctx(conn, active_nav="search", q=q, results=results))


@app.get("/jurisdiction/{code}", response_class=HTMLResponse)
def jurisdiction(request: Request, code: str):
    conn = _conn()
    j = conn.execute("SELECT * FROM jurisdictions WHERE code=?", (code,)).fetchone()
    insts = [dict(r) for r in conn.execute(
        "SELECT id, title, official_citation, type, status FROM instruments "
        "WHERE jurisdiction=? ORDER BY type, title", (code,))]
    return templates.TemplateResponse(request, "jurisdiction.html",
                                      _ctx(conn, active_jur=code, j=dict(j) if j else None, insts=insts))


def _has_provisions(conn) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='provisions'"
                        ).fetchone() is not None


def _section_reader(conn, iid, sec):
    """Provisions-aware view: chapter-grouped section rail + the selected section's text.
    Returns (rail, sel) or (None, None) if this instrument has no provisions loaded."""
    # Leaf kinds that rail as the reader's "sections": US/UK sections, UK schedule
    # paragraphs, and EU articles (InfoSoc). Source-derived kinds, never a jurisdiction
    # switch — the reader renders provision.label as stored ('§ 203' / 's. 12' / 'Article 5').
    LEAVES = "('section','article','schedule_para','recital')"
    n = conn.execute("SELECT COUNT(*) FROM provisions WHERE instrument_id=? "
                     f"AND kind IN {LEAVES}", (iid,)).fetchone()[0]
    if not n:
        return None, None
    rows = [dict(r) for r in conn.execute(
        "SELECT s.id, s.label, s.heading, s.citation, s.kind, "
        "  c.label AS chap_label, c.sort_int AS c_si, c.sort_suffix AS c_su "
        "FROM provisions s LEFT JOIN provisions c ON c.id=s.parent_id "
        f"WHERE s.instrument_id=? AND s.kind IN {LEAVES} "
        "ORDER BY c.sort_int, c.sort_suffix COLLATE BINARY, "
        "         s.sort_int, s.sort_suffix COLLATE BINARY", (iid,))]
    # Recitals (kind='recital') are top-level (no chapter) and precede the articles — rail
    # them as their own group rather than under the null-chapter "Sections" bucket.
    for r in rows:
        if r["kind"] == "recital":
            r["chap_label"] = "Recitals"
    sel_id = sec if sec is not None else rows[0]["id"]
    # group into the left rail by chapter, marking the active section
    rail, cur = [], None
    for r in rows:
        r["active"] = (r["id"] == sel_id)
        if cur is None or cur["chap_label"] != r["chap_label"]:
            cur = {"chap_label": r["chap_label"], "sections": []}
            rail.append(cur)
        cur["sections"].append(r)
    sel = conn.execute(
        "SELECT p.id, p.label, p.heading, p.citation, p.status, v.content, v.source_url, v.retrieved_at "
        "FROM provisions p LEFT JOIN versions v ON v.provision_id=p.id AND v.is_current=1 "
        "WHERE p.id=?", (sel_id,)).fetchone()
    return rail, (dict(sel) if sel else None)


@app.get("/instrument/{iid}", response_class=HTMLResponse)
def instrument(request: Request, iid: int, tab: str = "cases", sec: int | None = None):
    conn = _conn()
    inst = conn.execute("SELECT * FROM instruments WHERE id=?", (iid,)).fetchone()
    ver = conn.execute("SELECT * FROM versions WHERE instrument_id=? AND is_current=1 "
                       "AND provision_id IS NULL ORDER BY point_in_time DESC LIMIT 1"
                       if _has_provisions(conn) else
                       "SELECT * FROM versions WHERE instrument_id=? AND is_current=1 "
                       "ORDER BY point_in_time DESC LIMIT 1", (iid,)).fetchone()
    versions = [dict(r) for r in conn.execute(
        "SELECT id, point_in_time, retrieved_at, is_authentic, is_official_language "
        "FROM versions WHERE instrument_id=? AND provision_id IS NULL "
        "ORDER BY point_in_time DESC" if _has_provisions(conn) else
        "SELECT id, point_in_time, retrieved_at, is_authentic, is_official_language "
        "FROM versions WHERE instrument_id=? ORDER BY point_in_time DESC", (iid,))]
    # Provision-aware section reader (only when provisions are loaded for this instrument).
    rail, sel = (_section_reader(conn, iid, sec) if inst and _has_provisions(conn) else (None, None))
    # History tab: amendments TO this instrument, with the amending instrument's cite/title.
    amendments = [dict(r) for r in conn.execute(
        "SELECT a.effective_date, a.effect, a.sections_affected, "
        "  ai.official_citation AS amending_citation, ai.title AS amending_title "
        "FROM amendments a LEFT JOIN instruments ai ON ai.id=a.amending_instrument "
        "WHERE a.amended_instrument=? ORDER BY a.effective_date DESC", (iid,))]
    cases: list = []  # case-treatment arrives with the provisions rebuild — empty by design
    tab = "history" if tab == "history" else "cases"
    active = inst["jurisdiction"] if inst else None
    return templates.TemplateResponse(request, "instrument.html",
                                      _ctx(conn, active_jur=active, inst=dict(inst) if inst else None,
                                           ver=dict(ver) if ver else None, versions=versions,
                                           amendments=amendments, cases=cases, tab=tab,
                                           rail=rail, sel=sel))


@app.get("/matrix", response_class=HTMLResponse)
def matrix(request: Request):
    conn = _conn()
    cells = [dict(r) for r in conn.execute(
        "SELECT jurisdiction, attribute, value, verified_by FROM matrix_cells "
        "ORDER BY attribute, jurisdiction")]
    return templates.TemplateResponse(request, "matrix.html",
                                      _ctx(conn, active_nav="matrix", cells=cells))
