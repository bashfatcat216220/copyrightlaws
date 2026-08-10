"""Store layer: canonicalize a FetchedVersion into instruments + versions + FTS.

This is the ONLY writer of instrument/version rows. It computes content_sha256 (the change
key), upserts the instrument identity, inserts a new version when the text changed, flips
is_current, and syncs the FTS row. A connector never touches the DB directly.
"""
from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime, timezone

from connectors.base import FetchedVersion


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _upsert_instrument(conn: sqlite3.Connection, fv: FetchedVersion) -> int:
    row = conn.execute(
        "SELECT id FROM instruments WHERE jurisdiction=? AND ext_id_scheme IS ? AND ext_id IS ?",
        (fv.jurisdiction, fv.ext_id_scheme, fv.ext_id),
    ).fetchone()
    if row:
        conn.execute("UPDATE instruments SET title=?, official_citation=?, status=?, "
                     "last_updated_at=? WHERE id=?",
                     (fv.title, fv.official_citation, fv.status, now_iso(), row["id"]))
        return row["id"]
    cur = conn.execute(
        "INSERT INTO instruments (jurisdiction, type, title, official_citation, ext_id, "
        "ext_id_scheme, status, enacted_date, in_force_date, first_seen_at, last_updated_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (fv.jurisdiction, fv.instrument_type, fv.title, fv.official_citation, fv.ext_id,
         fv.ext_id_scheme, fv.status, fv.enacted_date, fv.in_force_date, now_iso(), now_iso()))
    return cur.lastrowid


def store_version(conn: sqlite3.Connection, fv: FetchedVersion) -> dict:
    """Insert fv as a version if new/changed. Returns {instrument_id, version_id, outcome}.
    outcome: 'new' | 'unchanged' | 'metadata-only'. Fires nothing here — the monitor reads diffs."""
    if not fv.source_url:
        raise ValueError("FetchedVersion.source_url is required (finding-aid provenance)")
    iid = _upsert_instrument(conn, fv)
    digest = sha256(fv.content) if fv.content else None

    existing = conn.execute(
        "SELECT id, content_sha256 FROM versions WHERE instrument_id=? AND point_in_time IS ? "
        "AND language=?", (iid, fv.point_in_time, fv.language)).fetchone()
    if existing and existing["content_sha256"] == digest:
        conn.commit()
        return {"instrument_id": iid, "version_id": existing["id"],
                "outcome": "metadata-only" if digest is None else "unchanged"}

    # New point-in-time (or the same slot's text changed): demote prior current, insert.
    conn.execute("UPDATE versions SET is_current=0 WHERE instrument_id=?", (iid,))
    cur = conn.execute(
        "INSERT INTO versions (instrument_id, version_label, point_in_time, language, "
        "is_official_language, is_consolidated, is_authentic, has_unapplied_effects, content, "
        "content_sha256, source_url, retrieved_at, is_current) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,1)",
        (iid, fv.version_label, fv.point_in_time, fv.language, int(fv.is_official_language),
         int(fv.is_consolidated), int(fv.is_authentic), int(fv.has_unapplied_effects),
         fv.content, digest, fv.source_url, now_iso()))
    vid = cur.lastrowid
    if fv.content:
        conn.execute("INSERT INTO versions_fts (rowid, title, citation, body) VALUES (?,?,?,?)",
                     (vid, fv.title, fv.official_citation or "", fv.content))
    conn.commit()
    return {"instrument_id": iid, "version_id": vid,
            "outcome": "metadata-only" if digest is None else "new"}
