"""Copyright Corpus — web shell (FastAPI + Jinja2 + HTMX).

Reads ONLY from the DB. Every page renders the standing finding-aid caveat and, on any
instrument/version, its source_url + retrieved_at (the two fields that matter most — the
tool is a finding aid, never a citation). Works empty (no data yet) with honest empty-states.
Styling = the Article One design system (navy accent, ink-black surfaces, Caslon/Source
Serif/Franklin/Plex Mono) in a legal-research-terminal layout (rail + citation gutter).
"""
from __future__ import annotations

import re
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
        "  (SELECT COUNT(*) FROM instruments i WHERE i.jurisdiction=j.code AND i.type != 'case') AS n "
        "FROM jurisdictions j ORDER BY j.tier, j.name"):
        tiers.setdefault(r["tier"], []).append(dict(r))
    return tiers


def _counts(conn: sqlite3.Connection) -> dict:
    """Live corpus counts for the breadcrumb bar (honest, computed — never hardcoded)."""
    return {
        "jurisdictions": conn.execute("SELECT COUNT(*) FROM jurisdictions").fetchone()[0],
        "instruments": conn.execute("SELECT COUNT(*) FROM instruments WHERE type != 'case'").fetchone()[0],
        "versions": conn.execute("SELECT COUNT(*) FROM versions").fetchone()[0],
        "alerts": conn.execute("SELECT COUNT(*) FROM alerts").fetchone()[0],
    }


def _ctx(conn, active_jur=None, active_nav=None, **extra) -> dict:
    return {"jurs": _rail(conn), "active_jur": active_jur, "active_nav": active_nav,
            "counts": _counts(conn), **extra}


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    conn = _conn()
    stats = {
        "instruments": conn.execute("SELECT COUNT(*) FROM instruments WHERE type != 'case'").fetchone()[0],
        "versions": conn.execute("SELECT COUNT(*) FROM versions").fetchone()[0],
        "jurisdictions": conn.execute("SELECT COUNT(*) FROM jurisdictions").fetchone()[0],
    }
    recent = [dict(r) for r in conn.execute(
        "SELECT id, title, official_citation, jurisdiction FROM instruments "
        "WHERE type != 'case' ORDER BY last_updated_at DESC LIMIT 12")]
    # distinct official-source domains, for the sources note at the foot of the home page
    from urllib.parse import urlparse
    srcs = {urlparse(u).netloc.replace("www.", "")
            for (u,) in conn.execute("SELECT DISTINCT source_url FROM versions WHERE source_url IS NOT NULL")
            if u and urlparse(u).netloc}
    return templates.TemplateResponse(request, "index.html",
                                      _ctx(conn, active_nav="browse", stats=stats, recent=recent,
                                           sources=sorted(srcs)))


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
        "WHERE jurisdiction=? AND type != 'case' ORDER BY type, title", (code,))]
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
    # A 'section' that CONTAINS 'article' children is a container, not a readable leaf
    # (JP structures its act chapter > section > article) — exclude it so it rails as a group
    # header rather than an empty clickable entry. US/UK sections hold subsections, never
    # articles, so they are unaffected.
    NOTC = ("NOT ({a}.kind='section' AND EXISTS (SELECT 1 FROM provisions ch "
            "WHERE ch.parent_id={a}.id AND ch.kind='article'))")
    n = conn.execute("SELECT COUNT(*) FROM provisions WHERE instrument_id=? "
                     f"AND kind IN {LEAVES} AND {NOTC.format(a='provisions')}", (iid,)).fetchone()[0]
    if not n:
        return None, None
    rows = [dict(r) for r in conn.execute(
        "SELECT s.id, s.label, s.heading, s.citation, s.kind, "
        "  c.label AS chap_label, c.sort_int AS c_si, c.sort_suffix AS c_su "
        "FROM provisions s LEFT JOIN provisions c ON c.id=s.parent_id "
        f"WHERE s.instrument_id=? AND s.kind IN {LEAVES} AND {NOTC.format(a='s')} "
        "ORDER BY c.sort_int, c.sort_suffix COLLATE BINARY, "
        "         s.sort_int, s.sort_suffix COLLATE BINARY", (iid,))]
    # Recitals (kind='recital') are top-level (no chapter) and precede the articles — rail
    # them as their own group rather than under the null-chapter "Sections" bucket.
    for r in rows:
        if r["kind"] == "recital":
            r["chap_label"] = "Recitals"
    _fill_incipits(conn, rows)                               # preview text for heading-less rails
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
        "SELECT p.id, p.label, p.heading, p.citation, p.status, v.content, v.source_url, "
        "  v.retrieved_at, v.point_in_time, v.is_official_language, v.is_authentic "
        "FROM provisions p LEFT JOIN versions v ON v.provision_id=p.id AND v.is_current=1 "
        "WHERE p.id=?", (sel_id,)).fetchone()
    sel = dict(sel) if sel else None
    if sel:
        sel["body"] = _format_body(sel.get("content"), sel.get("heading"))
        sel["nver"] = conn.execute("SELECT COUNT(*) FROM versions WHERE provision_id=?",
                                   (sel_id,)).fetchone()[0]
        sel["history"] = [dict(r) for r in conn.execute(
            "SELECT point_in_time, retrieved_at, is_current FROM versions "
            "WHERE provision_id=? ORDER BY retrieved_at DESC", (sel_id,))]
        sel["cases"] = [dict(r) for r in conn.execute(
            "SELECT i.title AS name, i.official_citation AS cite, i.enacted_date AS year, "
            "  ct.treatment, ct.holding, ct.source_url "
            "FROM case_treatment ct JOIN instruments i ON i.id=ct.case_instrument "
            "WHERE ct.provision_id=? ORDER BY i.enacted_date DESC, ct.id", (sel_id,))]
        # if this provision's current version is an alert's new_version, show the redline
        al = conn.execute(
            "SELECT a.summary, a.rule, ov.point_in_time AS old_pit "
            "FROM alerts a JOIN versions nv ON nv.id=a.new_version "
            "LEFT JOIN versions ov ON ov.id=a.old_version "
            "WHERE nv.provision_id=? AND nv.is_current=1 ORDER BY a.id DESC LIMIT 1", (sel_id,)).fetchone()
        if al:
            sel["redline_rule"] = al["rule"]
            sel["redline_old_pit"] = al["old_pit"]
            spans = []
            for span in (al["summary"] or "").split("   "):
                span = span.strip()
                if span:
                    op, _, txt = span.partition(" ")
                    spans.append((op, txt))
            sel["redline_spans"] = spans
    return rail, sel


_LEAF_KINDS = ("section", "article", "schedule_para", "recital")
_CONTAINER_KINDS = ("part", "subpart", "chapter", "subchapter")

# Reconstruct KM-style body paragraphs from the flattened section text: a subsection marker
# '(a)'/'(1)'/'(A)' opens a paragraph. Skip markers that are cross-references (a marker
# immediately followed by a lowercase connective, e.g. '(2) of this subsection'). This is a
# DISPLAY heuristic over text stored as one blob — the robust fix is per-subsection text.
_MARK_SPLIT = re.compile(r"(?<=\s)(\((?:[a-z]{1,2}|\d{1,3}|[A-Z]{1,2}|[ivxl]{1,4})\))(?=\s)")
_XREF = re.compile(r"^(of|or|and|to|through|shall|hereof|thereof|but|nor)\b", re.I)


def _format_body(content, heading=None):
    """Split flat section text into [{mark, text}] paragraphs (KM body structure)."""
    if not content:
        return []
    txt = content.strip()
    if heading:                                            # drop the leading '§ N. <heading>' (shown in the header)
        pos = txt.find(heading.strip())
        if 0 <= pos <= 40:
            txt = txt[pos + len(heading.strip()):].lstrip(" .—:—")
    toks = _MARK_SPLIT.split(txt)
    paras, mark, cur = [], "", [toks[0]]
    for i in range(1, len(toks), 2):
        mk, body = toks[i], (toks[i + 1] if i + 1 < len(toks) else "")
        if _XREF.match(body.strip()):                      # cross-ref, not a new subsection — keep inline
            cur.append(mk + body)
            continue
        paras.append({"mark": mark, "text": " ".join(cur).strip()})
        mark, cur = mk, [body]
    paras.append({"mark": mark, "text": " ".join(cur).strip()})
    return [p for p in paras if p["text"]]


def _incipit(content, limit=90):
    """A short text preview for provisions that carry NO source heading (e.g. Brazilian /
    French articles are numbered but not titled). Shown in the index/rail so the list isn't a
    column of bare numbers — it is the provision's own opening words, clearly a preview, never
    an invented rubric (prime rule 1: we don't originate titles the source doesn't have)."""
    if not content:
        return ""
    txt = re.sub(r"\s+", " ", content.strip())
    txt = re.sub(r"^\W*\d{1,3}\W+", "", txt) if False else txt   # keep leading numerals as-is
    if len(txt) <= limit:
        return txt
    cut = txt[:limit].rsplit(" ", 1)[0]
    return (cut or txt[:limit]).rstrip(" ,;:.") + "…"


def _fill_incipits(conn, rows):
    """Attach `incipit` to any leaf dict lacking a heading, from its current version text."""
    need = [r for r in rows if not (r.get("heading") or "").strip()]
    if not need:
        return
    ids = [r["id"] for r in need]
    got = dict(conn.execute(
        "SELECT provision_id, content FROM versions WHERE is_current=1 AND provision_id IN "
        f"({','.join('?' * len(ids))})", ids).fetchall())
    for r in need:
        r["incipit"] = _incipit(got.get(r["id"]))


def _chapter_index(conn, iid, chap):
    """KM 'View 1' — chapter rail + section grid. Groups an instrument's leaf provisions
    under their TOP-LEVEL container ('chapter'); returns the selected chapter's grid. For a
    flat instrument (no containers — e.g. a treaty) there is no chapter rail: the grid is all
    leaves. `chap` selects a chapter (defaults to the first)."""
    rows = [dict(r) for r in conn.execute(
        "SELECT id, parent_id, kind, label, heading, sort_int, sort_suffix, citation "
        "FROM provisions WHERE instrument_id=?", (iid,))]
    if not rows:
        return None
    by_id = {r["id"]: r for r in rows}
    key = lambda r: (r["sort_int"], r["sort_suffix"])

    def top(r):
        while r["parent_id"] is not None and r["parent_id"] in by_id:
            r = by_id[r["parent_id"]]
        return r

    # sections that contain 'article' children are containers (JP chapter>section>article), not leaves
    _art_parents = {r["parent_id"] for r in rows if r["kind"] == "article" and r["parent_id"]}
    leaves = [r for r in rows if r["kind"] in _LEAF_KINDS
              and not (r["kind"] == "section" and r["id"] in _art_parents)]
    # width (in ch) of the widest provision number in a grid — the section-number column is
    # sized to this so numbers and titles line up in a fixed spot regardless of number length.
    numw = lambda g: max((len(r["label"]) for r in g), default=5) + 1
    tops = [r for r in rows if r["parent_id"] is None and r["kind"] in _CONTAINER_KINDS]
    if not tops:                                            # flat instrument — no chapter rail
        grid = sorted(leaves, key=key)
        _fill_incipits(conn, grid)
        return {"flat": True, "chapters": [], "selected": None, "sel_chap": None,
                "grid": grid, "numw": numw(grid)}
    groups: dict = {}
    for lf in leaves:
        groups.setdefault(top(lf)["id"], []).append(lf)
    chapters = []
    for tc in sorted(tops, key=key):
        secs = sorted(groups.get(tc["id"], []), key=key)
        chapters.append({"id": tc["id"], "label": tc["label"], "heading": tc["heading"],
                         "n": len(secs),
                         "range": f"{secs[0]['label']}–{secs[-1]['label']}" if secs else ""})
    sel = chap if (chap in groups) else (chapters[0]["id"] if chapters else None)
    grid = sorted(groups.get(sel, []), key=key)
    _fill_incipits(conn, grid)
    return {"flat": False, "chapters": chapters, "selected": sel, "sel_chap": by_id.get(sel),
            "grid": grid, "numw": numw(grid)}


@app.get("/instrument/{iid}", response_class=HTMLResponse)
def instrument(request: Request, iid: int, tab: str = "cases",
               sec: int | None = None, chap: int | None = None):
    conn = _conn()
    inst = conn.execute("SELECT * FROM instruments WHERE id=?", (iid,)).fetchone()
    has_prov = bool(inst) and _has_provisions(conn) and conn.execute(
        "SELECT 1 FROM provisions WHERE instrument_id=? LIMIT 1", (iid,)).fetchone() is not None
    # History tab: amendments TO this instrument.
    amendments = [dict(r) for r in conn.execute(
        "SELECT a.effective_date, a.effect, a.sections_affected, "
        "  ai.official_citation AS amending_citation, ai.title AS amending_title "
        "FROM amendments a LEFT JOIN instruments ai ON ai.id=a.amending_instrument "
        "WHERE a.amended_instrument=? ORDER BY a.effective_date DESC", (iid,))] if inst else []
    cases: list = []
    tab = "history" if tab == "history" else "cases"

    ctx = dict(inst=dict(inst) if inst else None, amendments=amendments, cases=cases, tab=tab,
               view="none")
    if inst and has_prov and sec is not None:              # View 2 — section reader
        rail, sel = _section_reader(conn, iid, sec)
        rail_numw = max((len(s["label"]) for grp in (rail or []) for s in grp["sections"]),
                        default=6) + 1                     # align the rail number column (site standard)
        ctx.update(view="reader", rail=rail, sel=sel, rail_numw=rail_numw,
                   cases=(sel.get("cases") if sel else []))
    elif inst and has_prov:                                # View 1 — chapter index
        ctx.update(view="index", ci=_chapter_index(conn, iid, chap))
    elif inst:                                             # whole-instrument fallback (no provisions)
        ver = conn.execute("SELECT * FROM versions WHERE instrument_id=? AND is_current=1 "
                           "ORDER BY point_in_time DESC LIMIT 1", (iid,)).fetchone()
        versions = [dict(r) for r in conn.execute(
            "SELECT id, point_in_time, retrieved_at, is_authentic, is_official_language "
            "FROM versions WHERE instrument_id=? ORDER BY point_in_time DESC", (iid,))]
        ctx.update(view="whole", ver=dict(ver) if ver else None, versions=versions)
    return templates.TemplateResponse(request, "instrument.html",
                                      _ctx(conn, active_jur=inst["jurisdiction"] if inst else None, **ctx))


@app.get("/alerts", response_class=HTMLResponse)
def alerts(request: Request):
    conn = _conn()
    rows = [dict(r) for r in conn.execute(
        "SELECT a.id, a.rule, a.summary, a.notified_at, "
        "  i.id AS iid, i.jurisdiction, i.official_citation, "
        "  p.id AS pid, p.citation, p.heading, "
        "  ov.point_in_time AS old_pit, nv.point_in_time AS new_pit "
        "FROM alerts a "
        "JOIN instruments i ON i.id=a.instrument_id "
        "LEFT JOIN versions nv ON nv.id=a.new_version "
        "LEFT JOIN versions ov ON ov.id=a.old_version "
        "LEFT JOIN provisions p ON p.id=nv.provision_id "
        "ORDER BY a.notified_at DESC, a.id DESC")]
    return templates.TemplateResponse(request, "alerts.html",
                                      _ctx(conn, active_nav="alerts", alerts=rows))


@app.get("/matrix", response_class=HTMLResponse)
def matrix(request: Request):
    conn = _conn()
    cells = [dict(r) for r in conn.execute(
        "SELECT jurisdiction, attribute, value, verified_by FROM matrix_cells "
        "ORDER BY attribute, jurisdiction")]
    return templates.TemplateResponse(request, "matrix.html",
                                      _ctx(conn, active_nav="matrix", cells=cells))
