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
