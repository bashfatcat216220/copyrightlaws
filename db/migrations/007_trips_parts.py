"""007 — TRIPS: restore the real Part / Section container structure.

TRIPS was ingested as a flat list of 73 articles (+ the Annex), so its landing page had
no chapter rail — unlike every chaptered instrument (CDPA, BR, …) whose landing shows a
left "Parts" rail + the section grid. The Agreement is in fact divided into seven Parts,
with Part II (Standards) split into 8 Sections and Part III (Enforcement) into 5. This
migration inserts those Part/Section containers and re-parents the articles under them, so
the reader groups TRIPS exactly like CDPA (landing = Parts, in-article rail = Sections).

The structure is taken from the SOURCE artifact `spike/artifacts/trips_wto.html` (rule 9) —
NOT asserted from memory (prime rule 1). The migration re-parses the artifact's Part/Section/
Article headings and maps every article to its container by document position; if the parse
does not cover all 73 stored articles it ABORTS rather than guess.

STRUCTURE-ONLY — like migrations 004/005/006 it touches NOTHING versioned:
  * inserts `provisions` rows of kind 'part'/'section' (role 'enacting'), and
  * updates `provisions.parent_id` on the 73 article rows,
  * writes NO `content`, NO `content_sha256`, NO version rows, NO `is_current` — so the
    change monitor and any fired alerts are unaffected (containers carry no text).
  * sort_int uses global document order (each container = its first article's number) so the
    reader's parent-keyed ORDER BY stays monotonic across Part- and Section-parented articles.
  * The Annex/Appendix (top-level schedules) are left as-is — they surface as the trailing
    "Schedules" rail entry once real Parts exist, mirroring CDPA.
  * Idempotent: a re-run reuses existing containers (matched by citation) and re-asserts the
    article parents, making no duplicate rows.

Run:
    python db/migrations/007_trips_parts.py --db db/corpus.db
    python db/migrations/007_trips_parts.py --db db/corpus-demo.db
"""
from __future__ import annotations

import argparse
import html
import os
import re
import sqlite3

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
DEFAULT_HTML = os.path.join(REPO, "spike", "artifacts", "trips_wto.html")


def parse_structure(html_path: str):
    """Return ordered [(roman, part_title, [(sec_no, sec_title, [art_no,...]) | ('', '', [direct arts])])].

    Re-parses the WTO artifact's visible text: lines like 'Part I: …', 'Section 1: …',
    'Article 9 …' in document order. Articles between a Part header and its first Section are
    'direct' children of the Part; otherwise they belong to the current Section.
    """
    raw = open(html_path, "r", encoding="iso-8859-1").read()
    raw = re.sub(r"(?is)<(script|style).*?</\1>", " ", raw)
    txt = re.sub(r"(?s)<[^>]+>", " ", raw)
    txt = html.unescape(txt).replace("\xa0", " ")
    txt = re.sub(r"[ \t]+", " ", txt)
    lines = [l.strip() for l in txt.splitlines() if l.strip()]
    # main body ends at the Annex — the endnotes below it re-mention "Section N" (false hits)
    end = next((i for i, l in enumerate(lines) if re.match(r"(?i)^annex\b", l)), len(lines))
    parts: list = []
    cur_part = cur_sec = None
    for l in lines[:end]:
        mp = re.match(r"(?i)^part\s+([IVX]+)\s*[:\.]\s*(.+)$", l)
        ms = re.match(r"(?i)^section\s+(\d+)\s*[:\.]\s*(.+)$", l)
        # articles include bis/ter forms (Art. 31bis, added by the 2005 Protocol)
        ma = re.match(r"(?i)^article\s+(\d+\s*(?:bis|ter|quater|quinquies)?)\b", l)
        if mp and len(l) < 120 and "shall" not in l.lower():
            cur_part = {"roman": mp.group(1), "title": mp.group(2).strip(),
                        "direct": [], "sections": []}
            parts.append(cur_part); cur_sec = None
        elif ms and len(l) < 120 and cur_part is not None:
            cur_sec = {"no": ms.group(1), "title": ms.group(2).strip(), "arts": []}
            cur_part["sections"].append(cur_sec)
        elif ma and cur_part is not None:
            tok = re.sub(r"\s+", "", ma.group(1)).lower()    # '31bis', '39'
            (cur_sec["arts"] if cur_sec else cur_part["direct"]).append(tok)
    return parts


def _art_token(label: str) -> str | None:
    """Normalize a stored article label to a match token: 'Article 31bis' -> '31bis'."""
    m = re.match(r"(?i)article\s+(\d+\s*(?:bis|ter|quater|quinquies)?)\b", label.strip())
    return re.sub(r"\s+", "", m.group(1)).lower() if m else None


def _art_int(tok: str) -> int:
    return int(re.match(r"\d+", tok).group())


ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7,
         "VIII": 8, "IX": 9, "X": 10}


def _snapshot(conn, iid):
    return {
        "versions": conn.execute("SELECT COUNT(*) FROM versions").fetchone()[0],
        "alerts": conn.execute("SELECT COUNT(*) FROM alerts").fetchone()[0],
        "articles": conn.execute(
            "SELECT COUNT(*) FROM provisions WHERE instrument_id=? AND kind='article'",
            (iid,)).fetchone()[0],
        "sha_fingerprint": conn.execute(
            "SELECT COUNT(*), COALESCE(GROUP_CONCAT(content_sha256),'') FROM versions "
            "WHERE instrument_id=? AND is_current=1", (iid,)).fetchone(),
    }


def _upsert_container(conn, iid, parent_id, sort_int, label, heading, kind, citation):
    """Insert a container row, or reuse an existing one matched by citation (idempotent)."""
    row = conn.execute(
        "SELECT id FROM provisions WHERE instrument_id=? AND citation=? AND kind=?",
        (iid, citation, kind)).fetchone()
    if row:
        conn.execute(
            "UPDATE provisions SET parent_id=?, sort_int=?, sort_suffix='', label=?, "
            "heading=?, role='enacting', status='in_force' WHERE id=?",
            (parent_id, sort_int, label, heading, row[0]))
        return row[0]
    cur = conn.execute(
        "INSERT INTO provisions (instrument_id, parent_id, sort_int, sort_suffix, label, "
        "heading, kind, role, citation, status) "
        "VALUES (?,?,?,'',?,?,?, 'enacting', ?, 'in_force')",
        (iid, parent_id, sort_int, label, heading, kind, citation))
    return cur.lastrowid


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", required=True)
    ap.add_argument("--html", default=DEFAULT_HTML)
    a = ap.parse_args()
    if not os.path.exists(a.html):
        raise SystemExit(f"source artifact not found: {a.html} (rule 9 — cannot confirm structure)")

    parts = parse_structure(a.html)
    # flatten the source's article coverage (tokens: '1'..'73' + '31bis')
    src_arts = []
    for p in parts:
        src_arts += p["direct"]
        for s in p["sections"]:
            src_arts += s["arts"]
    if len(src_arts) != len(set(src_arts)):
        raise SystemExit(f"artifact parse produced duplicate articles: {sorted(src_arts)}")

    conn = sqlite3.connect(a.db)
    conn.execute("PRAGMA foreign_keys = ON")
    row = conn.execute(
        "SELECT id FROM instruments WHERE ext_id='trips-1994' AND ext_id_scheme='TREATY'").fetchone()
    if not row:
        raise SystemExit("TRIPS instrument not found in this DB")
    iid = row[0]

    before = _snapshot(conn, iid)
    # article token -> provision id (from the stored 'Article N[bis]' labels)
    art_id = {}
    for pid, label in conn.execute(
            "SELECT id, label FROM provisions WHERE instrument_id=? AND kind='article'", (iid,)):
        tok = _art_token(label)
        if tok:
            art_id[tok] = pid
    # source structure and stored articles must cover EXACTLY the same set (prime rule 1)
    if set(src_arts) != set(art_id):
        only_src = sorted(set(src_arts) - set(art_id))
        only_db = sorted(set(art_id) - set(src_arts))
        raise SystemExit(f"artifact/DB article mismatch — only in source: {only_src}; "
                         f"only in DB: {only_db}; refusing to guess")
    print(f"source artifact: {len(parts)} Parts, "
          f"{sum(len(p['sections']) for p in parts)} Sections, {len(src_arts)} articles; "
          f"exact match to the {len(art_id)} stored articles")

    n_parts = n_secs = n_reparent = 0
    for p in parts:
        first_art = min(_art_int(t) for t in p["direct"] + [a for s in p["sections"] for a in s["arts"]])
        part_id = _upsert_container(
            conn, iid, None, first_art, f"Part {p['roman']}", p["title"], "part",
            f"TRIPS Part {p['roman']}")
        n_parts += 1
        for t in p["direct"]:                                # articles directly under the Part
            conn.execute("UPDATE provisions SET parent_id=? WHERE id=?", (part_id, art_id[t]))
            n_reparent += 1
        for s in p["sections"]:
            sec_first = min(_art_int(t) for t in s["arts"])
            sec_id = _upsert_container(
                conn, iid, part_id, sec_first, f"Section {s['no']}", s["title"], "section",
                f"TRIPS Part {p['roman']}, Section {s['no']}")
            n_secs += 1
            for t in s["arts"]:
                conn.execute("UPDATE provisions SET parent_id=? WHERE id=?", (sec_id, art_id[t]))
                n_reparent += 1
    conn.commit()

    after = _snapshot(conn, iid)
    print(f"containers: {n_parts} Parts + {n_secs} Sections; re-parented {n_reparent} articles")

    # ── invariants: structure-only, monitor untouched ─────────────────────────
    assert after["versions"] == before["versions"], "version count changed"
    assert after["alerts"] == before["alerts"], "alert count changed"
    assert after["articles"] == before["articles"], "article count changed"
    assert after["sha_fingerprint"] == before["sha_fingerprint"], \
        "TRIPS current-version text/sha changed — NOT structure-only!"
    print(f"  invariants: versions {after['versions']}, alerts {after['alerts']} unchanged; "
          f"{after['articles']} articles intact; TRIPS current-version SHAs byte-identical "
          f"(no content write)")

    # show the restored top-level rail (what the landing page will now show)
    print("  restored Parts rail:")
    for lbl, hd, si in conn.execute(
            "SELECT label, heading, sort_int FROM provisions WHERE instrument_id=? AND "
            "kind='part' AND parent_id IS NULL ORDER BY sort_int", (iid,)):
        n = conn.execute(
            "WITH RECURSIVE d(id) AS (SELECT ? UNION ALL SELECT p.id FROM provisions p "
            "JOIN d ON p.parent_id=d.id) "
            "SELECT COUNT(*) FROM provisions WHERE id IN (SELECT id FROM d) AND kind='article'",
            (conn.execute("SELECT id FROM provisions WHERE instrument_id=? AND label=? AND kind='part'",
                          (iid, lbl)).fetchone()[0],)).fetchone()[0]
        print(f"     {lbl:9} · {hd[:52]:52} ({n} arts)")
    conn.close()


if __name__ == "__main__":
    main()
