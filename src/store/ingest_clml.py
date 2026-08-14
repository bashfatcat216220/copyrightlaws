"""Provision-aware ingest for CLML (legislation.gov.uk) — CDPA 1988 slice.  DRAFT — FOR REVIEW.

Second source shape after USLM. Exercises the Body-vs-Schedule role split the spike found:
Body `P1`s are operative sections (role='enacting'); Schedule `P1`s are operative too but a
separate class (kind='schedule_para', role='schedule'); `BlockAmendment`/`Quotation` reproduce
OTHER Acts' words and are skipped. Same idempotency + corpus.db guard as ingest_uslm.

Run against a scratch/demo DB that has migration 001 applied:
    python src/store/ingest_clml.py --db db/corpus-demo.db --xml spike/artifacts/cdpa.xml \
        --source-url https://www.legislation.gov.uk/ukpga/1988/48/data.xml
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import sqlite3
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

SKIP = {"BlockAmendment", "Quotation"}          # reproduce OTHER instruments' words
PLEVEL = {"P2": "subsection", "P3": "paragraph", "P4": "subparagraph", "P5": "clause", "P6": "subclause"}
NUM_RE = re.compile(r"^\s*(\d+)([A-Za-z]*)\s*$")

INSTRUMENT = dict(jurisdiction="GB", type="statute", official_citation="CDPA 1988",
                  ext_id_scheme="ELI", ext_id="ukpga/1988/48",
                  title="Copyright, Designs and Patents Act 1988")


def local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _txt(el) -> str | None:
    return " ".join("".join(el.itertext()).split()) if el is not None else None


def _child(el, name):
    return el.find(f"./{{*}}{name}")


def ordinal(num_val: str | None, doc_index: int) -> tuple[int, str]:
    m = NUM_RE.match(num_val or "")
    if m:
        return int(m.group(1)), m.group(2).upper()
    return doc_index, ""


def _operative_text(el) -> str:
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
    root = ET.parse(xml_path).getroot()
    records: list[dict] = []
    seen: dict[str, int] = {}          # deterministic citation-uniqueness guard

    def add(**kw) -> int:
        # KNOWN REFINEMENT: some CDPA schedule paragraphs still collide on citation (schedule
        # sub-structure the pinpoint doesn't yet capture). Disambiguate deterministically so a
        # collision never overwrites another provision's text; same input → same suffixes →
        # idempotent. Real fix later: full schedule-part pinpointing in the citation.
        cit = kw.get("citation")
        if cit is not None:
            seen[cit] = seen.get(cit, 0) + 1
            if seen[cit] > 1:
                kw["citation"] = f"{cit} #{seen[cit]}"
        kw["local_id"] = len(records) + 1
        records.append(kw)
        return kw["local_id"]

    def walk(el, parent_local, container_cite, sec_cite, subpath, group_title, in_sched, sched_no):
        sib = 0
        for c in el:
            name = local(c.tag)
            if name in SKIP:
                continue
            if name in ("Part", "Chapter"):
                # A Part/Chapter can appear inside a Schedule (CDPA Sch. 1 has Parts) — PRESERVE
                # the schedule context and make the citation container-relative, else the
                # schedule's paragraphs get misclassified as Body sections and collide.
                sib += 1
                kind = name.lower()
                label = _txt(_child(c, "Number")) or f"{name} {sib}"
                cite = f"{container_cite or 'CDPA 1988'} {label}"
                si, su = ordinal(re.sub(r"[^0-9]", "", label), sib)
                role = "schedule" if in_sched else "enacting"
                lid = add(parent_local=parent_local, kind=kind, label=label,
                          heading=_txt(_child(c, "Title")), sort_int=si, sort_suffix=su,
                          role=role, citation=cite, content=None)
                walk(c, lid, cite, None, [], None, in_sched, sched_no)
            elif name == "Schedule":
                sib += 1
                num = (_txt(_child(c, "Number")) or f"SCHEDULE {sib}").replace("SCHEDULE", "").strip()
                label = f"Schedule {num}"
                cite = f"CDPA 1988 {label}"
                si, su = ordinal(num, sib)
                heading = _txt(c.find(".//{*}Title"))
                lid = add(parent_local=parent_local, kind="schedule", label=label, heading=heading,
                          sort_int=si, sort_suffix=su, role="schedule", citation=cite, content=None)
                walk(c, lid, cite, None, [], None, True, num)
            elif name == "P1group":
                walk(c, parent_local, container_cite, sec_cite, subpath,
                     _txt(_child(c, "Title")), in_sched, sched_no)
            elif name == "P1":
                sib += 1
                # normalize the section number — some CDPA point-in-time XML carries a trailing
                # dot on Pnumber ("205B."), which forked s.205B into a duplicate provision and
                # masked its change-monitor alert. Strip it so the citation is stable across snapshots.
                num = (_txt(_child(c, "Pnumber")) or "").rstrip(". ") or None
                si, su = ordinal(num, sib)
                if in_sched:
                    # container_cite is the Schedule (or Schedule+Part) — keeps paragraph
                    # numbers unique when a schedule restarts numbering across its Parts.
                    cite = f"{container_cite or 'CDPA 1988 Sch. ' + str(sched_no)} para. {num}"
                    lid = add(parent_local=parent_local, kind="schedule_para", label=f"para. {num}",
                              heading=group_title, sort_int=si, sort_suffix=su, role="schedule",
                              citation=cite, content=_operative_text(c))
                else:
                    cite = f"CDPA 1988 s. {num}"
                    lid = add(parent_local=parent_local, kind="section", label=f"s. {num}",
                              heading=group_title, sort_int=si, sort_suffix=su, role="enacting",
                              citation=cite, content=_operative_text(c))
                walk(c, lid, container_cite, cite, [], None, in_sched, sched_no)
            elif name in PLEVEL:
                sib += 1
                num = (_txt(_child(c, "Pnumber")) or "").rstrip(". ") or None
                si, su = ordinal(num, sib)
                newsub = subpath + [num]
                cite = (sec_cite or "CDPA 1988 s.") + "".join(f"({x})" for x in newsub)
                lid = add(parent_local=parent_local, kind=PLEVEL[name], label=f"({num})",
                          heading=None, sort_int=si, sort_suffix=su,
                          role="schedule" if in_sched else "enacting", citation=cite, content=None)
                walk(c, lid, container_cite, sec_cite, newsub, None, in_sched, sched_no)
            else:
                walk(c, parent_local, container_cite, sec_cite, subpath, group_title, in_sched, sched_no)

    walk(root, None, None, None, [], None, False, None)
    return INSTRUMENT["title"], records


# ── DB writers (idempotent) — same contract as ingest_uslm ──────────────────
def _require_migration(conn):
    if not conn.execute("SELECT name FROM sqlite_master WHERE name='provisions'").fetchone():
        raise SystemExit("target DB has no `provisions` table — apply migration 001 first")


def _upsert_instrument(conn, title) -> int:
    row = conn.execute("SELECT id FROM instruments WHERE jurisdiction=? AND ext_id_scheme=? AND ext_id=?",
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


def _store_version(conn, iid, provid, r, source_url, point_in_time) -> str:
    # Idempotent BY CONTENT (matches _common): a re-fetch only versions a provision if its text
    # differs from the current version; on change, update the pit slot in place or insert new.
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
                (iid, provid, "legislation.gov.uk", point_in_time, content, digest, source_url, now_iso()))
            vid = c2.lastrowid
        conn.execute("INSERT INTO versions_fts (rowid, title, citation, body) VALUES (?,?,?,?)",
                     (vid, "CDPA 1988", r["citation"], content))
        outcome = "new"
    conn.execute("DELETE FROM provisions_fts WHERE rowid=?", (provid,))
    conn.execute("INSERT INTO provisions_fts (rowid, citation, heading, body) VALUES (?,?,?,?)",
                 (provid, r["citation"], r["heading"] or "", content))
    return outcome


def ingest(db_path, xml_path, source_url, point_in_time=None, allow_corpus=False) -> dict:
    if os.path.basename(db_path) == "corpus.db" and not allow_corpus:
        raise SystemExit("refusing to write the live corpus.db (schema pending sign-off). "
                         "Pass --allow-corpus only after the migration is approved.")
    title, records = parse(xml_path)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    _require_migration(conn)
    iid = _upsert_instrument(conn, title)
    localmap: dict[int, int] = {}
    stats = {"provisions": 0, "sections": 0, "schedule_paras": 0, "versions_new": 0, "versions_unchanged": 0}
    for r in records:
        parent_id = localmap.get(r["parent_local"]) if r["parent_local"] else None
        pid = _upsert_provision(conn, iid, parent_id, r)
        localmap[r["local_id"]] = pid
        stats["provisions"] += 1
        if r["kind"] == "section":
            stats["sections"] += 1
        elif r["kind"] == "schedule_para":
            stats["schedule_paras"] += 1
        if r["content"]:
            outcome = _store_version(conn, iid, pid, r, source_url, point_in_time)
            stats["versions_new" if outcome == "new" else "versions_unchanged"] += 1
    conn.commit()
    conn.close()
    stats.update(instrument_id=iid, title=title)
    return stats


def main() -> None:
    ap = argparse.ArgumentParser(description="Ingest CDPA 1988 CLML into a provisions DB (draft).")
    ap.add_argument("--db", required=True)
    ap.add_argument("--xml", required=True)
    ap.add_argument("--source-url", required=True)
    ap.add_argument("--point-in-time", default=None)
    ap.add_argument("--allow-corpus", action="store_true")
    a = ap.parse_args()
    s = ingest(a.db, a.xml, a.source_url, a.point_in_time, a.allow_corpus)
    print(f"instrument #{s['instrument_id']}  {s['title']} (CDPA 1988)")
    print(f"  provisions upserted   : {s['provisions']}")
    print(f"  Body sections         : {s['sections']}")
    print(f"  Schedule paragraphs   : {s['schedule_paras']}  (role='schedule', separate class)")
    print(f"  versions              : new {s['versions_new']}, unchanged {s['versions_unchanged']}")


if __name__ == "__main__":
    main()
