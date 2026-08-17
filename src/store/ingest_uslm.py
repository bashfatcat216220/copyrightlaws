"""Provision-aware ingest for USLM (US Code) — 17 U.S.C. slice.  DRAFT — FOR REVIEW.

Retrieval-first: a connector FETCHES the official OLRC USLM XML; this store step parses it
into a provision tree (per the parsing spike's rules) and versions the operative text at the
SECTION level. Writes instruments + provisions + versions + FTS. It NEVER originates text.

Re-runnable / idempotent: instruments keyed on (jurisdiction, ext_id_scheme, ext_id);
provisions on (instrument_id, citation); section versions dedup on content_sha256 — so
Title 17 can be re-parsed repeatedly without duplicating rows. Safe by construction: refuses
to write the live db/corpus.db unless --allow-corpus is passed, and requires migration 001
(the `provisions` table) to be present.

Run (against a scratch DB that already has schema.sql + migration 001 applied):
    python src/store/ingest_uslm.py --db /tmp/scratch.db --xml spike/artifacts/usc17.xml \
        --source-url https://uscode.house.gov/download/releasepoints/us/pl/119/102/xml_usc17@119-102.zip
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import sqlite3
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

# Levels that become provisions (title/subtitle are the instrument, not a provision).
LEVELS = {"part", "subpart", "chapter", "subchapter", "section", "subsection",
          "paragraph", "subparagraph", "clause", "subclause", "item", "subitem"}
CONTAINER_LEVELS = {"part", "subpart", "chapter", "subchapter"}
# Non-operative subtrees: USLM reproduces OTHER statutes' text inside notes/quotedContent.
SKIP = {"note", "notes", "quotedContent", "sourceCredit"}
NUM_RE = re.compile(r"^\s*§*\s*(\d+)([A-Za-z]*)\s*$")

USC_TITLE = "17"
INSTRUMENT = dict(jurisdiction="US", type="statute", official_citation="17 U.S.C.",
                  ext_id_scheme="USC", ext_id="t17")

# ── 1976 Act "Transitional and Supplementary Provisions" (Pub. L. 94-553, Title I) ──
# §§ 102–115 are OPERATIVE UNCODIFIED law (effective dates, savings, lost/expired
# copyrights, appropriations, separability). USLM carries them NOT in the codified
# section tree but reproduced inside statutory <note>s — the actual statutory words sit
# in a <quotedContent origin="/us/pl/94/553/tI/sNNN">. `SKIP` (above) drops ALL notes to
# keep the ~625 editorial notes out of the operative body; we do NOT touch that. Instead a
# SEPARATE, surgical pass (transitional_records) targets ONLY these §§102–115 by their
# `origin` attribute — the machine-readable provenance selector, robust across refreshes.
#
# Scoped by exact origin match so nothing adjacent bleeds in: the run is 102..115 but this
# release only reproduces 102,103,104,106,107,108,109,110,112,114,115 (105/111/113 are not
# carried in the artifact at all — no fake law: we capture what is present, nothing more).
TRANS_ORIGIN_RE = re.compile(r"^/us/pl/94/553/tI/s(1(?:0[2-9]|1[0-5]))$")
TRANS_CONTAINER_CITE = "17 U.S.C. Transitional and Supplementary Provisions"
TRANS_CONTAINER_HEADING = ("Transitional and Supplementary Provisions "
                           "(Pub. L. 94-553, Title I, §§ 102–115)")
TRANS_SORT_BASE = 90000  # file AFTER the codified body (§§101–1511) in provision order


def local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _num(el) -> str | None:
    n = el.find("./{*}num")
    if n is None:
        return None
    return n.get("value") or " ".join("".join(n.itertext()).split())


def _heading(el) -> str | None:
    h = el.find("./{*}heading")
    return " ".join("".join(h.itertext()).split()) if h is not None else None


def ordinal(num_val: str | None, doc_index: int) -> tuple[int, str]:
    """(sort_int, sort_suffix) — number-derived for numbered levels (survives §106A/§296ZA);
    alpha/roman levels (subsection 'a', clause 'iv') fall back to document order, which is
    authoritative from the single USLM fetch. sort_suffix compared under BINARY collation."""
    m = NUM_RE.match(num_val or "")
    if m:
        return int(m.group(1)), m.group(2).upper()
    return doc_index, ""


def _operative_text(el) -> str:
    """Full operative text of a section subtree, skipping quoted/note material."""
    parts: list[str] = []

    def rec(e):
        if local(e.tag) in SKIP:
            return
        if e.text and e.text.strip():
            parts.append(e.text.strip())
        for c in e:
            rec(c)
            if c.tail and c.tail.strip():
                parts.append(c.tail.strip())

    rec(el)
    return " ".join(parts)


def parse(xml_path: str) -> tuple[str, list[dict]]:
    """Return (instrument_title, provision_records). Records are in document order,
    parents before children, each with a local_id and parent_local for wiring."""
    root = ET.parse(xml_path).getroot()
    title_heading = None
    for el in root.iter():
        if local(el.tag) == "title":
            title_heading = _heading(el)
            break
    records: list[dict] = []

    def add(**kw) -> int:
        kw["local_id"] = len(records) + 1
        records.append(kw)
        return kw["local_id"]

    def walk(el, parent_local, sec_cite, subpath):
        sib = 0
        for c in el:
            name = local(c.tag)
            if name in SKIP:
                continue
            if name in LEVELS:
                sib += 1
                num = _num(c)
                heading = _heading(c)
                si, su = ordinal(num, sib)
                if name in CONTAINER_LEVELS:
                    cite = f"17 U.S.C. ch. {num}" if name == "chapter" else f"17 U.S.C. {name} {num}"
                    label = f"{name.capitalize()} {num}"
                    lid = add(parent_local=parent_local, kind=name, label=label, heading=heading,
                              sort_int=si, sort_suffix=su, role="enacting", citation=cite, content=None)
                    walk(c, lid, None, [])
                elif name == "section":
                    cite = f"17 U.S.C. § {num}"
                    lid = add(parent_local=parent_local, kind="section", label=f"§ {num}",
                              heading=heading, sort_int=si, sort_suffix=su, role="enacting",
                              citation=cite, content=_operative_text(c))
                    walk(c, lid, cite, [])
                else:  # subsection / paragraph / clause / ... — addressable, versioned at section
                    newsub = subpath + [num]
                    base = sec_cite or "17 U.S.C. §"
                    cite = base + "".join(f"({x})" for x in newsub)
                    lid = add(parent_local=parent_local, kind=name, label=f"({num})", heading=heading,
                              sort_int=si, sort_suffix=su, role="enacting", citation=cite, content=None)
                    walk(c, lid, sec_cite, newsub)
            else:
                walk(c, parent_local, sec_cite, subpath)

    walk(root, None, None, [])
    _append_transitional(root, records, add)
    return (title_heading or "Copyrights"), records


def _note_text(note_el) -> str:
    """Full verbatim text of a statutory <note>: the introductory credit line
    ('Pub. L. 94-553, title I, § NNN, Oct. 19, 1976, 90 Stat. …, provided that:') AND the
    reproduced statutory words inside <quotedContent>. Unlike _operative_text this does NOT
    apply SKIP (which exists to keep notes/quoted material OUT of the codified body) — here
    the note IS the operative uncodified provision, captured verbatim. The note's own
    <heading> is stored separately as the provision heading, so it is excluded from the body."""
    parts: list[str] = []

    def rec(e):
        if local(e.tag) == "heading":
            return  # captured as the provision heading, not repeated in the body
        if e.text and e.text.strip():
            parts.append(e.text.strip())
        for c in e:
            rec(c)
            if c.tail and c.tail.strip():
                parts.append(c.tail.strip())

    rec(note_el)
    return " ".join(parts)


def _append_transitional(root, records: list[dict], add) -> None:
    """SURGICAL capture of Pub. L. 94-553, Title I, §§ 102–115 (the 1976 Act transitional
    and supplementary provisions) — operative uncodified law. Selects ONLY <note>s whose
    reproduced text carries origin="/us/pl/94/553/tI/s1{02..15}"; captures each such note
    verbatim as a schedule_para. Leaves the codified body and every other note untouched."""
    parents = {c: p for p in root.iter() for c in p}
    seen: set[str] = set()
    found: list[tuple[int, str, str, str]] = []  # (sec, num, heading, body)
    for el in root.iter():
        if local(el.tag) != "quotedContent":
            continue
        m = TRANS_ORIGIN_RE.match(el.get("origin", "") or "")
        if not m:
            continue
        num = m.group(1)
        if num in seen:            # one provision per section (idempotent within a parse)
            continue
        # walk up to the enclosing statutory <note> (its intro line + quoted words = the text)
        note = el
        while note is not None and local(note.tag) != "note":
            note = parents.get(note)
        if note is None:
            continue
        seen.add(num)
        h = note.find("./{*}heading")
        heading = " ".join("".join(h.itertext()).split()) if h is not None else None
        found.append((int(num), num, heading, _note_text(note)))

    if not found:
        return
    found.sort(key=lambda t: t[0])
    cid = add(parent_local=None, kind="schedule", label="Transitional and Supplementary Provisions",
              heading=TRANS_CONTAINER_HEADING, sort_int=TRANS_SORT_BASE, sort_suffix="",
              role="schedule", citation=TRANS_CONTAINER_CITE, content=None)
    for sec, num, heading, body in found:
        add(parent_local=cid, kind="schedule_para", label=f"§ {num}", heading=heading,
            sort_int=TRANS_SORT_BASE + sec, sort_suffix="", role="schedule",
            citation=f"17 U.S.C. Trans. & Supp. Prov. § {num}", content=body or None)


# ── DB writers (idempotent) ─────────────────────────────────────────────────
def _require_migration(conn: sqlite3.Connection) -> None:
    if not conn.execute("SELECT name FROM sqlite_master WHERE name='provisions'").fetchone():
        raise SystemExit("target DB has no `provisions` table — apply "
                         "db/migrations/001_provisions_rebuild.sql first")


def _upsert_instrument(conn, title) -> int:
    row = conn.execute(
        "SELECT id FROM instruments WHERE jurisdiction=? AND ext_id_scheme=? AND ext_id=?",
        (INSTRUMENT["jurisdiction"], INSTRUMENT["ext_id_scheme"], INSTRUMENT["ext_id"])).fetchone()
    if row:
        conn.execute("UPDATE instruments SET title=?, official_citation=?, last_updated_at=? WHERE id=?",
                     (title, INSTRUMENT["official_citation"], now_iso(), row[0]))
        return row[0]
    cur = conn.execute(
        "INSERT INTO instruments (jurisdiction, type, title, official_citation, ext_id, "
        "ext_id_scheme, status, first_seen_at, last_updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
        (INSTRUMENT["jurisdiction"], INSTRUMENT["type"], title, INSTRUMENT["official_citation"],
         INSTRUMENT["ext_id"], INSTRUMENT["ext_id_scheme"], "in_force", now_iso(), now_iso()))
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


def _store_section_version(conn, iid, provid, r, source_url, point_in_time) -> str:
    # Idempotent BY CONTENT (matches _common): re-fetch only versions a changed section; on
    # change, update the pit slot in place or insert new.
    content = r["content"]
    digest = sha256(content)
    cur = conn.execute("SELECT content_sha256 FROM versions WHERE instrument_id=? AND "
                       "provision_id=? AND is_current=1", (iid, provid)).fetchone()
    outcome = "unchanged"
    if not cur or cur[0] != digest:
        conn.execute("UPDATE versions SET is_current=0 WHERE instrument_id=? AND provision_id=?",
                     (iid, provid))
        slot = conn.execute("SELECT id FROM versions WHERE instrument_id=? AND provision_id=? "
                            "AND point_in_time IS ? AND language='en'",
                            (iid, provid, point_in_time)).fetchone()
        if slot:
            conn.execute("UPDATE versions SET content=?, content_sha256=?, source_url=?, "
                         "retrieved_at=?, is_current=1 WHERE id=?",
                         (content, digest, source_url, now_iso(), slot[0]))
            vid = slot[0]
            conn.execute("DELETE FROM versions_fts WHERE rowid=?", (vid,))
        else:
            c2 = conn.execute(
                "INSERT INTO versions (instrument_id, provision_id, version_label, point_in_time, "
                "language, content, content_sha256, source_url, retrieved_at, is_current) "
                "VALUES (?,?,?,?, 'en', ?,?,?,?, 1)",
                (iid, provid, "OLRC USLM", point_in_time, content, digest, source_url, now_iso()))
            vid = c2.lastrowid
        conn.execute("INSERT INTO versions_fts (rowid, title, citation, body) VALUES (?,?,?,?)",
                     (vid, "17 U.S.C.", r["citation"], content))
        outcome = "new"
    conn.execute("DELETE FROM provisions_fts WHERE rowid=?", (provid,))
    conn.execute("INSERT INTO provisions_fts (rowid, citation, heading, body) VALUES (?,?,?,?)",
                 (provid, r["citation"], r["heading"] or "", content))
    return outcome


def ingest(db_path: str, xml_path: str, source_url: str,
           point_in_time: str | None = None, allow_corpus: bool = False) -> dict:
    if os.path.basename(db_path) == "corpus.db" and not allow_corpus:
        raise SystemExit("refusing to write the live corpus.db (schema is pending sign-off). "
                         "Pass --allow-corpus only after the migration is approved.")
    title, records = parse(xml_path)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    _require_migration(conn)
    iid = _upsert_instrument(conn, title)
    localmap: dict[int, int] = {}
    stats = {"provisions": 0, "sections": 0, "versions_new": 0, "versions_unchanged": 0}
    for r in records:
        parent_id = localmap.get(r["parent_local"]) if r["parent_local"] else None
        pid = _upsert_provision(conn, iid, parent_id, r)
        localmap[r["local_id"]] = pid
        stats["provisions"] += 1
        if r["content"]:
            stats["sections"] += 1
            outcome = _store_section_version(conn, iid, pid, r, source_url, point_in_time)
            stats["versions_new" if outcome == "new" else "versions_unchanged"] += 1
    conn.commit()
    conn.close()
    stats.update(instrument_id=iid, title=title)
    return stats


def main() -> None:
    ap = argparse.ArgumentParser(description="Ingest 17 U.S.C. USLM into a provisions DB (draft).")
    ap.add_argument("--db", required=True, help="target SQLite DB (must have migration 001 applied)")
    ap.add_argument("--xml", required=True, help="OLRC USLM usc17.xml")
    ap.add_argument("--source-url", required=True, help="official source URL (provenance)")
    ap.add_argument("--point-in-time", default=None, help="ISO date the text is in force from")
    ap.add_argument("--allow-corpus", action="store_true", help="permit writing the live corpus.db")
    a = ap.parse_args()
    s = ingest(a.db, a.xml, a.source_url, a.point_in_time, a.allow_corpus)
    print(f"instrument #{s['instrument_id']}  {s['title']} (17 U.S.C.)")
    print(f"  provisions upserted : {s['provisions']}")
    print(f"  sections versioned  : {s['sections']}  (new {s['versions_new']}, "
          f"unchanged {s['versions_unchanged']})")


if __name__ == "__main__":
    main()
