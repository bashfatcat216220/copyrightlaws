"""Tier-2 ingest — Germany, Act on Copyright and Related Rights (UrhG).  DRAFT.

First Tier-2 jurisdiction. Source: the OFFICIAL English translation published by the German
Federal Ministry of Justice (gesetze-im-internet.de) — cleaner than WIPO Lex (PDF-only here).
It is a TRANSLATION, so version rows carry is_official_language=0 (the authentic language is
German) — surfaced in the UI. NO fake law: every section's text is from the fetched page.

Tier-2 is heterogeneous (each country: its own source + markup + numbering), so this parser is
Germany-specific; the DB-writer + provision model are the shared pattern from the other ingests.
Structure: Part/Division/Subdivision containers + `Section N<br/>title` + body <p> paragraphs;
letter-suffixed sections (20a, 60a…) fit the (sort_int, sort_suffix) ordinal.

Run:
    python src/store/ingest_de_urhg.py --db db/corpus.db --allow-corpus \
        --html spike/artifacts/de_urhg.html \
        --source-url https://www.gesetze-im-internet.de/englisch_urhg/englisch_urhg.html
"""
from __future__ import annotations

import argparse
import hashlib
import html as htmlmod
import os
import re
import sqlite3
from datetime import datetime, timezone

INSTRUMENT = dict(jurisdiction="DE", type="statute", official_citation="UrhG",
                  ext_id_scheme="NATIONAL", ext_id="de-urhg",
                  title="Act on Copyright and Related Rights (Urheberrechtsgesetz, UrhG)")

# Structural markers: <a name="pNNNN"></a> UNIT N <br/> Title </p>. German units → generic kinds.
KIND = {"Part": "part", "Division": "chapter", "Subdivision": "subchapter", "Section": "section"}
HEAD = re.compile(
    r'<a name="p\d+">(?:<!---->)?</a>\s*(Part|Division|Subdivision|Section)\s+(\d+[a-z]*)\b'
    r'\s*(?:<br\s*/?>\s*(.*?))?</p>', re.S)
NUM_RE = re.compile(r"^\s*(\d+)([A-Za-z]*)\s*$")


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _clean(frag: str) -> str:
    frag = re.sub(r'<a\b[^>]*>.*?</a>', ' ', frag, flags=re.S)   # drop anchors + TOC links
    frag = re.sub(r"<[^>]+>", " ", frag)
    frag = re.sub(r"\btable of contents\b", " ", frag, flags=re.I)
    return re.sub(r"\s+", " ", htmlmod.unescape(frag)).strip()


def ordinal(token: str, doc_index: int) -> tuple[int, str]:
    m = NUM_RE.match(token or "")
    return (int(m.group(1)), m.group(2).upper()) if m else (doc_index, "")


def parse(html_path: str) -> list[dict]:
    html = open(html_path, encoding="utf-8", errors="replace").read()
    heads = list(HEAD.finditer(html))
    records: list[dict] = []
    seen: dict[str, int] = {}
    container = {"part": None, "chapter": None, "subchapter": None}   # local ids

    def add(**kw) -> int:
        cit = kw["citation"]
        seen[cit] = seen.get(cit, 0) + 1
        if seen[cit] > 1:
            kw["citation"] = f"{cit} #{seen[cit]}"
        kw["local_id"] = len(records) + 1
        records.append(kw)
        return kw["local_id"]

    for i, m in enumerate(heads):
        unit, num, title = m.group(1), m.group(2), _clean(m.group(3) or "") or None
        kind = KIND[unit]
        si, su = ordinal(num, i)
        if kind == "section":
            body = _clean(html[m.end(): heads[i + 1].start() if i + 1 < len(heads) else m.end() + 4000])
            parent = container["subchapter"] or container["chapter"] or container["part"]
            add(parent_local=parent, kind="section", label=f"Section {num}", heading=title,
                sort_int=si, sort_suffix=su, role="enacting",
                citation=f"UrhG § {num}", content=body or None)
        else:  # container (Part / Division / Subdivision)
            cite = f"UrhG {unit} {num}"
            if kind == "part":
                container["chapter"] = container["subchapter"] = None
                parent = None
            elif kind == "chapter":
                container["subchapter"] = None
                parent = container["part"]
            else:
                parent = container["chapter"] or container["part"]
            lid = add(parent_local=parent, kind=kind, label=f"{unit} {num}", heading=title,
                      sort_int=si, sort_suffix=su, role="enacting", citation=cite, content=None)
            container[kind] = lid
    return records


# ── DB writers (idempotent) — shared pattern with the other ingests ─────────
def _require_migration(conn):
    if not conn.execute("SELECT name FROM sqlite_master WHERE name='provisions'").fetchone():
        raise SystemExit("target DB has no `provisions` table — apply migration 001 first")


def _upsert_instrument(conn) -> int:
    row = conn.execute("SELECT id FROM instruments WHERE jurisdiction=? AND ext_id_scheme=? AND ext_id=?",
                       (INSTRUMENT["jurisdiction"], INSTRUMENT["ext_id_scheme"], INSTRUMENT["ext_id"])).fetchone()
    if row:
        conn.execute("UPDATE instruments SET title=?, official_citation=?, last_updated_at=? WHERE id=?",
                     (INSTRUMENT["title"], INSTRUMENT["official_citation"], now_iso(), row[0]))
        return row[0]
    cur = conn.execute(
        "INSERT INTO instruments (jurisdiction, type, title, official_citation, ext_id, "
        "ext_id_scheme, status, first_seen_at, last_updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
        (INSTRUMENT["jurisdiction"], INSTRUMENT["type"], INSTRUMENT["title"],
         INSTRUMENT["official_citation"], INSTRUMENT["ext_id"], INSTRUMENT["ext_id_scheme"],
         "in_force", now_iso(), now_iso()))
    return cur.lastrowid


def _upsert_provision(conn, iid, parent_id, r) -> int:
    row = conn.execute("SELECT id FROM provisions WHERE instrument_id=? AND citation=?",
                       (iid, r["citation"])).fetchone()
    if row:
        conn.execute("UPDATE provisions SET parent_id=?, sort_int=?, sort_suffix=?, label=?, "
                     "heading=?, kind=?, role=? WHERE id=?",
                     (parent_id, r["sort_int"], r["sort_suffix"], r["label"], r["heading"],
                      r["kind"], r["role"], row[0]))
        return row[0]
    cur = conn.execute("INSERT INTO provisions (instrument_id, parent_id, sort_int, sort_suffix, "
                       "label, heading, kind, role, citation) VALUES (?,?,?,?,?,?,?,?,?)",
                       (iid, parent_id, r["sort_int"], r["sort_suffix"], r["label"], r["heading"],
                        r["kind"], r["role"], r["citation"]))
    return cur.lastrowid


def _store_version(conn, iid, provid, r, source_url, point_in_time) -> str:
    content = r["content"]
    digest = sha256(content)
    existing = conn.execute(
        "SELECT content_sha256 FROM versions WHERE instrument_id=? AND provision_id=? "
        "AND point_in_time IS ? AND language='en'", (iid, provid, point_in_time)).fetchone()
    outcome = "unchanged"
    if not existing or existing[0] != digest:
        conn.execute("UPDATE versions SET is_current=0 WHERE instrument_id=? AND provision_id=?",
                     (iid, provid))
        # OFFICIAL translation, but a translation: is_official_language=0 (authentic = German).
        cur = conn.execute(
            "INSERT INTO versions (instrument_id, provision_id, version_label, point_in_time, "
            "language, is_official_language, is_consolidated, is_authentic, content, "
            "content_sha256, source_url, retrieved_at, is_current) "
            "VALUES (?,?,?,?, 'en', 0, 1, 0, ?,?,?,?, 1)",
            (iid, provid, "gesetze-im-internet.de (EN translation)", point_in_time, content,
             digest, source_url, now_iso()))
        conn.execute("INSERT INTO versions_fts (rowid, title, citation, body) VALUES (?,?,?,?)",
                     (cur.lastrowid, "UrhG", r["citation"], content))
        outcome = "new"
    conn.execute("DELETE FROM provisions_fts WHERE rowid=?", (provid,))
    conn.execute("INSERT INTO provisions_fts (rowid, citation, heading, body) VALUES (?,?,?,?)",
                 (provid, r["citation"], r["heading"] or "", content))
    return outcome


def ingest(db_path, html_path, source_url, point_in_time=None, allow_corpus=False) -> dict:
    if os.path.basename(db_path) == "corpus.db" and not allow_corpus:
        raise SystemExit("refusing to write the live corpus.db (pass --allow-corpus).")
    records = parse(html_path)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    _require_migration(conn)
    iid = _upsert_instrument(conn)
    localmap: dict[int, int] = {}
    stats = {"provisions": 0, "sections": 0, "versions_new": 0, "versions_unchanged": 0}
    for r in records:
        parent_id = localmap.get(r["parent_local"]) if r["parent_local"] else None
        pid = _upsert_provision(conn, iid, parent_id, r)
        localmap[r["local_id"]] = pid
        stats["provisions"] += 1
        if r["kind"] == "section":
            stats["sections"] += 1
        if r["content"]:
            outcome = _store_version(conn, iid, pid, r, source_url, point_in_time)
            stats["versions_new" if outcome == "new" else "versions_unchanged"] += 1
    conn.commit()
    conn.close()
    stats["instrument_id"] = iid
    return stats


def main() -> None:
    ap = argparse.ArgumentParser(description="Ingest Germany UrhG (gesetze-im-internet.de EN) — draft.")
    ap.add_argument("--db", required=True)
    ap.add_argument("--html", required=True)
    ap.add_argument("--source-url", required=True)
    ap.add_argument("--point-in-time", default=None)
    ap.add_argument("--allow-corpus", action="store_true")
    a = ap.parse_args()
    s = ingest(a.db, a.html, a.source_url, a.point_in_time, a.allow_corpus)
    print(f"instrument #{s['instrument_id']}  Germany UrhG")
    print(f"  provisions : {s['provisions']}  (sections {s['sections']})")
    print(f"  versions   : new {s['versions_new']}, unchanged {s['versions_unchanged']} "
          f"(is_official_language=0 — English translation)")


if __name__ == "__main__":
    main()
