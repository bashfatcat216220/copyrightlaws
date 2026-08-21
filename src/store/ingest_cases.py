"""Case-law fetch — CourtListener v4, citeCount-ranked, HUMAN-GATED apply.

Implements CASES-REFETCH-DESIGN-2026-08-21.md (rev. 2), hardened by the 2026-08-21
multi-agent implementation review (23 confirmed findings folded in). Two phases:

  plan   Fetch the top-N most-cited published opinions per curated 17 U.S.C. section
         (exact-phrase, BOTH "§" variants unioned — verified non-equivalent: the API does
         not tokenize '§' away), screen them, diff against EACH DB, and write a review
         artifact + human sheet. NO DB WRITES.
  apply  Converge one DB to the approved target set. Requires the operator-supplied
         --approved-sha (pasted from the review sheet a human actually read) and
         --approved-by. Pair-consistency of generated files is NOT approval. Before
         touching the real DB, apply self-validates on a throwaway clone and PROVES
         idempotency (a second clone run must be a no-op) — else it refuses.

Honesty (prime rules 1–2):
  * treatment='cited' only — CourtListener tells us a case CITES a section (a fact);
    editorial followed/distinguished is a citator judgment we can't source and never assert.
  * holding = the highlighted citing-context excerpt the API returns (real opinion text,
    ≤600 chars, <mark> tags stripped) — we never re-host full opinions.
  * A hit with no real citation stores official_citation=NULL — no minted cites, no
    court+year pseudo-cites. A hit with no case name or no opinion URL is SKIPPED entirely
    (counted + disclosed) — we fabricate neither titles nor provenance.
  * retrieved_at = the FETCH timestamp (artifact meta.generated_at), not apply time —
    provenance never overstates freshness.
  * The model screen (claude-opus-4-8, CLAUDE.md prime rule 5) is ADVISORY and classifies
    fetched/stored text only; its output NEVER enters the DB. Without ANTHROPIC_API_KEY it
    is recorded as not_run (never guessed) and relevance-based removals are BLOCKED at
    apply. It screens BOTH the fetched hits AND the existing below-cap links (the latter
    from their stored excerpts) — existing off-topic links are exactly where the noise
    lives (review finding: Gambill is below-cap, a top-N-only screen could never reach it).
  * Every model drop — including drops of hits that were never linked — is listed on the
    review sheet with the model's reason; drops of hits with citeCount >= 200 carry a
    high_signal_drop flag ON THE SHEET (the floor guard is only real if the human sees it).
  * A link whose case has no parseable cl-<n> ext_id CANNOT be presence-verified — it is
    KEPT and flagged for manual review, never auto-removed under a false "verified absent".

Identity: CourtListener carries one opinion under multiple clusters, so cl-<cluster_id> is
NOT the identity of an opinion. Matching reuses migration 009's merge key (real reporter
cite alone, else title+cite) FIRST, ext_id second — an existing case is UPDATEd in place and
its /instrument/{id} URL never breaks.

Run:
  python src/store/ingest_cases.py plan  --dbs db/corpus.db db/corpus-demo.db [--per 15]
  python src/store/ingest_cases.py apply --db db/corpus.db --allow-corpus \
      --artifact spike/artifacts/cases_refetch_<date>.json \
      --approved-sha <sha256 from the review sheet> --approved-by "<name>"
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import sqlite3
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

CL = "https://www.courtlistener.com"
UA = "copyright-corpus/1.0 (finding aid; contact via repo)"
REPO = Path(__file__).resolve().parent.parent.parent

# keys live in the gitignored repo-root .env (ANTHROPIC_API_KEY unlocks the relevance
# screen; COURTLISTENER_API_TOKEN raises the fetch rate limit) — loaded here because
# nothing else does; real environment variables always win over .env values
sys.path.insert(0, str(REPO / "src"))
from env import load_env  # noqa: E402

load_env()
API_PAGE_SIZE = 20                      # v4 search page size; --per beyond this would need paging

# Most-litigated 17 U.S.C. sections — unchanged curation (widening is a separate decision).
CURATED = ["102", "103", "106", "106A", "107", "108", "109", "110", "115", "201",
           "203", "204", "301", "302", "411", "412", "501", "504", "505", "512", "1201", "1202"]

# The model screen may never silently drop a hit at/above this citeCount — a hallucinated
# drop of a landmark must be a flagged row on the review sheet, not an unnoticed checkbox.
HIGH_SIGNAL_CITECOUNT = 200


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# case_fts — case full-text search (migration 010 imports sync_case_fts; keep stable)
# ---------------------------------------------------------------------------
# Cases carry no `versions` rows (opinion text never re-hosted), so a dedicated FTS table
# indexes exactly what the corpus RECORDS per citing link: case name, citation, excerpt.
CASE_FTS_DDL = ("CREATE VIRTUAL TABLE IF NOT EXISTS case_fts USING fts5("
                "title, citation, holding, tokenize = 'porter unicode61')")


def sync_case_fts(conn) -> int:
    """Rebuild case_fts from case_treatment (full rebuild — idempotent, cheap at this scale)."""
    conn.execute(CASE_FTS_DDL)
    conn.execute("DELETE FROM case_fts")
    conn.execute(
        "INSERT INTO case_fts (rowid, title, citation, holding) "
        "SELECT ct.id, i.title, i.official_citation, ct.holding "
        "FROM case_treatment ct JOIN instruments i ON i.id = ct.case_instrument")
    return conn.execute("SELECT COUNT(*) FROM case_fts").fetchone()[0]


# ---------------------------------------------------------------------------
# Opinion identity — REUSE migration 009's merge key (don't re-derive)
# ---------------------------------------------------------------------------
def _load_009():
    spec = importlib.util.spec_from_file_location(
        "mig009", REPO / "db" / "migrations" / "009_dedupe_cases.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_M009 = _load_009()
merge_key = _M009._merge_key            # (real cite) alone, else (title, cite)


# ---------------------------------------------------------------------------
# Source-derived field mappers (unit-tested; never model-inferred)
# ---------------------------------------------------------------------------
# Reporter preference: official first, specialty/service cites last (design rev. 2).
_CITE_TIERS = [
    re.compile(r"^\d+ U\.S\. \d"),                       # official U.S. Reports
    re.compile(r"^\d+ F\.(4th|3d|2d)? \d|^\d+ F\. \d"),  # federal appellate
    re.compile(r"^\d+ F\. Supp\."),                      # federal district
    re.compile(r"^\d+ S\. Ct\. \d"),
    re.compile(r"^\d+ L\. Ed\."),
]
_CITE_LAST = re.compile(r"U\.S\.P\.Q|WL \d|LEXIS|U\.S\.L\.W|Media L\. Rep|Rad\. Reg")


def best_cite(citations) -> str | None:
    """Best REAL citation from the API's parallel-cite list; None when the list is empty —
    a case with no citation stores NULL, never a minted or court+year pseudo-cite."""
    real = [c.strip() for c in (citations or []) if c and c.strip()[:1].isdigit()]
    if not real:
        return None
    def rank(c):
        for i, pat in enumerate(_CITE_TIERS):
            if pat.search(c):
                return i
        return len(_CITE_TIERS) + (1 if _CITE_LAST.search(c) else 0)
    return sorted(real, key=lambda c: (rank(c), len(c)))[0]


def court_level(court_id, court_name) -> str:
    """From the source's own court id/name (schema vocabulary scotus|circuit|district|other).
    'other' covers state courts (they hear § 301 preemption), CFC (§ 1498(b)), bankruptcy —
    kept and labeled, never auto-noise."""
    cid, name = (court_id or "").lower(), (court_name or "")
    if cid == "scotus" or "Supreme Court of the United States" in name:
        return "scotus"
    if re.fullmatch(r"ca(\d{1,2}|dc|fed)", cid) or ("Court of Appeals" in name and "Circuit" in name):
        return "circuit"
    if "District Court" in name:
        return "district"
    return "other"


def clean_snippet(s) -> str:
    """Highlighted API snippet -> stored excerpt: strip tags (incl. <mark>), collapse
    whitespace, cap at 600 chars. Real opinion text only — never edited, only truncated."""
    s = re.sub(r"<[^>]+>", "", s or "")
    return " ".join(s.split())[:600]


# ---------------------------------------------------------------------------
# Fetch (plan phase) — citeCount-ranked, both '§' phrase variants unioned
# ---------------------------------------------------------------------------
def _api_get(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(
        {"Authorization": f"Token {os.environ['COURTLISTENER_API_TOKEN']}"}
        if os.environ.get("COURTLISTENER_API_TOKEN") else {})})
    for attempt in range(6):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 5:
                # anonymous throttle: honor Retry-After when given, else back off hard —
                # a plan run is a batch job, patience beats a dead run
                ra = e.headers.get("Retry-After") if e.headers else None
                wait = int(ra) if (ra or "").isdigit() else 45 * (attempt + 1)
                print(f"    429 — waiting {wait}s (attempt {attempt + 1}/5)")
                time.sleep(min(wait, 300))
                continue
            raise
    raise RuntimeError("unreachable")


def _phrases(section: str) -> list[str]:
    return [f'"17 U.S.C. § {section}"', f'"17 U.S.C. {section}"']


def _search_url(q: str, published_only: bool = True) -> str:
    return (f"{CL}/api/rest/v4/search/?q={urllib.parse.quote(q)}&type=o"
            f"&order_by={urllib.parse.quote('citeCount desc')}"
            f"{'&stat_Published=on' if published_only else ''}&highlight=on")


def fetch_section(section: str, per: int, skipped: list) -> list[dict]:
    """Top `per` published opinions citing the section, by citeCount. Runs both phrase
    variants (verified non-equivalent) and unions by cluster_id keeping the best data.
    Hits with no case name or no opinion URL are SKIPPED (recorded in `skipped`) — we
    fabricate neither a '(unreported)' title nor a homepage source_url (prime rule 1)."""
    by_cluster: dict = {}
    for q in _phrases(section):
        d = _api_get(_search_url(q))
        for r in (d.get("results") or []):
            cid = r.get("cluster_id") or r.get("id")
            if cid is None:
                continue
            if not r.get("caseName") or not r.get("absolute_url"):
                skipped.append({"section": section, "cluster_id": cid,
                                "why": "no caseName" if not r.get("caseName") else "no URL"})
                continue
            op = (r.get("opinions") or [{}])[0]
            hit = {
                "cluster_id": cid,
                "name": r["caseName"],
                "citations": r.get("citation") or [],
                "court_id": r.get("court_id"),
                "court_name": r.get("court"),
                "cite_count": r.get("citeCount") or 0,
                "date_filed": r.get("dateFiled"),
                "status": r.get("status"),
                "url": CL + r["absolute_url"],
                "excerpt": clean_snippet(op.get("snippet") or ""),
                "section": section,
                "matched_query": q,
            }
            prev = by_cluster.get(cid)
            if prev is None or hit["cite_count"] > prev["cite_count"] or (
                    not prev["excerpt"] and hit["excerpt"]):
                by_cluster[cid] = hit
        time.sleep(0.6)
    hits = sorted(by_cluster.values(), key=lambda h: -h["cite_count"])[:per]
    for i, h in enumerate(hits, 1):
        h["rank"] = i
    return hits


def still_in_results(section: str, cluster_ids: list[int]) -> dict:
    """Below-cap verification, BATCHED: {cluster_id: precedential_status} for those of these
    opinions still in CourtListener's result set for the section (either phrase variant);
    absent ids are omitted. Queried WITHOUT the published filter so an unpublished existing
    link is classified not_published (its true, source-stated reason) rather than falsely
    'no_longer_returned'. One fielded query per section — (phrase OR phrase) AND
    (cluster_id:A OR …) — the per-link version blew the anonymous rate limit."""
    todo = [c for c in cluster_ids if (section, c) not in _PRESENCE_CACHE]
    if todo:                                          # both DBs share links — query once
        phrase = "(" + " OR ".join(_phrases(section)) + ")"
        clusters = "(" + " OR ".join(f"cluster_id:{c}" for c in todo) + ")"
        d = _api_get(_search_url(f"{phrase} AND {clusters}", published_only=False))
        time.sleep(1.5)
        found = {r.get("cluster_id"): (r.get("status") or "Published")
                 for r in (d.get("results") or [])}
        for c in todo:
            _PRESENCE_CACHE[(section, c)] = found.get(c)      # None = absent
    return {c: _PRESENCE_CACHE[(section, c)] for c in cluster_ids
            if _PRESENCE_CACHE.get((section, c)) is not None}


_PRESENCE_CACHE: dict = {}


# ---------------------------------------------------------------------------
# Model screen — ADVISORY, classifies fetched/stored text only, output never enters the DB
# ---------------------------------------------------------------------------
def _screen_one(client, name, court, excerpt, section) -> dict:
    prompt = (
        "You are screening search results for a copyright-law finding aid. Judge ONLY "
        "from the text given — do not use outside knowledge of the case, and do not "
        "invent facts.\n\n"
        f"Target provision: 17 U.S.C. § {section}\n"
        f"Case: {name} ({court or 'court unknown'})\n"
        f"Excerpt (real opinion text): {excerpt!r}\n\n"
        "Does this opinion actually engage the target copyright provision (apply, "
        "construe, or substantively discuss it) — or does it merely mention it in "
        "passing while deciding something unrelated? Reply with exactly one line:\n"
        "KEEP: <one-line reason>  or  DROP: <one-line reason>")
    try:
        msg = client.messages.create(model="claude-opus-4-8", max_tokens=100,
                                     messages=[{"role": "user", "content": prompt}])
        line = (msg.content[0].text or "").strip().splitlines()[0]
    except Exception as e:                           # screen failure ≠ verdict — record it
        return {"verdict": "error", "reason": f"{type(e).__name__}: {e}"}
    verdict = "drop" if line.upper().startswith("DROP") else "keep"
    return {"verdict": verdict, "reason": line.split(":", 1)[-1].strip()}


def make_screener():
    """Returns (screen_status, screen_fn). screen_fn(name, court, excerpt, section)->dict.
    Offline-safe: without ANTHROPIC_API_KEY, screen_fn is None and status is not_run —
    never guessed — and apply refuses relevance-based removals on a not_run artifact."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return "not_run", None
    import anthropic
    client = anthropic.Anthropic()
    return "ran", lambda name, court, excerpt, section: _screen_one(
        client, name, court, excerpt, section)


def screen_hits(hits: list[dict], screen_fn) -> None:
    for h in hits:
        if screen_fn is None:
            h["screen"] = {"verdict": "not_run"}
            continue
        entry = screen_fn(h["name"], h["court_name"], h["excerpt"], h["section"])
        if entry["verdict"] == "drop" and h["cite_count"] >= HIGH_SIGNAL_CITECOUNT:
            entry["high_signal_drop"] = True         # floor guard — flagged, never silent
        h["screen"] = entry


# ---------------------------------------------------------------------------
# Diff (plan phase) — per DB, opinion-identity matching first
# ---------------------------------------------------------------------------
def _existing_cases(conn) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT id, title, official_citation, ext_id, court_level, authority, status, "
        "  enacted_date FROM instruments WHERE type='case'")]


def match_existing(hit: dict, existing: list[dict]):
    """Match a fetched hit to an existing case instrument: merge key (opinion identity)
    FIRST across ALL the hit's parallel cites, ext_id second. Returns the row or None."""
    keys = {merge_key(hit["name"], c) for c in hit["citations"] if c}
    keys.add(merge_key(hit["name"], best_cite(hit["citations"])))
    by_key = {}
    for e in existing:
        if e["official_citation"] is not None:
            by_key.setdefault(merge_key(e["title"], e["official_citation"]), e)
    for k in keys:
        if k in by_key:
            return by_key[k]
    ext = f"cl-{hit['cluster_id']}"
    return next((e for e in existing if e["ext_id"] == ext), None)


def diff_db(conn, hits: list[dict], screen_status: str, check_presence=still_in_results,
            screen_fn=None) -> dict:
    """Classify this DB's case layer against the fetched target set. Pure read.
    screen_fn (when the model screen ran) is ALSO applied to existing below-cap links via
    their stored excerpts — that's where relevance noise actually lives (Gambill-class
    links are below-cap by construction; a top-N-only screen could never reach them)."""
    existing = _existing_cases(conn)
    links = [dict(r) for r in conn.execute(
        "SELECT ct.id AS link_id, ct.provision_id, ct.case_instrument, ct.holding, "
        "  p.citation AS prov_citation, i.title, i.official_citation, i.ext_id "
        "FROM case_treatment ct JOIN provisions p ON p.id=ct.provision_id "
        "JOIN instruments i ON i.id=ct.case_instrument")]
    usc = conn.execute(
        "SELECT id FROM instruments WHERE jurisdiction='US' AND ext_id='t17'").fetchone()
    usc = usc[0] if usc else None

    adds, updates, keeps, keeps_below_cap, removes, manual = [], [], [], [], [], []
    matched_pairs = set()                            # (case_id, section) covered by a hit
    updated_case_ids = set()                         # parallel-cluster hits: update ONCE

    survivors = [h for h in hits if (h.get("screen") or {}).get("verdict") != "drop"]
    for h in survivors:
        e = match_existing(h, existing)
        sec_cite = f"17 U.S.C. § {h['section']}"
        if e:
            matched_pairs.add((e["id"], h["section"]))
            if e["id"] not in updated_case_ids:
                upd = {}
                new_cite = best_cite(h["citations"])
                old = e["official_citation"]
                old_is_real = bool(old) and old.strip()[:1].isdigit()
                if new_cite and not old_is_real:
                    upd["official_citation"] = {"old": old, "new": new_cite}
                if not e["court_level"]:
                    upd["court_level"] = {"old": None,
                                          "new": court_level(h["court_id"], h["court_name"])}
                if e["authority"] != "precedent":
                    upd["authority"] = {"old": e["authority"], "new": "precedent"}
                if e["status"] != "unknown":
                    upd["status"] = {"old": e["status"], "new": "unknown"}
                if upd:
                    updates.append({"case_id": e["id"], "title": e["title"], "fields": upd})
                    updated_case_ids.add(e["id"])
            has_link = any(l["case_instrument"] == e["id"] and l["prov_citation"] == sec_cite
                           for l in links)
            row = {"case_id": e["id"], "title": e["title"], "section": h["section"],
                   "cite_count": h["cite_count"], "hit": h}
            (keeps if has_link else adds).append(
                row if has_link else {**row, "kind": "link_to_existing"})
        else:
            adds.append({"kind": "new_case", "section": h["section"], "hit": h,
                         "title": h["name"], "cite": best_cite(h["citations"]),
                         "court_level": court_level(h["court_id"], h["court_name"]),
                         "cite_count": h["cite_count"], "date_filed": h["date_filed"]})

    # Fetched hits the model DROPPED that match an existing link -> removal candidates
    dropped: dict = {}                               # (case_id, section) -> screen entry
    for h in hits:
        scr = h.get("screen") or {}
        if scr.get("verdict") == "drop":
            e = match_existing(h, existing)
            if e:
                dropped[(e["id"], h["section"])] = scr

    # Existing links not covered by any surviving hit: KEEP below cap when still present;
    # REMOVE only for a VERIFIED taxonomy reason (screened/unpublished/absent) — never
    # "missed the cap", and never an unverifiable claim (no cluster id -> manual review).
    to_check: dict = {}                               # section -> [(link, cl_id)]
    for l in links:
        m = re.search(r"§ (\w+)$", l["prov_citation"] or "")
        section = m.group(1) if m else None
        if section is None or section not in CURATED:
            keeps.append({"case_id": l["case_instrument"], "title": l["title"],
                          "section": section, "note": "outside curated set — untouched"})
            continue
        if (l["case_instrument"], section) in matched_pairs:
            continue                                  # already a KEEP above
        scr = dropped.get((l["case_instrument"], section))
        if scr is not None and screen_status == "ran":
            removes.append({"link_id": l["link_id"], "case_id": l["case_instrument"],
                            "title": l["title"], "section": section,
                            "reason": "screened_irrelevant", "screen": scr})
            continue
        cl_id = None
        if l["ext_id"] and l["ext_id"].startswith("cl-"):
            try:
                cl_id = int(l["ext_id"][3:])
            except ValueError:
                pass
        if cl_id is None:                             # presence unverifiable — never delete
            manual.append({"link_id": l["link_id"], "case_id": l["case_instrument"],
                           "title": l["title"], "section": section,
                           "note": "no parseable CourtListener id — presence unverifiable; "
                                   "KEPT, flagged for manual review"})
            continue
        to_check.setdefault(section, []).append((l, cl_id))
    for section, pairs in to_check.items():
        present = check_presence(section, [c for _, c in pairs])
        for l, cl_id in pairs:
            status = present.get(cl_id)
            if status is None:
                removes.append({"link_id": l["link_id"], "case_id": l["case_instrument"],
                                "title": l["title"], "section": section,
                                "reason": "no_longer_returned"})
            elif status != "Published":
                removes.append({"link_id": l["link_id"], "case_id": l["case_instrument"],
                                "title": l["title"], "section": section,
                                "reason": "not_published",
                                "detail": f"source-stated status: {status}"})
            elif screen_fn is not None:
                # screen the below-cap link from its STORED excerpt — this is the path
                # that can actually reach Gambill-class noise
                scr = screen_fn(l["title"], None, l["holding"] or "", section)
                if scr["verdict"] == "drop":
                    removes.append({"link_id": l["link_id"], "case_id": l["case_instrument"],
                                    "title": l["title"], "section": section,
                                    "reason": "screened_irrelevant", "screen": scr})
                else:
                    keeps_below_cap.append({"link_id": l["link_id"],
                                            "case_id": l["case_instrument"],
                                            "title": l["title"], "section": section,
                                            "screen": scr,
                                            "reason": "below_cap — link is true, cap moved; KEPT"})
            else:
                keeps_below_cap.append({"link_id": l["link_id"], "case_id": l["case_instrument"],
                                        "title": l["title"], "section": section,
                                        "reason": "below_cap — link is true, cap moved; KEPT "
                                                  "(relevance screen not_run)"})
    return {"usc_id": usc, "adds": adds, "updates": updates, "keeps": keeps,
            "keeps_below_cap": keeps_below_cap, "removes": removes, "manual": manual}


# ---------------------------------------------------------------------------
# Plan — fetch + screen once, per-DB diff, artifact + review sheet. NO DB writes.
# ---------------------------------------------------------------------------
def plan(db_paths: list[str], per: int) -> None:
    if per > API_PAGE_SIZE:
        raise SystemExit(f"--per {per} exceeds the API page size ({API_PAGE_SIZE}); "
                         "paging is not implemented — a silent truncation would misreport "
                         "the ranking. Use --per <= 20.")
    date = now_iso()[:10]
    all_hits: list[dict] = []
    skipped: list[dict] = []
    for s in CURATED:
        hits = fetch_section(s, per, skipped)
        all_hits.extend(hits)
        print(f"  § {s}: top {len(hits)} by citeCount "
              f"(lead: {hits[0]['name'][:48] if hits else '—'})")
    if skipped:
        print(f"  skipped {len(skipped)} hits with no case name / no URL (disclosed in artifact)")
    screen_status, screen_fn = make_screener()
    screen_hits(all_hits, screen_fn)
    print(f"model screen: {screen_status}"
          + (" — relevance removals will be BLOCKED at apply" if screen_status != "ran" else ""))

    artifact = {"meta": {"generated_at": now_iso(), "per": per, "sections": CURATED,
                         "screen": screen_status, "skipped_hits": skipped,
                         "design": "CASES-REFETCH-DESIGN-2026-08-21.md"},
                "hits": all_hits, "dbs": {}}
    for p in db_paths:
        conn = sqlite3.connect(p)
        conn.row_factory = sqlite3.Row
        artifact["dbs"][os.path.basename(p)] = diff_db(conn, all_hits, screen_status,
                                                       screen_fn=screen_fn)
        conn.close()

    out = REPO / "spike" / "artifacts" / f"cases_refetch_{date}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(artifact, indent=1, sort_keys=True, ensure_ascii=False)
    out.write_text(body)
    sha = hashlib.sha256(body.encode()).hexdigest()

    sheet = REPO / f"CASES-REFETCH-REVIEW-{date}.md"
    sheet.write_text(_review_md(artifact, sha, out))
    print(f"\nartifact: {out}\nreview sheet: {sheet}\nAPPROVAL SHA: {sha}")
    print("NO DB WRITES were made. Bing reviews the sheet, then apply per DB with "
          "--approved-sha <the sha above>.")


def _review_md(artifact: dict, sha: str, artifact_path: Path) -> str:
    m = artifact["meta"]
    L = [f"# CourtListener re-fetch — REVIEW SHEET ({m['generated_at'][:10]})", "",
         f"Per design `{m['design']}`. Top {m['per']} published opinions per section, "
         f"citeCount-ranked, both `§` phrase variants. Model screen: **{m['screen']}**"
         + ("" if m["screen"] == "ran" else
            " — relevance-based removals are BLOCKED for this artifact (mechanical reasons "
            "only); below-cap links will be screened on a future plan run with the key set."),
         "", f"Artifact: `{artifact_path.name}`", f"**APPROVAL SHA:** `{sha}`",
         "", "To apply (per DB, after review):",
         "```", "python src/store/ingest_cases.py apply --db db/corpus.db --allow-corpus \\",
         f"    --artifact spike/artifacts/{artifact_path.name} \\",
         f"    --approved-sha {sha} --approved-by \"<your name>\"", "```", "",
         "Apply also normalizes every case instrument's `status` `'in_force'` → `'unknown'` "
         "(a statute concept retired on opinions — disclosed here, not hidden in code).", ""]
    if m.get("skipped_hits"):
        L += [f"Fetch skipped **{len(m['skipped_hits'])}** hits with no case name or no "
              "opinion URL (we fabricate neither): "
              + ", ".join(f"§ {s['section']} cluster {s['cluster_id']} ({s['why']})"
                          for s in m["skipped_hits"][:10])
              + (" …" if len(m["skipped_hits"]) > 10 else ""), ""]
    # every model drop is visible on the sheet — high-signal drops flagged loudly
    model_drops = [h for h in artifact["hits"]
                   if (h.get("screen") or {}).get("verdict") == "drop"]
    if model_drops:
        L += ["## Model-screen drops (fetched hits NOT added — review these)", "",
              "| Case | citeCount | § | Model's reason | FLAG |", "|---|---|---|---|---|"]
        for h in sorted(model_drops, key=lambda x: -x["cite_count"]):
            scr = h["screen"]
            L.append(f"| {h['name'][:55]} | {h['cite_count']} | {h['section']} | "
                     f"{scr.get('reason', '—')[:80]} | "
                     f"{'**HIGH-SIGNAL DROP — check this**' if scr.get('high_signal_drop') else ''} |")
        L.append("")
    for db, d in artifact["dbs"].items():
        new_case_rows = [a for a in d["adds"] if a.get("kind") == "new_case"]
        new_links = [a for a in d["adds"] if a.get("kind") == "link_to_existing"]
        # a landmark tops several sections' lists -> several add ROWS, ONE new case at
        # apply time. Group by OPINION IDENTITY (merge key — parallel clusters of the same
        # opinion also collapse), so the sheet counts what apply will actually create.
        by_case: dict = {}
        for a in new_case_rows:
            k = merge_key(a["title"], a["cite"])
            g = by_case.setdefault(k, {**a, "sections": []})
            g["sections"].append(a["hit"]["section"])
        distinct = list(by_case.values())
        L += [f"## {db}", "",
              f"ADD {len(distinct)} new cases carrying {len(new_case_rows)} section links "
              f"+ {len(new_links)} new links to existing cases · "
              f"UPDATE {len(d['updates'])} · KEEP {len(d['keeps'])} · "
              f"KEEP-below-cap {len(d['keeps_below_cap'])} · REMOVE {len(d['removes'])} · "
              f"MANUAL {len(d.get('manual', []))}", ""]
        if distinct:
            L += ["### ADD — new cases (one row per case; §§ = every section it topped)", "",
                  "| Case | Cite | Court | citeCount | Filed | §§ | Screen |", "|---|---|---|---|---|---|---|"]
            for a in sorted(distinct, key=lambda x: -x["cite_count"]):
                h = a["hit"]
                L.append(f"| {a['title'][:60]} | {a['cite'] or '—'} | {a['court_level']} | "
                         f"{a['cite_count']} | {a['date_filed'] or '—'} | "
                         f"{', '.join(a['sections'])} | "
                         f"{(h.get('screen') or {}).get('verdict', '—')} |")
            L.append("")
        if new_links:
            L += ["### ADD — new section links on existing cases", ""]
            L += [f"- {a['title'][:70]} → § {a['section']} (citeCount {a['cite_count']})"
                  for a in new_links] + [""]
        if d["updates"]:
            L += ["### UPDATE — existing cases (old → new)", ""]
            for u in d["updates"]:
                fields = " · ".join(f"{k}: {v['old']!r} → {v['new']!r}"
                                    for k, v in u["fields"].items())
                L.append(f"- [{u['case_id']}] {u['title'][:60]}: {fields}")
            L.append("")
        if d["keeps_below_cap"]:
            L += ["### KEEP (below cap) — true links outside the new top-N, verified still "
                  "in CourtListener's results; KEPT by policy", ""]
            L += [f"- [{k['case_id']}] {k['title'][:70]} → § {k['section']}"
                  + (f"  *(screen: {k['screen'].get('reason', '')[:60]})*"
                     if k.get("screen") else "")
                  for k in d["keeps_below_cap"]] + [""]
        if d.get("manual"):
            L += ["### MANUAL REVIEW — presence unverifiable (no CourtListener id); "
                  "KEPT, decide by hand", ""]
            L += [f"- [{x['case_id']}] {x['title'][:70]} → § {x['section']}"
                  for x in d["manual"]] + [""]
        if d["removes"]:
            L += ["### REMOVE — each row carries its verified reason", "",
                  "| Case | § | Reason | Detail |", "|---|---|---|---|"]
            for r in d["removes"]:
                detail = (r.get("screen") or {}).get("reason") or r.get("detail") or ""
                flag = " **HIGH-SIGNAL**" if (r.get("screen") or {}).get("high_signal_drop") else ""
                L.append(f"| {r['title'][:55]} | {r['section']} | {r['reason']}{flag} | "
                         f"{detail[:80]} |")
            L.append("")
    L += ["---", "*Internal research aid. The reviewer approves this as a DATA diff; legal "
          "correctness of case relevance is a separate (attorney) question.*"]
    return "\n".join(L)


# ---------------------------------------------------------------------------
# Apply — converge ONE DB to the approved target set (gated, backed up, idempotent)
# ---------------------------------------------------------------------------
MUTATION_KEYS = ("cases_added", "links_added", "updated", "links_removed",
                 "cases_removed", "dedupe_merged", "status_normalized")


def _integrity_snapshot(conn) -> dict:
    """Counts PLUS a content hash over the monitored layers — 'unchanged' means the
    version/alert content is byte-identical, not merely same-cardinality."""
    h = hashlib.sha256()
    for (s,) in conn.execute(
            "SELECT COALESCE(content_sha256, '') FROM versions ORDER BY id"):
        h.update(s.encode())
    for row in conn.execute("SELECT id, rule, old_version, new_version FROM alerts ORDER BY id"):
        h.update(repr(tuple(row)).encode())
    return {
        "provisions": conn.execute("SELECT COUNT(*) FROM provisions").fetchone()[0],
        "versions": conn.execute("SELECT COUNT(*) FROM versions").fetchone()[0],
        "alerts": conn.execute("SELECT COUNT(*) FROM alerts").fetchone()[0],
        "content_hash": h.hexdigest(),
    }


def _apply_diff(conn, d: dict, screen_ran: bool, ts_fetch: str, ts_apply: str) -> dict:
    """The actual convergence, on an open connection. Change-only writes: a second run on
    the same DB must return all-zero MUTATION_KEYS (the idempotency proof relies on it)."""
    usc = d["usc_id"]
    stats = dict.fromkeys(MUTATION_KEYS, 0)
    stats["removes_skipped"] = 0

    def _prov_id(section):
        r = conn.execute("SELECT id FROM provisions WHERE instrument_id=? AND citation=?",
                         (usc, f"17 U.S.C. § {section}")).fetchone()
        return r[0] if r else None

    # 1. UPDATE matched existing cases (metadata only; only fields that actually differ)
    for u in d["updates"]:
        row = conn.execute("SELECT official_citation, court_level, authority, status "
                           "FROM instruments WHERE id=? AND type='case'",
                           (u["case_id"],)).fetchone()
        if not row:
            continue
        current = dict(zip(("official_citation", "court_level", "authority", "status"), row))
        sets, vals = [], []
        for field, ch in u["fields"].items():
            if field not in ("official_citation", "court_level", "authority", "status"):
                raise SystemExit(f"REFUSED: artifact update names unexpected column {field!r}")
            if current[field] != ch["new"]:
                sets.append(f"{field}=?")
                vals.append(ch["new"])
        if sets:
            sets.append("last_updated_at=?")
            vals += [ts_apply, u["case_id"]]
            conn.execute(f"UPDATE instruments SET {', '.join(sets)} WHERE id=?", vals)
            stats["updated"] += 1

    # 1b. status normalization on ALL case rows (design S3): 'in_force' is a statute
    # concept — an opinion's currency is not tracked here; disclosed on the review sheet.
    cur = conn.execute("UPDATE instruments SET status='unknown' "
                       "WHERE type='case' AND status='in_force'")
    stats["status_normalized"] = cur.rowcount

    # 2. ADD new cases + links (idempotent: re-match before every insert)
    for a in d["adds"]:
        h = a["hit"]
        e = match_existing(h, _existing_cases(conn))
        cid = e["id"] if e else None
        if cid is None:
            conn.execute(
                "INSERT INTO instruments (jurisdiction, type, title, official_citation, "
                "ext_id, ext_id_scheme, status, authority, court_level, enacted_date, "
                "first_seen_at, last_updated_at) "
                "VALUES ('US','case',?,?,?,'COURTLISTENER','unknown','precedent',?,?,?,?)",
                (h["name"], best_cite(h["citations"]), f"cl-{h['cluster_id']}",
                 court_level(h["court_id"], h["court_name"]),
                 (h["date_filed"] or "")[:4] or None, ts_apply, ts_apply))
            cid = conn.execute("SELECT id FROM instruments WHERE ext_id=? AND "
                               "ext_id_scheme='COURTLISTENER'",
                               (f"cl-{h['cluster_id']}",)).fetchone()[0]
            stats["cases_added"] += 1
        pid = _prov_id(h["section"])
        if pid is None:
            continue
        existing_link = conn.execute(
            "SELECT id, cite_count, retrieved_at FROM case_treatment "
            "WHERE provision_id=? AND case_instrument=?", (pid, cid)).fetchone()
        if existing_link is None:
            conn.execute(
                "INSERT INTO case_treatment (provision_id, case_instrument, treatment, "
                "holding, cite_count, source_url, retrieved_at) "
                "VALUES (?,?,'cited',?,?,?,?)",
                (pid, cid, h["excerpt"] or None, h["cite_count"], h["url"], ts_fetch))
            stats["links_added"] += 1
        elif existing_link[1] != h["cite_count"] or existing_link[2] != ts_fetch:
            conn.execute("UPDATE case_treatment SET cite_count=?, retrieved_at=? WHERE id=?",
                         (h["cite_count"], ts_fetch, existing_link[0]))

    # 2b. refresh kept links' cite_count/retrieved_at from their hit (fetch-time stamp)
    for k in d["keeps"]:
        h = k.get("hit")
        if not h:
            continue
        pid = _prov_id(h["section"])
        if pid:
            conn.execute("UPDATE case_treatment SET cite_count=?, retrieved_at=? "
                         "WHERE provision_id=? AND case_instrument=? AND "
                         "(cite_count IS NOT ? OR retrieved_at != ?)",
                         (h["cite_count"], ts_fetch, pid, k["case_id"],
                          h["cite_count"], ts_fetch))

    # 3. REMOVE links — verified taxonomy reasons only; not_run blocks relevance removals
    for r in d["removes"]:
        if r["reason"] == "screened_irrelevant" and not screen_ran:
            stats["removes_skipped"] += 1
            continue
        if r["reason"] not in ("screened_irrelevant", "not_published", "no_longer_returned"):
            raise SystemExit(f"REFUSED: unknown removal reason {r['reason']!r} in artifact")
        cur = conn.execute("DELETE FROM case_treatment WHERE id=?", (r["link_id"],))
        stats["links_removed"] += cur.rowcount

    # 4. a case left with zero links existed only as a citing record — remove it
    cur = conn.execute(
        "DELETE FROM instruments WHERE type='case' AND id NOT IN "
        "(SELECT DISTINCT case_instrument FROM case_treatment WHERE case_instrument IS NOT NULL)")
    stats["cases_removed"] = cur.rowcount

    # 5. backstop: 009 dedupe on the merged result (mechanism is merge-key matching above;
    # anything this catches is COUNTED — silent structural deletes are not acceptable)
    for _, _, ids in _M009._dup_groups(conn):
        canonical, dups = ids[0], ids[1:]
        for dup in dups:
            conn.execute("UPDATE case_treatment SET case_instrument=? WHERE case_instrument=?",
                         (canonical, dup))
            conn.execute("DELETE FROM instruments WHERE id=? AND type='case'", (dup,))
            stats["dedupe_merged"] += 1
    conn.execute("DELETE FROM case_treatment WHERE id NOT IN "
                 "(SELECT MIN(id) FROM case_treatment GROUP BY provision_id, case_instrument)")

    sync_case_fts(conn)                              # search stays live, same transaction
    return stats


def apply(db_path: str, artifact_path: str, approved_sha: str, approved_by: str,
          allow_corpus: bool) -> None:
    if os.path.basename(db_path) in ("corpus.db", "corpus-demo.db") and not allow_corpus:
        raise SystemExit("refusing to write a live DB — pass --allow-corpus.")
    body = Path(artifact_path).read_text()
    sha = hashlib.sha256(body.encode()).hexdigest()
    if sha != approved_sha:
        raise SystemExit(f"REFUSED: artifact sha {sha[:16]}… does not match the approved sha "
                         f"{approved_sha[:16]}… — the artifact changed after review, or the "
                         "wrong sha was supplied. Re-review the sheet.")
    if not approved_by.strip():
        raise SystemExit("REFUSED: --approved-by is required (who reviewed the sheet?).")
    artifact = json.loads(body)
    dbkey = os.path.basename(db_path)
    if dbkey not in artifact["dbs"]:
        raise SystemExit(f"REFUSED: artifact has no diff for {dbkey} "
                         f"(has: {list(artifact['dbs'])}).")
    d = artifact["dbs"][dbkey]
    d.setdefault("manual", [])
    screen_ran = artifact["meta"]["screen"] == "ran"
    ts_fetch = artifact["meta"].get("generated_at")  # provenance = when data was FETCHED
    if not ts_fetch:
        raise SystemExit("REFUSED: artifact meta has no generated_at — a hit's retrieved_at "
                         "must be the FETCH time, never the apply time (provenance honesty).")
    ts_apply = now_iso()

    # rule 9: real backup via the sqlite backup API before any write (lands next to the
    # target DB, so test DBs never litter the repo's db/ directory)
    bdir = Path(db_path).resolve().parent / "_backup_refetch"
    bdir.mkdir(exist_ok=True)
    backup_path = bdir / f"{dbkey}.{ts_apply.replace(':', '')}.bak.db"
    src = sqlite3.connect(db_path)
    dst = sqlite3.connect(backup_path)
    src.backup(dst)
    dst.close()

    # CLONE VALIDATION + IDEMPOTENCY PROOF before the real DB is touched: run the full
    # convergence twice on a throwaway clone; the second run must be a no-op.
    with tempfile.TemporaryDirectory() as tmp:
        clone_path = Path(tmp) / f"validate-{dbkey}"
        cdst = sqlite3.connect(clone_path)
        src.backup(cdst)
        cdst.close()
        src.close()
        cconn = sqlite3.connect(clone_path)
        cconn.row_factory = sqlite3.Row
        cconn.execute("PRAGMA foreign_keys = ON")
        first = _apply_diff(cconn, d, screen_ran, ts_fetch, ts_apply)
        cconn.commit()
        second = _apply_diff(cconn, d, screen_ran, ts_fetch, ts_apply)
        cconn.commit()
        cconn.close()
        residue = {k: v for k, v in second.items() if k in MUTATION_KEYS and v}
        if residue:
            raise SystemExit(f"REFUSED: apply is not idempotent on the validation clone — "
                             f"second run still mutated {residue}. Real DB untouched "
                             f"(backup at {backup_path}).")
        print(f"clone validation ok — first run {first}; second run: no-op")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 15000")
    before = _integrity_snapshot(conn)
    stats = _apply_diff(conn, d, screen_ran, ts_fetch, ts_apply)
    conn.commit()
    after = _integrity_snapshot(conn)

    cases = conn.execute("SELECT COUNT(*) FROM instruments WHERE type='case'").fetchone()[0]
    links = conn.execute("SELECT COUNT(*) FROM case_treatment").fetchone()[0]
    fk_ok = not conn.execute("PRAGMA foreign_key_check").fetchall()
    integ = conn.execute("PRAGMA integrity_check").fetchone()[0]
    conn.close()

    print(f"applied to {dbkey} (approved by: {approved_by}; backup: {backup_path.name})")
    print(f"  {stats}")
    print(f"  cases now: {cases} · links now: {links}")
    print(f"  invariant (provisions/versions/alerts byte-identical): {before == after}")
    print(f"  foreign_key_check ok: {fk_ok} · integrity_check: {integ}")
    if before != after:
        print("  !! INVARIANT BROKEN — restore from the backup and investigate.")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan", help="fetch + screen + per-DB diff -> review artifact (NO DB writes)")
    p.add_argument("--dbs", nargs="+", required=True)
    p.add_argument("--per", type=int, default=15)
    a = sub.add_parser("apply", help="converge one DB to the approved target set")
    a.add_argument("--db", required=True)
    a.add_argument("--artifact", required=True)
    a.add_argument("--approved-sha", required=True)
    a.add_argument("--approved-by", required=True)
    a.add_argument("--allow-corpus", action="store_true")
    ns = ap.parse_args()
    if ns.cmd == "plan":
        plan(ns.dbs, ns.per)
    else:
        apply(ns.db, ns.artifact, ns.approved_sha, ns.approved_by, ns.allow_corpus)


if __name__ == "__main__":
    main()
