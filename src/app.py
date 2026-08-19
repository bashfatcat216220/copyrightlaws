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

# Some sources (EUR-Lex, some CLML chapters) SHOUT their container headings in all-caps
# ("GENERAL PROVISIONS", "MEASURES TO ADAPT EXCEPTIONS ..."), while others use normal case
# ("Copyright"), so the rail looks inconsistent. Normalise case for DISPLAY ONLY — the stored
# heading stays the verbatim source (headings are navigational, not monitored version text).
# Applies only to a heading that is ENTIRELY uppercase; mixed-case source is left untouched.
_TITLE_SMALL = {"a", "an", "the", "and", "or", "of", "to", "in", "for", "on", "with", "at",
                "by", "from", "as", "but", "nor", "per", "via", "into", "over"}


def _smart_title(s):
    if not s or any(ch.islower() for ch in s) or not any(ch.isalpha() for ch in s):
        return s                                             # not shouting → leave as-is
    words = s.split()
    out = []
    for i, w in enumerate(words):
        lw = w.lower()
        if 0 < i < len(words) - 1 and lw in _TITLE_SMALL:
            out.append(lw)
        else:
            out.append(lw[:1].upper() + lw[1:])
    return " ".join(out)


templates.env.filters["smart_title"] = _smart_title

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


# Source-vintage caveats (F-FR1 / F-ES4, Bing-approved 2026-08-14). These hand-loaded
# translations are faithful AS OF their vintage but years behind the current law — surface
# that visibly (prime rule 3: flag the caveats per source). Honesty metadata only, keyed by
# the instrument's ext_id; the stored text is never altered.
SOURCE_VINTAGE = {
    "fr-cpi-lit": "Source translation dated ~2006 — may not reflect later amendments; "
                  "confirm against the official source.",
    "es-trlpi-1996": "Source translation dated ~2012 — may not reflect later amendments; "
                     "confirm against the official source.",
    # Wave C (2f audit, 2026-08-16) — NL and IT are the same class of stale hand-loaded
    # translation as FR/ES and were missing their caveat:
    "nl-auteurswet": "Source translation dated ~2012 — may not reflect later amendments; "
                     "confirm against the official source.",
    "it-lda-633-1941": "Source translation dated ~2003 — may not reflect later amendments; "
                       "confirm against the official source.",
}

# Per-instrument caveat notes (Wave C, 2026-08-16) — same mechanism and render slot as
# SOURCE_VINTAGE (keyed by ext_id; the instruments table has no note column). Honesty
# metadata only; the stored text is never altered.
INSTRUMENT_NOTES = {
    "in-copyright-1957": "Authoritative text is the Gazette of India; India Code is an "
                         "as-is departmental consolidation, and indiacode.nic.in blocks "
                         "scripted refresh — confirm against the official source.",
}


def _has_provisions(conn) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='provisions'"
                        ).fetchone() is not None


def _lcp(strings):
    """Longest common prefix, trimmed back to the last whole-word boundary — used to strip an
    instrument's shared citation prefix ('17 U.S.C. ', 'Directive 2001/29 ') off a pinpoint."""
    if not strings:
        return ""
    s1, s2 = min(strings), max(strings)
    i = 0
    while i < len(s1) and s1[i] == s2[i]:
        i += 1
    p = s1[:i]
    return p[:p.rfind(" ") + 1] if " " in p else ""


def _slugify_pin(pin):
    """URL-safe, lowercase pinpoint slug — '§ 107' → 's-107', 'Art. 1(2)(a)' → 'art-1-2-a'.
    § and # are encoded as words so they can't collapse into an adjacent number. Case-only
    twins (e.g. clause (i) vs (I)) are rare (2 across the whole corpus) and are separated by
    the deterministic -N disambiguator in _slug_map, not by casing the URL."""
    s = pin.replace("§", " s ").replace("¶", " para ").replace("#", " no ").lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "x"


def _slug_map(conn, iid):
    """Deep-linkable pinpoint slugs for one instrument's provisions. Keyed on the stable
    `citation` (UNIQUE per instrument), NOT the DB row id — so a link pasted into a memo
    survives a manifest rebuild (row ids do not). Returns (pid->slug, slug->pid)."""
    rows = [dict(r) for r in conn.execute(
        "SELECT id, citation, sort_int, sort_suffix FROM provisions "
        "WHERE instrument_id=? AND citation IS NOT NULL", (iid,))]
    pfx = _lcp([r["citation"] for r in rows])
    rows.sort(key=lambda r: (r["sort_int"] or 0, r["sort_suffix"] or "", r["id"]))
    pid2slug, slug2pid = {}, {}
    for r in rows:
        cit = r["citation"]
        pin = cit[len(pfx):] if pfx and cit.startswith(pfx) else cit
        base = _slugify_pin(pin)
        s, n = base, 2
        while s in slug2pid:                                  # deterministic disambiguator (unused today)
            s, n = f"{base}-{n}", n + 1
        slug2pid[s] = r["id"]
        pid2slug[r["id"]] = s
    return pid2slug, slug2pid


def _chapter_slug_map(conn, iid):
    """Stable slugs for the TOP-LEVEL container provisions (part/subpart/chapter/subchapter)
    of one instrument — so the chapter rail (`?chap=<slug>`) survives a manifest rebuild the
    same way pinpoint deep-links do. Prefers the citation-derived slug from _slug_map (every
    container in the corpus carries a citation), falling back to a label-derived slug ('Chapter
    1' → 'chapter-1'); collisions within the instrument get the deterministic -N disambiguator.
    Returns (cid->slug, slug->cid)."""
    pid2slug, _ = _slug_map(conn, iid)
    tops = [dict(r) for r in conn.execute(
        "SELECT id, label, sort_int, sort_suffix FROM provisions "
        "WHERE instrument_id=? AND parent_id IS NULL AND kind IN "
        f"({','.join('?' * len(_CONTAINER_KINDS))})", (iid, *_CONTAINER_KINDS)).fetchall()]
    tops.sort(key=lambda r: (r["sort_int"] or 0, r["sort_suffix"] or "", r["id"]))
    cid2slug, slug2cid = {}, {}
    for r in tops:
        base = pid2slug.get(r["id"]) or _slugify_pin(r["label"] or "")   # citation slug, else label
        s, n = base, 2
        while s in slug2cid:                                  # deterministic disambiguator
            s, n = f"{base}-{n}", n + 1
        slug2cid[s] = r["id"]
        cid2slug[r["id"]] = s
    return cid2slug, slug2cid


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
    # The INVERSE for back-matter (2f/2g audit): a 'schedule' container with NO children is a
    # TERMINAL leaf holding its own text (37 C.F.R. Part 202 App. A, CA Schedule I + repealed
    # tombstones, JP per-act supplementary blocks) — rail it as clickable. One WITH children
    # stays a group header only (its paragraphs already rail under its label; no double-listing).
    # The test is "no children AT ALL", not "no schedule_para children" — CDPA Sch ZA1/5A nest
    # schedule > part > schedule_para, and must stay containers. Require a current version so a
    # bodiless shell (CDPA Schedule 8) doesn't rail as an empty clickable row.
    SCHED_LEAF = ("({a}.kind='schedule' "
                  "AND NOT EXISTS (SELECT 1 FROM provisions ch WHERE ch.parent_id={a}.id) "
                  "AND EXISTS (SELECT 1 FROM versions v "
                  "            WHERE v.provision_id={a}.id AND v.is_current=1))")
    LEAF_WHERE = f"(({{a}}.kind IN {LEAVES} AND {NOTC}) OR {SCHED_LEAF})"
    n = conn.execute(
        "SELECT COUNT(*) FROM provisions p WHERE p.instrument_id=? AND "
        + LEAF_WHERE.format(a='p'), (iid,)).fetchone()[0]
    if not n:
        return None, None
    # ORDER BY: a top-level childless schedule has no parent (chapter slot NULL would sort it
    # FIRST) — sort it by its OWN sort_int in the chapter slot instead, so its high sort_int
    # (10000+) places it after the body and interleaved chronologically with sibling
    # schedule-with-children groups (JP). Non-schedule rows keep the existing c.sort_int order.
    rows = [dict(r) for r in conn.execute(
        "SELECT s.id, s.label, s.heading, s.citation, s.kind, s.status, "
        "  c.label AS chap_label, c.sort_int AS c_si, c.sort_suffix AS c_su "
        "FROM provisions s LEFT JOIN provisions c ON c.id=s.parent_id "
        "WHERE s.instrument_id=? AND " + LEAF_WHERE.format(a='s') +
        " ORDER BY CASE WHEN s.kind='schedule' AND s.parent_id IS NULL THEN s.sort_int "
        "               ELSE c.sort_int END, "
        "         c.sort_suffix COLLATE BINARY, "
        "         s.sort_int, s.sort_suffix COLLATE BINARY", (iid,))]
    # Recitals (kind='recital') are top-level (no chapter) and precede the articles — rail
    # them as their own group rather than under the null-chapter "Sections" bucket.
    # Likewise a PARENTLESS childless schedule groups under a literal "Schedules" header
    # (a parented one, e.g. 37 C.F.R. App. A, groups under its parent's label as usual).
    for r in rows:
        if r["kind"] == "recital":
            r["chap_label"] = "Recitals"
        elif r["kind"] == "schedule" and not r["chap_label"]:
            r["chap_label"] = "Schedules"
    _fill_incipits(conn, rows)                               # preview text for heading-less rails
    pid2slug, _ = _slug_map(conn, iid)                        # stable deep-link slugs for the rail
    for r in rows:
        r["slug"] = pid2slug.get(r["id"])
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
        "  v.retrieved_at, v.point_in_time, v.is_official_language, v.is_authentic, "
        "  v.has_unapplied_effects "
        "FROM provisions p LEFT JOIN versions v ON v.provision_id=p.id AND v.is_current=1 "
        "WHERE p.id=?", (sel_id,)).fetchone()
    sel = dict(sel) if sel else None
    if sel:
        sel["slug"] = pid2slug.get(sel_id)                    # canonical deep link for this provision
        # Sub-paragraphs repealed IN PLACE render as a dotted leader in the flattened body; pull
        # their source repeal notices (stored as sub-item metadata by the ingest) keyed by label
        # so _format_body can surface "(cc) [S. 205B(1)(cc) repealed …]" in place of the dots.
        notes = {lbl.strip("()"): note for lbl, note in conn.execute(
            "WITH RECURSIVE sub(id) AS (SELECT ? UNION ALL "
            "  SELECT p.id FROM provisions p JOIN sub ON p.parent_id=sub.id) "
            "SELECT label, heading FROM provisions "
            "WHERE id IN (SELECT id FROM sub) AND status='repealed' AND heading IS NOT NULL",
            (sel_id,))}
        sel["body"] = _format_body(sel.get("content"), sel.get("heading"), notes)
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
                    # a redline span that is only a dotted leader is an in-place repeal captured
                    # by the diff — show a muted marker, not a raw dot-wall (the body already
                    # carries the full "[… repealed by …]" notice via _annotate_repealed_subitems).
                    if _PURE_DOTTED_LEADER.fullmatch(txt):
                        txt = "[repealed]"
                    spans.append((op, txt))
            sel["redline_spans"] = spans
    return rail, sel


_LEAF_KINDS = ("section", "article", "schedule_para", "recital")
_CONTAINER_KINDS = ("part", "subpart", "chapter", "subchapter")
# noun for a rail group's count sub-label — a legal reader expects the real unit, not a
# blanket "SECTION" (calling articles/recitals "sections" reads as imprecise). Mixed → 'provision'.
_UNIT_NOUN = {"article": "article", "section": "section", "recital": "recital",
              "schedule_para": "paragraph", "schedule": "schedule"}


def _unit_noun(items):
    kinds = {i["kind"] for i in items}
    return _UNIT_NOUN.get(next(iter(kinds)), "provision") if len(kinds) == 1 else "provision"
# Sentinel chapter-rail id/slug for the synthetic "Schedules" group in _chapter_index (View 1):
# top-level schedules aren't _CONTAINER_KINDS, so their leaves need their own rail entry.
_SCHED_SEL = "schedules"

# Reconstruct KM-style body paragraphs from the flattened section text: a subsection marker
# '(a)'/'(1)'/'(A)' opens a paragraph. Skip markers that are cross-references (a marker
# immediately followed by a lowercase connective, e.g. '(2) of this subsection'). This is a
# DISPLAY heuristic over text stored as one blob — the robust fix is per-subsection text.
# Single uppercase only — '[A-Z]' not '[A-Z]{1,2}' — so a reference like '(EU)' / '(EC)' is never
# read as a subsection marker.
_MARK_SPLIT = re.compile(r"(?<=\s)(\((?:[a-z]{1,2}|\d{1,3}|[A-Z]|[ivxl]{1,4})\))(?=\s)")
_XREF = re.compile(r"^(of|or|and|to|through|shall|hereof|thereof|but|nor)\b", re.I)


# A sub-paragraph repealed in place prints as its label followed by a dotted leader. In CDPA's
# flattened body the label is BARE ("…; cc . . . . d paragraph 3…"), not parenthesised, and the
# dotted run (spaced dots) is the distinctive marker. `_annotate_repealed_subitems` swaps that
# label+dots for the source's own keyed repeal notice, driven by the {label: notice} map so it
# works for every label shape (cc, 3, 3A, …) regardless of _MARK_SPLIT.
_PURE_DOTTED_LEADER = re.compile(r"\s*(?:\.\s*){4,}\.?\s*")


def _annotate_repealed_subitems(txt, notes):
    """Replace each 'label . . . .' in-place-repeal marker with the source's keyed notice,
    bracketed so it reads as the editorial annotation it is (never asserted as statutory text).
    The stored section body is untouched — this is display-only over a copy."""
    if not notes:
        return txt
    for label, note in notes.items():
        if not note:
            continue
        # the bare (or parenthesised) label immediately before a 4+ spaced-dot leader
        pat = re.compile(r"(?<![\w.])\(?" + re.escape(label) + r"\)?\s*(?:\.\s*){4,}\.?")
        txt = pat.sub(f"{label} [{note}]", txt, count=1)
    return txt


def _format_body(content, heading=None, notes=None):
    """Split flat section text into [{mark, text}] paragraphs (KM body structure). A numbered
    marker '(N)' only opens a paragraph when it CONTINUES THE SEQUENCE — an out-of-sequence
    '(N)' is a cross-reference in the prose ('as defined in subsection (2)') and stays inline,
    so numbering isn't thrown off (esp. German Absätze). This is a DISPLAY heuristic over text
    stored as one blob; the robust fix is per-subsection storage (PROJECT_STATE depth layer c).

    `notes` (sub-item label -> repeal notice) surfaces the source's own repeal notice where a
    repealed-in-place sub-paragraph would otherwise show a bare dotted leader (s.205B(1)(cc))."""
    if not content:
        return []
    txt = content.strip()
    if heading:                                            # drop the leading '§ N. <heading>' (shown in the header)
        pos = txt.find(heading.strip())
        if 0 <= pos <= 40:
            txt = txt[pos + len(heading.strip()):].lstrip(" .—:—")
    txt = _annotate_repealed_subitems(txt, notes)          # dotted in-place repeals -> source notice
    toks = _MARK_SPLIT.split(" " + txt)                    # leading space so a '(1)' at position 0 is matched
    paras, mark, cur = [], "", [toks[0]]
    exp_num = 1                                             # next expected top-level '(N)'
    for i in range(1, len(toks), 2):
        mk, body = toks[i], (toks[i + 1] if i + 1 < len(toks) else "")
        inner = mk[1:-1]
        if inner.isdigit():
            if int(inner) != exp_num:                      # out-of-sequence number = cross-ref → inline
                cur.append(mk + body)
                continue
            exp_num += 1
        elif _XREF.match(body.strip()):                    # letter/roman connective cross-ref → inline
            cur.append(mk + body)
            continue
        paras.append({"mark": mark, "text": " ".join(cur).strip()})
        mark, cur = mk, [body]
    paras.append({"mark": mark, "text": " ".join(cur).strip()})
    return [p for p in paras if p["text"]]


# legislation.gov.uk's whole-provision repeal marker: a body that is JUST the provision
# number followed by a dotted leader ("5 . . . . . . ."). Used to distinguish a dot-wall
# tombstone (→ "[Repealed]" label) from a repealed provision that carries a real notice.
_DOTTED_LEADER = re.compile(r"\s*\d+[A-Za-z]*\.?\s*(\.\s*){4,}\.?\s*")


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
    """Attach `incipit` to any leaf dict lacking a heading, from its current version text.

    Exception — dot-wall tombstones: legislation.gov.uk renders a fully-repealed provision's
    body as `number + dotted leader` ("5 . . . . . . ."), so ~32 heading-less repealed CDPA
    provisions would preview as a wall of dots. For a row that is `status='repealed'` AND whose
    body is JUST that dotted leader, show a muted "[Repealed]" UI label instead. Gated on BOTH
    the ingest-set `status` column (so a live BR/FR article can never be labelled repealed) AND
    the dotted-leader body shape — so a repealed provision that carries a real repeal NOTICE
    ("Ss. 31C-31E repealed (1.6.2014) by…") KEEPS that informative notice as its preview (rule 2:
    surface the source's own notice). "[Repealed]" is a UI label, not asserted law: the reading
    pane still shows the source's verbatim dotted leader + the rust badge."""
    need = [r for r in rows if not (r.get("heading") or "").strip()]
    if not need:
        return
    ids = [r["id"] for r in need]
    got = dict(conn.execute(
        "SELECT provision_id, content FROM versions WHERE is_current=1 AND provision_id IN "
        f"({','.join('?' * len(ids))})", ids).fetchall())
    for r in need:
        content = got.get(r["id"])
        if r.get("status") == "repealed" and _DOTTED_LEADER.fullmatch(content or ""):
            r["incipit"] = "[Repealed]"
        else:
            r["incipit"] = _incipit(content)


def _chapter_index(conn, iid, chap):
    """KM 'View 1' — chapter rail + section grid. Groups an instrument's leaf provisions
    under their TOP-LEVEL container ('chapter'); returns the selected chapter's grid. For a
    flat instrument (no containers — e.g. a treaty) there is no chapter rail: the grid is all
    leaves. `chap` selects a chapter (defaults to the first) — it may be a stable slug string
    ('ch-1') OR, for backward compatibility, a legacy int container row id."""
    cid2slug, slug2cid = _chapter_slug_map(conn, iid)         # stable chapter-rail slugs
    chap_raw = chap if isinstance(chap, str) else None        # kept for the flat pseudo-rail below
    if isinstance(chap, str):                                 # resolve a slug → container id …
        chap = slug2cid.get(chap) or slug2cid.get(chap.lower()) or \
            (_SCHED_SEL if chap.lower() == _SCHED_SEL else None) or \
            (int(chap) if chap.isdigit() else None)           # … tolerating a legacy int id ('5')
    rows = [dict(r) for r in conn.execute(
        "SELECT id, parent_id, kind, label, heading, sort_int, sort_suffix, citation, status "
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
    # the inverse for back-matter (mirrors _section_reader's SCHED_LEAF): a 'schedule' with NO
    # children of any kind is a terminal leaf holding its own text (37 CFR App. A, CA Schedule
    # I–III, JP per-act supplementary blocks) — one WITH children (incl. CDPA ZA1/5A's
    # schedule>part>schedule_para nesting) stays a container. Bodiless shells (CDPA Schedule 8,
    # no current version) are excluded so the grid never lists an empty entry.
    _parents = {r["parent_id"] for r in rows if r["parent_id"]}
    _sched_ids = [r["id"] for r in rows if r["kind"] == "schedule" and r["id"] not in _parents]
    _sched_bodied = {pid for (pid,) in conn.execute(
        "SELECT provision_id FROM versions WHERE is_current=1 AND provision_id IN "
        f"({','.join('?' * len(_sched_ids))})", _sched_ids)} if _sched_ids else set()
    leaves = [r for r in rows if (r["kind"] in _LEAF_KINDS
              and not (r["kind"] == "section" and r["id"] in _art_parents))
              or (r["kind"] == "schedule" and r["id"] in _sched_bodied)]
    # width (in ch) of the widest provision NUMBER in a grid — the number column is sized to this
    # so numbers and titles line up regardless of number length. Size to short numeric labels
    # only and cap it: a flat treaty (WPPT) mixes 'Article 12' with 59-char 'Agreed Statement
    # concerning Articles …' recital labels, which would otherwise blow the gutter out to 60ch and
    # shove every article title across the row. Long-label items render as full-width title rows
    # (see instrument.html), so they don't need this gutter.
    numw = lambda g: min(max((len(r["label"]) for r in g if len(r["label"]) <= 16), default=5) + 1, 16)
    pid2slug, _ = _slug_map(conn, iid)                        # stable deep-link slugs for the grid
    for r in leaves:
        r["slug"] = pid2slug.get(r["id"])
    tops = [r for r in rows if r["parent_id"] is None and r["kind"] in _CONTAINER_KINDS]
    if not tops:
        # No stored containers (a flat treaty/directive). Rather than leave the landing page
        # railless, synthesize a presentational rail from the leaves' OWN roles —
        # Recitals / Articles / Appendix / Schedules. This writes NOTHING to the DB and invents
        # no legal structure (labels reflect what the rows already are); it mirrors how View 2
        # (_section_reader) already groups the same flat instruments, so both views agree. An
        # instrument with only one such bucket (e.g. Rome — articles only) keeps the plain grid.
        FLAT_ORDER = {"recitals": 0, "provisions": 1, "appendix": 2, "agreed": 3, _SCHED_SEL: 4}

        def _flat_bucket(r):
            if r["kind"] == "recital":
                # treaties store their Agreed Statements as recitals — those are back-matter
                # keyed to articles, NOT the preamble; label + order them accordingly
                if (r["label"] or "").startswith("Agreed Statement"):
                    return ("agreed", "Agreed Statements")
                return ("recitals", "Recitals")
            if r["kind"] in ("schedule", "schedule_para"):
                return (_SCHED_SEL, "Schedules")
            if (r["label"] or "").startswith("Appendix"):     # Berne's Appendix (real back-matter)
                return ("appendix", "Appendix")
            return ("provisions", "Articles")

        buckets: dict = {}
        for lf in leaves:
            gid, glabel = _flat_bucket(lf)
            buckets.setdefault(gid, {"label": glabel, "items": []})["items"].append(lf)
        if len(buckets) <= 1:                               # single bucket — nothing to separate
            grid = sorted(leaves, key=key)
            _fill_incipits(conn, grid)
            return {"flat": True, "chapters": [], "selected": None, "sel_chap": None,
                    "grid": grid, "numw": numw(grid)}
        for b in buckets.values():
            b["items"].sort(key=key)
        # the main "Articles" bucket is labelled "Provisions" if it holds non-article leaves
        if "provisions" in buckets and not all(
                i["kind"] == "article" for i in buckets["provisions"]["items"]):
            buckets["provisions"]["label"] = "Provisions"
        UNIT_BY_BUCKET = {"recitals": "recital", "agreed": "agreed statement"}
        ordered = sorted(buckets.items(), key=lambda kv: FLAT_ORDER.get(kv[0], 9))
        chapters = [{"id": gid, "slug": gid, "label": b["label"], "heading": None,
                     "n": len(b["items"]),
                     "unit": UNIT_BY_BUCKET.get(gid) or _unit_noun(b["items"]),
                     "range": f"{b['items'][0]['label']}–{b['items'][-1]['label']}"}
                    for gid, b in ordered]
        sel = chap_raw if chap_raw in buckets else (
            "provisions" if "provisions" in buckets else ordered[0][0])
        grid = buckets[sel]["items"]
        _fill_incipits(conn, grid)
        # main "Articles" bucket → let the H1 be the instrument's own title (no meaningful chapter
        # heading exists); a named bucket (Recitals/Appendix/…) titles the page with its label.
        sel_chap = None if sel == "provisions" else {"label": buckets[sel]["label"], "heading": None}
        return {"flat": False, "chapters": chapters, "selected": sel,
                "sel_chap": sel_chap, "grid": grid, "numw": numw(grid)}
    # Wave-E View-1 fix: a schedule LEAF whose top-level ancestor is NOT a rendered container
    # (CA Schedule I–III, CDPA schedule paragraphs under top-level 'schedule' rows, JP/KR
    # addenda blocks, EU annexes) used to group under an id the chapter rail never lists —
    # invisible on the landing page though railed/searchable. Collect them into ONE trailing
    # "Schedules" pseudo-chapter (?chap=schedules) instead of dropping them.
    top_ids = {t["id"] for t in tops}
    groups: dict = {}
    sched_grid: list = []
    for lf in leaves:
        t = top(lf)
        if t["id"] in top_ids:
            groups.setdefault(t["id"], []).append(lf)
        elif lf["kind"] in ("schedule", "schedule_para"):
            # keep each schedule's paras contiguous; the container id breaks sort-key TIES
            # (CDPA Sch ZA1 vs Sch 1 share a doc-order sort_int — without it their paras
            # would interleave pairwise)
            lf["_topkey"] = (*key(t), t["id"])
            sched_grid.append(lf)
    chapters = []
    for tc in sorted(tops, key=key):
        secs = sorted(groups.get(tc["id"], []), key=key)
        chapters.append({"id": tc["id"], "slug": cid2slug.get(tc["id"]),
                         "label": tc["label"], "heading": tc["heading"],
                         "n": len(secs), "unit": _unit_noun(secs) if secs else "provision",
                         "range": f"{secs[0]['label']}–{secs[-1]['label']}" if secs else ""})
    if sched_grid:
        sg = sorted(sched_grid, key=lambda r: (r["_topkey"], key(r)))
        groups[_SCHED_SEL] = sg
        chapters.append({"id": _SCHED_SEL, "slug": _SCHED_SEL, "label": "Schedules",
                         "heading": None, "n": len(sg), "unit": _unit_noun(sg),
                         "range": f"{sg[0]['label']}–{sg[-1]['label']}"})
    sel = chap if (chap in groups) else (chapters[0]["id"] if chapters else None)
    grid = groups.get(sel, []) if sel == _SCHED_SEL else sorted(groups.get(sel, []), key=key)
    _fill_incipits(conn, grid)
    sel_chap = by_id.get(sel) or ({"label": "Schedules", "heading": None}
                                  if sel == _SCHED_SEL else None)
    return {"flat": False, "chapters": chapters, "selected": sel, "sel_chap": sel_chap,
            "grid": grid, "numw": numw(grid)}


@app.get("/instrument/{iid}", response_class=HTMLResponse)
def instrument(request: Request, iid: int, tab: str = "cases",
               sec: int | None = None, chap: str | None = None):
    """Instrument page. `?sec=<pid>` (internal row id) is kept as a backward-compatible
    fallback; the canonical deep link is `/instrument/{iid}/{pinpoint}` (see below).
    `?chap=<slug>` selects a chapter by its stable slug ('ch-1'); a legacy int id still works
    (both resolved in _chapter_index)."""
    return _render_instrument(request, iid, tab, sec, chap)


@app.get("/instrument/{iid}/{pinpoint}", response_class=HTMLResponse)
def instrument_pinpoint(request: Request, iid: int, pinpoint: str, tab: str = "cases"):
    """Deep-linkable provision URL — `/instrument/1/s-107`. Resolves a stable citation-derived
    pinpoint slug to the provision (survives manifest rebuilds, unlike a row id). An unknown
    pinpoint falls back to the instrument index rather than erroring."""
    conn = _conn()
    _, slug2pid = _slug_map(conn, iid)
    pid = slug2pid.get(pinpoint) or slug2pid.get(pinpoint.lower())   # tolerate typed-case
    return _render_instrument(request, iid, tab, pid, None)


def _render_instrument(request: Request, iid: int, tab: str,
                       sec: int | None, chap: str | None):
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

    # vintage_note is the shared per-instrument caveat slot: source-vintage staleness and/or
    # the instrument's own caveat note (e.g. IN: Gazette controls) render as one warn flag.
    note = " ".join(filter(None, (SOURCE_VINTAGE.get(inst["ext_id"]),
                                  INSTRUMENT_NOTES.get(inst["ext_id"])))) if inst else None
    ctx = dict(inst=dict(inst) if inst else None, amendments=amendments, cases=cases, tab=tab,
               view="none",
               vintage_note=note or None)
    if inst and has_prov and sec is not None:              # View 2 — section reader
        rail, sel = _section_reader(conn, iid, sec)
        ctx.update(view="reader", rail=rail, sel=sel,
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
    slug_cache = {}                                           # one _slug_map per distinct instrument, not per row
    for row in rows:
        iid = row["iid"]
        if iid not in slug_cache:
            slug_cache[iid], _ = _slug_map(conn, iid)
        row["slug"] = slug_cache[iid].get(row["pid"])         # stable deep-link slug; None → template ?sec= fallback
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
