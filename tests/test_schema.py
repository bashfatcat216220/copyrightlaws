"""Schema + store invariant tests. Run: pytest -q"""
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))


@pytest.fixture()
def conn(monkeypatch):
    tmp = Path(tempfile.mkdtemp()) / "t.db"
    monkeypatch.setenv("CORPUS_DB_PATH", str(tmp))
    import importlib
    import db as db_mod
    importlib.reload(db_mod)
    c = db_mod.init_db()
    yield c
    c.close()


def _fv(**kw):
    from connectors.base import FetchedVersion
    base = dict(jurisdiction="GB", instrument_type="statute", title="CDPA 1988",
                source_url="https://www.legislation.gov.uk/ukpga/1988/48",
                official_citation="CDPA 1988", ext_id="ukpga/1988/48", ext_id_scheme="ELI",
                content="1. Copyright is a property right...", point_in_time="2020-01-01")
    base.update(kw)
    return FetchedVersion(**base)


def test_seed_has_tier1(conn):
    n = conn.execute("SELECT COUNT(*) FROM jurisdictions WHERE tier=1").fetchone()[0]
    assert n >= 4  # US, GB, EU, INT


def test_store_version_new_then_unchanged(conn):
    import store
    r1 = store.store_version(conn, _fv())
    assert r1["outcome"] == "new"
    r2 = store.store_version(conn, _fv())  # identical text -> same sha
    assert r2["outcome"] == "unchanged"
    assert conn.execute("SELECT COUNT(*) FROM versions").fetchone()[0] == 1


def test_changed_text_makes_new_version_and_flips_current(conn):
    import store
    store.store_version(conn, _fv())
    store.store_version(conn, _fv(point_in_time="2023-06-01", content="1. Copyright is amended..."))
    cur = conn.execute("SELECT COUNT(*) FROM versions WHERE is_current=1").fetchone()[0]
    assert cur == 1
    assert conn.execute("SELECT COUNT(*) FROM versions").fetchone()[0] == 2


def test_fts_search_finds_body(conn):
    import store
    store.store_version(conn, _fv())
    hit = conn.execute("SELECT COUNT(*) FROM versions_fts WHERE versions_fts MATCH 'property'").fetchone()[0]
    assert hit == 1


def test_version_with_text_requires_sha(conn):
    # the trigger fires on a raw INSERT that supplies content but no sha
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO instruments (jurisdiction,type,title,first_seen_at,last_updated_at) "
                     "VALUES ('GB','statute','x','t','t')")
        iid = conn.execute("SELECT id FROM instruments WHERE title='x'").fetchone()[0]
        conn.execute("INSERT INTO versions (instrument_id,content,source_url,retrieved_at) "
                     "VALUES (?,?,?,?)", (iid, "text here", "http://x", "t"))


def test_source_url_required(conn):
    import store
    with pytest.raises(ValueError):
        store.store_version(conn, _fv(source_url=""))


def test_matrix_verify_requires_source(conn):
    # prime rule 4 gate: a cell with no source_version cannot be promoted to authority
    code = conn.execute("SELECT code FROM jurisdictions LIMIT 1").fetchone()[0]
    conn.execute("INSERT INTO matrix_cells (jurisdiction,attribute,value) VALUES (?,?,?)",
                 (code, "term_individual", "life + 70"))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE matrix_cells SET verified_by='x' "
                     "WHERE jurisdiction=? AND attribute='term_individual'", (code,))


def _apply_provisions_migration(conn):
    """The test fixture builds from schema.sql only; provisions/case_treatment live in
    migration 001 (safe on a fresh DB — versions is empty, so the rebuild copy is a no-op)."""
    sql = Path(__file__).resolve().parent.parent / "db" / "migrations" / "001_provisions_rebuild.sql"
    conn.executescript(sql.read_text())


def test_case_fts_reaches_holding_excerpt(conn):
    # issue 4: search must reach case law via what the corpus RECORDS (name, citation, the
    # stored excerpt) — cases have no versions rows, so versions_fts can't carry them
    _apply_provisions_migration(conn)
    conn.execute("INSERT INTO instruments (jurisdiction,type,title,first_seen_at,last_updated_at) "
                 "VALUES ('US','statute','t17','t','t')")
    usc = conn.execute("SELECT id FROM instruments WHERE title='t17'").fetchone()[0]
    conn.execute("INSERT INTO provisions (instrument_id,sort_int,label,kind,citation) "
                 "VALUES (?,107,'§ 107','section','17 U.S.C. § 107')", (usc,))
    pid = conn.execute("SELECT id FROM provisions WHERE instrument_id=?", (usc,)).fetchone()[0]
    conn.execute("INSERT INTO instruments (jurisdiction,type,title,official_citation,"
                 "first_seen_at,last_updated_at) VALUES ('US','case','c1','510 U.S. 569','t','t')")
    case = conn.execute("SELECT id FROM instruments WHERE title='c1'").fetchone()[0]
    conn.execute("INSERT INTO case_treatment (provision_id,case_instrument,treatment,holding,"
                 "source_url,retrieved_at) VALUES (?,?,'cited',"
                 "'whether the fair use defense applies to parody','http://x','t')", (pid, case))
    from store.ingest_cases import sync_case_fts
    assert sync_case_fts(conn) == 1
    hits = conn.execute("SELECT rowid FROM case_fts WHERE case_fts MATCH 'fair use'").fetchall()
    assert len(hits) == 1
    assert sync_case_fts(conn) == 1                 # idempotent — a re-sync never duplicates


def test_case_fts_sync_on_empty_db(conn):
    # a fresh DB with no case links must sync to an empty (not missing/broken) index
    _apply_provisions_migration(conn)
    from store.ingest_cases import sync_case_fts
    assert sync_case_fts(conn) == 0
    assert conn.execute("SELECT COUNT(*) FROM case_fts WHERE case_fts MATCH 'anything'"
                        ).fetchone()[0] == 0


def test_matrix_verify_with_source_ok(conn):
    # a cell that cites a real source version CAN be verified
    code = conn.execute("SELECT code FROM jurisdictions LIMIT 1").fetchone()[0]
    conn.execute("INSERT INTO instruments (jurisdiction,type,title,first_seen_at,last_updated_at) "
                 "VALUES (?,?,?,?,?)", (code, "statute", "m", "t", "t"))
    iid = conn.execute("SELECT id FROM instruments WHERE title='m'").fetchone()[0]
    conn.execute("INSERT INTO versions (instrument_id,source_url,retrieved_at) VALUES (?,?,?)",
                 (iid, "http://x", "t"))
    vid = conn.execute("SELECT id FROM versions WHERE instrument_id=?", (iid,)).fetchone()[0]
    conn.execute("INSERT INTO matrix_cells (jurisdiction,attribute,value,source_version) "
                 "VALUES (?,?,?,?)", (code, "moral_rights_waivable", "yes", vid))
    conn.execute("UPDATE matrix_cells SET verified_by='x', verified_at='t' "
                 "WHERE jurisdiction=? AND attribute='moral_rights_waivable'", (code,))
    assert conn.execute("SELECT verified_by FROM matrix_cells WHERE attribute='moral_rights_waivable'"
                        ).fetchone()[0] == "x"
