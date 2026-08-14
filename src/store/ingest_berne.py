"""Hand-loaded ingest for the Berne Convention — the treaty (no-XML) source shape.  DRAFT.

Fourth source shape after USLM (US), CLML (UK), Formex (EU). Treaties have no XML API, so
this parses the OFFICIAL WIPO Lex text (server-rendered HTML) into a provision tree —
articles (with bis/ter and the roman-numeral Appendix) + numbered paragraphs. NO fake law:
every article's text comes from the fetched WIPO page; nothing is typed from memory. Same
idempotency + corpus.db guard as the other ingests.

Source (retained): spike/artifacts/berne_wipolex.html — WIPO Lex text/283698, the Paris Act
(1971, amended 1979). Provenance URL is the WIPO Lex page.

Run:
    python src/store/ingest_berne.py --db db/corpus.db --allow-corpus \
        --html spike/artifacts/berne_wipolex.html \
        --source-url https://www.wipo.int/wipolex/en/text/283698
"""
from __future__ import annotations

import argparse
import hashlib
import html as htmlmod
import os
import re
import sqlite3
from datetime import datetime, timezone

INSTRUMENT = dict(jurisdiction="INT", type="treaty", official_citation="Berne Convention",
                  ext_id_scheme="TREATY", ext_id="berne-paris-1971",
                  title="Berne Convention for the Protection of Literary and Artistic Works "
                        "(Paris Act, 1971, as amended 1979)")

# Article heading marker in the WIPO body: <strong>Article N[<em>bis</em>]<br/> ... </strong>
HEAD = re.compile(r"<strong>\s*Article\s+(\d+|[IVXLC]+)\s*"
                  r"(?:<em>\s*(bis|ter|quater)\s*</em>)?\s*<br\s*/?>(.*?)</strong>", re.S)
NUM_RE = re.compile(r"^\s*(\d+)([A-Za-z]*)\s*$")


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _clean(frag: str) -> str:
    frag = re.sub(r"<a\s+name[^>]*>\s*</a>", "", frag)
    frag = re.sub(r"<[^>]+>", " ", frag)
    return re.sub(r"\s+", " ", htmlmod.unescape(frag)).strip()


def ordinal(token: str, doc_index: int) -> tuple[int, str]:
    """(sort_int, sort_suffix). '6bis' -> (6,'BIS') so 6 < 6bis < 7; roman Appendix
    articles (I, II, ...) have no arabic number -> fall back to document order."""
    m = NUM_RE.match(token or "")
    if m:
        return int(m.group(1)), m.group(2).upper()
    return doc_index, ""


def parse(html_path: str) -> list[dict]:
    html = open(html_path, encoding="utf-8").read()
    heads = list(HEAD.finditer(html))
    records: list[dict] = []
    seen: dict[str, int] = {}

    def add(**kw) -> int:
        cit = kw["citation"]
        seen[cit] = seen.get(cit, 0) + 1
        if seen[cit] > 1:
            kw["citation"] = f"{cit} #{seen[cit]}"
        kw["local_id"] = len(records) + 1
        records.append(kw)
        return kw["local_id"]

    for i, m in enumerate(heads):
        raw_num, suffix = m.group(1), (m.group(2) or "")
        is_roman = not raw_num.isdigit()          # roman numerals = the Appendix articles
        token = f"{raw_num}{suffix}"
        # marginal note = the strong's text after the number, up to the first ':'
        note = _clean(m.group(3)).split(":")[0].strip() or None
        if is_roman:
            label = f"Appendix Article {raw_num}"
            cite = f"Berne Convention Appendix Art. {raw_num}"
        else:
            label = f"Article {token}"
            cite = f"Berne Convention Art. {token}"
        si, su = ordinal(token, i)
        body = _clean(html[m.end(): heads[i + 1].start() if i + 1 < len(heads) else m.end() + 8000])
        aid = add(parent_local=None, kind="article", label=label, heading=note,
                  sort_int=si, sort_suffix=su, role="enacting", citation=cite, content=body or None)
        # numbered paragraphs (1)(2)... as addressable child provisions (article carries the text).
        # STRICTLY SEQUENTIAL only: a real list runs (1),(2),(3)… — a "(N)" out of sequence is a
        # cross-reference ("Article 7(1) of…") or duplicate, not a pinpoint (prime rule 1: no fake law).
        expected = 1
        for p in re.split(r"(?=\(\d+\)\s)", body):
            pm = re.match(r"\((\d+)\)", p)
            if not pm or int(pm.group(1)) != expected:
                continue
            add(parent_local=aid, kind="paragraph", label=f"({expected})", heading=None,
                sort_int=expected, sort_suffix="", role="enacting",
                citation=f"{cite}({expected})", content=None)
            expected += 1
    return records


# ── DB writers (idempotent) — same contract as the other ingests ────────────
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
        # Treaty text from WIPO is an official English text (authentic); not a consolidation.
        cur = conn.execute(
            "INSERT INTO versions (instrument_id, provision_id, version_label, point_in_time, "
            "language, is_official_language, is_consolidated, is_authentic, content, "
            "content_sha256, source_url, retrieved_at, is_current) "
            "VALUES (?,?,?,?, 'en', 1, 0, 1, ?,?,?,?, 1)",
            (iid, provid, "WIPO Lex (Paris Act 1971)", point_in_time, content, digest,
             source_url, now_iso()))
        conn.execute("INSERT INTO versions_fts (rowid, title, citation, body) VALUES (?,?,?,?)",
                     (cur.lastrowid, "Berne Convention", r["citation"], content))
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
    stats = {"provisions": 0, "articles": 0, "paragraphs": 0, "versions_new": 0, "versions_unchanged": 0}
    for r in records:
        parent_id = localmap.get(r["parent_local"]) if r["parent_local"] else None
        pid = _upsert_provision(conn, iid, parent_id, r)
        localmap[r["local_id"]] = pid
        stats["provisions"] += 1
        stats["articles" if r["kind"] == "article" else "paragraphs"] += 1
        if r["content"]:
            outcome = _store_version(conn, iid, pid, r, source_url, point_in_time)
            stats["versions_new" if outcome == "new" else "versions_unchanged"] += 1
    conn.commit()
    conn.close()
    stats["instrument_id"] = iid
    return stats


def main() -> None:
    ap = argparse.ArgumentParser(description="Ingest the Berne Convention (WIPO Lex HTML) — draft.")
    ap.add_argument("--db", required=True)
    ap.add_argument("--html", required=True)
    ap.add_argument("--source-url", required=True)
    ap.add_argument("--point-in-time", default=None)
    ap.add_argument("--allow-corpus", action="store_true")
    a = ap.parse_args()
    s = ingest(a.db, a.html, a.source_url, a.point_in_time, a.allow_corpus)
    print(f"instrument #{s['instrument_id']}  Berne Convention")
    print(f"  provisions upserted : {s['provisions']}")
    print(f"  articles            : {s['articles']}  (incl. bis/ter + roman Appendix)")
    print(f"  paragraphs          : {s['paragraphs']}")
    print(f"  versions            : new {s['versions_new']}, unchanged {s['versions_unchanged']}")


if __name__ == "__main__":
    main()
