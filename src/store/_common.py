"""Shared ingest machinery for the provisions model — the writer half of every connector.

A per-source ingest is now just: (1) an INSTRUMENT dict, (2) a `parse()` that builds a
`RecordSet` of provisions, (3) a `main()` that calls `run_ingest`. Everything below — the
DB upserts, per-provision versioning, FTS sync, idempotency, and the corpus.db guard — is
shared, so a new jurisdiction is a parser, not boilerplate. NEVER originates text.

Record contract (what `RecordSet.add` stores; the driver wires parent_local → db id):
  local_id, parent_local, kind, label, heading, sort_int, sort_suffix, role, citation, content
Provisions with `content` get a version + FTS row (the citable/versioned unit, e.g. a section
or article); deeper nodes are addressable but shareless.
"""
from __future__ import annotations

import hashlib
import os
import re
import sqlite3
from datetime import datetime, timezone

_NUM_RE = re.compile(r"^\s*[§(]?\s*(\d+)([A-Za-z]*)\)?\.?\s*$")


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def ordinal(token: str, doc_index: int) -> tuple[int, str]:
    """(sort_int, sort_suffix): '6bis'/'20a'/'106A' → (n, SUFFIX) so 6<6bis<7; non-numeric
    tokens (roman 'IV', alpha 'k') fall back to document order. sort_suffix is compared under
    the column's pinned BINARY collation."""
    m = _NUM_RE.match(token or "")
    return (int(m.group(1)), m.group(2).upper()) if m else (doc_index, "")


# A provision is REPEALED when its whole text is the source's own tombstone notice — "Deleted",
# "[Repealed …]", "(repealed)", "Omitted", "abrogé/derogado/abrogato/vervallen/weggefallen",
# "VETOED", or CDPA's row-of-dots. Detected from the notice itself (grounded), never invented.
_REPEAL_RE = re.compile(
    r"^\s*[\(\[【]?\s*(deleted|repealed|omitted|renumbered|abrog|derogad|abrogat|soppress|"
    r"se deroga|revogad|vetad|vetoed|vervallen|weggefallen|aufgehoben)", re.I)


def is_repealed(content: str | None, heading: str | None) -> bool:
    for t in (heading, content):
        if t and _REPEAL_RE.match(t.strip()) and len(t.strip()) < 400:
            return True
    if content and content.strip() and set(content.strip()) <= set(". "):   # CDPA dots-tombstone
        return True
    return False


class RecordSet:
    """Ordered provision records with a deterministic citation-uniqueness guard."""

    def __init__(self) -> None:
        self.records: list[dict] = []
        self._seen: dict[str, int] = {}

    def add(self, *, kind: str, label: str, sort_int: int, citation: str,
            parent_local: int | None = None, heading: str | None = None,
            sort_suffix: str = "", role: str = "enacting", content: str | None = None,
            status: str | None = None) -> int:
        self._seen[citation] = self._seen.get(citation, 0) + 1
        if self._seen[citation] > 1:                       # collision → deterministic #n suffix
            citation = f"{citation} #{self._seen[citation]}"
        lid = len(self.records) + 1
        # status: explicit override, else auto-detect a repeal tombstone from the notice text.
        st = status or ("repealed" if is_repealed(content, heading) else "in_force")
        self.records.append(dict(local_id=lid, parent_local=parent_local, kind=kind, label=label,
                                 heading=heading, sort_int=sort_int, sort_suffix=sort_suffix,
                                 role=role, citation=citation, content=content, status=st))
        return lid


def require_migration(conn: sqlite3.Connection) -> None:
    if not conn.execute("SELECT name FROM sqlite_master WHERE name='provisions'").fetchone():
        raise SystemExit("target DB has no `provisions` table — apply migration 001 first")


def upsert_instrument(conn: sqlite3.Connection, inst: dict) -> int:
    row = conn.execute("SELECT id FROM instruments WHERE jurisdiction=? AND ext_id_scheme=? AND ext_id=?",
                       (inst["jurisdiction"], inst["ext_id_scheme"], inst["ext_id"])).fetchone()
    if row:
        conn.execute("UPDATE instruments SET title=?, official_citation=?, type=?, "
                     "last_updated_at=? WHERE id=?",
                     (inst["title"], inst["official_citation"], inst["type"], now_iso(), row[0]))
        return row[0]
    cur = conn.execute(
        "INSERT INTO instruments (jurisdiction, type, title, official_citation, ext_id, "
        "ext_id_scheme, status, first_seen_at, last_updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
        (inst["jurisdiction"], inst["type"], inst["title"], inst["official_citation"],
         inst["ext_id"], inst["ext_id_scheme"], inst.get("status", "in_force"),
         now_iso(), now_iso()))
    return cur.lastrowid


def _upsert_provision(conn, iid, parent_id, r) -> int:
    row = conn.execute("SELECT id FROM provisions WHERE instrument_id=? AND citation=?",
                       (iid, r["citation"])).fetchone()
    st = r.get("status") or "in_force"
    if row:
        conn.execute("UPDATE provisions SET parent_id=?, sort_int=?, sort_suffix=?, label=?, "
                     "heading=?, kind=?, role=?, status=? WHERE id=?",
                     (parent_id, r["sort_int"], r["sort_suffix"], r["label"], r["heading"],
                      r["kind"], r["role"], st, row[0]))
        return row[0]
    cur = conn.execute("INSERT INTO provisions (instrument_id, parent_id, sort_int, sort_suffix, "
                       "label, heading, kind, role, citation, status) VALUES (?,?,?,?,?,?,?,?,?,?)",
                       (iid, parent_id, r["sort_int"], r["sort_suffix"], r["label"], r["heading"],
                        r["kind"], r["role"], r["citation"], st))
    return cur.lastrowid


def _store_version(conn, iid, provid, r, *, source_url, point_in_time, fts_title, version_label,
                   is_authentic, is_consolidated, is_official_language) -> str:
    """Version a provision's text. Idempotent BY CONTENT: if the current version's text is
    unchanged, it's a no-op — so a re-fetch (auto-refresh) only creates a new version for
    provisions that actually changed. On a change: demote the current, then either update the
    same point-in-time slot in place or insert a new one (never violates the pit UNIQUE)."""
    content = r["content"]
    digest = sha256(content)
    cur = conn.execute("SELECT content_sha256 FROM versions WHERE instrument_id=? AND "
                       "provision_id=? AND is_current=1", (iid, provid)).fetchone()
    outcome = "unchanged"
    if not cur or cur[0] != digest:                        # content differs from current (or first)
        conn.execute("UPDATE versions SET is_current=0 WHERE instrument_id=? AND provision_id=?",
                     (iid, provid))
        slot = conn.execute("SELECT id FROM versions WHERE instrument_id=? AND provision_id=? "
                            "AND point_in_time IS ? AND language='en'",
                            (iid, provid, point_in_time)).fetchone()
        if slot:                                           # re-version at an existing pit slot → update in place
            conn.execute("UPDATE versions SET version_label=?, content=?, content_sha256=?, "
                         "source_url=?, retrieved_at=?, is_official_language=?, is_consolidated=?, "
                         "is_authentic=?, is_current=1 WHERE id=?",
                         (version_label, content, digest, source_url, now_iso(),
                          is_official_language, is_consolidated, is_authentic, slot[0]))
            vid = slot[0]
            conn.execute("DELETE FROM versions_fts WHERE rowid=?", (vid,))
        else:
            c2 = conn.execute(
                "INSERT INTO versions (instrument_id, provision_id, version_label, point_in_time, "
                "language, is_official_language, is_consolidated, is_authentic, content, "
                "content_sha256, source_url, retrieved_at, is_current) "
                "VALUES (?,?,?,?, 'en', ?, ?, ?, ?,?,?,?, 1)",
                (iid, provid, version_label, point_in_time, is_official_language, is_consolidated,
                 is_authentic, content, digest, source_url, now_iso()))
            vid = c2.lastrowid
        conn.execute("INSERT INTO versions_fts (rowid, title, citation, body) VALUES (?,?,?,?)",
                     (vid, fts_title, r["citation"], content))
        outcome = "new"
    conn.execute("DELETE FROM provisions_fts WHERE rowid=?", (provid,))
    conn.execute("INSERT INTO provisions_fts (rowid, citation, heading, body) VALUES (?,?,?,?)",
                 (provid, r["citation"], r["heading"] or "", content))
    return outcome


def store_pinned_version(conn, iid: int, provid: int, citation: str, content: str, *,
                         source_url: str, point_in_time: str, version_label: str,
                         fts_title: str, is_authentic: int, is_consolidated: int,
                         is_official_language: int = 1) -> str:
    """ADDITIVE pinned layer (Wave D, 2f): store a historical/baseline MANIFESTATION of a
    provision at its own point_in_time WITHOUT touching is_current — the working text (eCFR /
    EU consolidated) keeps the reader; the pinned layer lands in History + search. Contrast
    `_store_version`, which promotes to current. Idempotent by content at the pit slot; a
    re-run after a parser fix updates the slot in place. REFUSES a slot owned by the live
    current layer (that would clobber the working text — pick a different point_in_time).
    NEVER originates text; requires a non-NULL point_in_time (a pinned layer without a date
    is meaningless)."""
    if not point_in_time:
        raise SystemExit("store_pinned_version requires an explicit point_in_time")
    if not content:
        raise SystemExit(f"refusing to store an empty pinned version for {citation}")
    digest = sha256(content)
    slot = conn.execute(
        "SELECT id, content_sha256, is_current FROM versions WHERE instrument_id=? AND "
        "provision_id=? AND point_in_time IS ? AND language='en'",
        (iid, provid, point_in_time)).fetchone()
    if slot and slot[2]:
        raise SystemExit(f"pit slot {point_in_time} for {citation} holds the CURRENT working "
                         "version — refusing to overwrite (choose a different point_in_time)")
    if slot and slot[1] == digest:
        return "unchanged"
    if slot:                                   # re-run after a parser fix → update in place
        conn.execute("UPDATE versions SET version_label=?, content=?, content_sha256=?, "
                     "source_url=?, retrieved_at=?, is_official_language=?, is_consolidated=?, "
                     "is_authentic=? WHERE id=?",
                     (version_label, content, digest, source_url, now_iso(),
                      is_official_language, is_consolidated, is_authentic, slot[0]))
        vid = slot[0]
        conn.execute("DELETE FROM versions_fts WHERE rowid=?", (vid,))
    else:
        cur = conn.execute(
            "INSERT INTO versions (instrument_id, provision_id, version_label, point_in_time, "
            "language, is_official_language, is_consolidated, is_authentic, content, "
            "content_sha256, source_url, retrieved_at, is_current) "
            "VALUES (?,?,?,?, 'en', ?, ?, ?, ?,?,?,?, 0)",
            (iid, provid, version_label, point_in_time, is_official_language, is_consolidated,
             is_authentic, content, digest, source_url, now_iso()))
        vid = cur.lastrowid
    conn.execute("INSERT INTO versions_fts (rowid, title, citation, body) VALUES (?,?,?,?)",
                 (vid, fts_title, citation, content))
    return "new"


def run_ingest(db_path: str, inst: dict, rs: RecordSet, source_url: str, *,
               point_in_time: str | None = None, allow_corpus: bool = False,
               is_authentic: int = 1, is_consolidated: int = 1, is_official_language: int = 1,
               version_label: str = "", fts_title: str | None = None) -> dict:
    """Drive an idempotent ingest of `rs` into `db_path`. Refuses the live corpus.db unless
    allow_corpus. Flags default to authentic/official — override per source (EU consolidated:
    is_authentic=0; translations: is_official_language=0)."""
    if os.path.basename(db_path) == "corpus.db" and not allow_corpus:
        raise SystemExit("refusing to write the live corpus.db — pass allow_corpus=True "
                         "(only after the migration is approved).")
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 15000")           # tolerate a concurrent writer
    require_migration(conn)
    iid = upsert_instrument(conn, inst)
    localmap: dict[int, int] = {}
    stats: dict = {"provisions": 0, "versioned": 0, "versions_new": 0, "versions_unchanged": 0,
                   "by_kind": {}}
    for r in rs.records:
        parent_id = localmap.get(r["parent_local"]) if r["parent_local"] else None
        pid = _upsert_provision(conn, iid, parent_id, r)
        localmap[r["local_id"]] = pid
        stats["provisions"] += 1
        stats["by_kind"][r["kind"]] = stats["by_kind"].get(r["kind"], 0) + 1
        if r["content"]:
            outcome = _store_version(conn, iid, pid, r, source_url=source_url,
                                     point_in_time=point_in_time,
                                     fts_title=fts_title or inst["official_citation"],
                                     version_label=version_label, is_authentic=is_authentic,
                                     is_consolidated=is_consolidated,
                                     is_official_language=is_official_language)
            stats["versioned"] += 1
            stats["versions_new" if outcome == "new" else "versions_unchanged"] += 1
    conn.commit()
    conn.close()
    stats["instrument_id"] = iid
    return stats
