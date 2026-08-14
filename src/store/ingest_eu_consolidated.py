"""Re-base EU directives onto their LATEST consolidated version (EUR-Lex ELI HTML).

Currency fix (2026-08-14 audit). Three copyright directives were stored from their ORIGINAL
adopted act, so they missed later amendments; this module layers the current consolidated
text over the existing ARTICLE provisions:

  * Directive 2006/116 (Term)      -> consolidated 2011-10-31 (Dir. 2011/77 term extension,
                                       incl. the inserted Article 10a)
  * Directive 96/9  (Database)     -> consolidated 2019-06-06 (Dir. (EU) 2019/790 amendment)
  * Directive 2001/29 (InfoSoc)    -> consolidated 2019-06-06 (refresh from 2017-10-10)

Source shape: the modern EUR-Lex ELI consolidated HTML —
  <div class="eli-subdivision" id="art_N">
     <p class="title-article-norm">Article N</p>
     <div class="eli-title"><p ...>Heading</p></div>
     <div class="norm"><span class="no-parag">1. </span><div class="norm inline-element">…</div></div> …
Amendment markers (►M1 … ◄, ▼M1) and modref/footnote spans are stripped; the amended text is
kept. Consolidated ELI HTML carries NO recitals (the preamble is dropped) — so this ingests
ARTICLES ONLY; existing recitals keep their authentic-original version untouched.

Honesty / discipline (prime rules 1-3):
  * Consolidated = editorial, NOT authentic -> is_authentic=0, is_consolidated=1, and the UI
    "Consolidated — not authentic" banner. point_in_time = the consolidation date.
  * This is a MANIFESTATION re-base, not an observed amendment. Diffing consolidated ELI text
    against the original-act extraction is cross-source formatting noise, so we DO NOT run the
    change monitor for it and DO NOT fire alerts (that would misrepresent reformatting as a
    legal change). The version history honestly retains both manifestations with provenance.
  * No-clobber: an existing article gets ONLY a new version — its provision row (parent_id,
    sort, children) is never rewritten. A genuinely-new article (e.g. 10a) is created.

Run (scratch first):
    python src/store/ingest_eu_consolidated.py --db /tmp/eu.db --which term
    python src/store/ingest_eu_consolidated.py --db db/corpus.db --allow-corpus --which all
"""
from __future__ import annotations

import argparse
import hashlib
import html as htmlmod
import os
import re
import sqlite3
from datetime import datetime, timezone

ART_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "spike", "artifacts")

# celex/ext_id keyed on the ORIGINAL act (that's how the instrument is stored); short_num
# drives the citation ("Directive 2006/116 Art. 3") — MUST match the existing ingest.
TARGETS = {
    "term": dict(ext_id="32006L0116", short="2006/116", pit="2011-10-31",
                 artifact="eu_term_cons_20111031.html",
                 source_url="https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:02006L0116-20111031"),
    "database": dict(ext_id="31996L0009", short="96/9", pit="2019-06-06",
                     artifact="eu_database_cons_20190606.html",
                     source_url="https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:01996L0009-20190606"),
    "infosoc": dict(ext_id="32001L0029", short="2001/29", pit="2019-06-06",
                    artifact="eu_infosoc_cons_20190606.html",
                    source_url="https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:02001L0029-20190606"),
}

_ART_ANCHOR = re.compile(r'<div\b[^>]*class="eli-subdivision"[^>]*id="art_([0-9a-z]+)"', re.I)
_ART_TITLE = re.compile(r'<p\b[^>]*class="title-article-norm"[^>]*>(.*?)</p>', re.S | re.I)
_ART_HEAD = re.compile(r'<div\b[^>]*class="eli-title"[^>]*>\s*<p\b[^>]*>(.*?)</p>', re.S | re.I)
_NUM = re.compile(r'Article\s+([0-9]+[a-z]*)', re.I)


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _strip(frag: str) -> str:
    """ELI fragment -> clean text: drop footnote/modref/arrow spans + amendment glyphs, tags."""
    # editorial spans that are NOT operative text
    frag = re.sub(r'<span\b[^>]*class="(?:modref|arrow|note-tag|superscript|footnote)"[^>]*>.*?</span>',
                  " ", frag, flags=re.S | re.I)
    frag = re.sub(r'<a\b[^>]*class="[^"]*footnote[^"]*"[^>]*>.*?</a>', " ", frag, flags=re.S | re.I)
    frag = re.sub(r"<[^>]+>", " ", frag)
    frag = htmlmod.unescape(frag)
    frag = frag.replace("►", " ").replace("◄", " ").replace("▼", " ")  # ► ◄ ▼
    frag = re.sub(r"(?<![A-Za-z])[MBCN]\d+(?![A-Za-z])", " ", frag)  # stray M1/B1 amendment refs
    return re.sub(r"\s+", " ", frag).strip()


def parse_articles(html: str, short: str) -> list[dict]:
    """Article-level records (label, heading, citation, content) from ELI consolidated HTML."""
    anchors = list(_ART_ANCHOR.finditer(html))
    out: list[dict] = []
    for i, m in enumerate(anchors):
        start = m.start()
        end = anchors[i + 1].start() if i + 1 < len(anchors) else len(html)
        region = html[start:end]
        tm = _ART_TITLE.search(region)
        nm = _NUM.search(_strip(tm.group(1))) if tm else None
        if not nm:
            continue
        token = nm.group(1)                                   # '3' or '10a'
        # heading: the eli-title block right after the article title
        hm = _ART_HEAD.search(region)
        heading = _strip(hm.group(1)) if hm else None
        # body: region minus the title <p> and the heading block, markers stripped
        body_html = region
        if tm:
            body_html = body_html[:tm.start()] + body_html[tm.end():]
        # re-find + drop the heading block in the trimmed html
        hm2 = _ART_HEAD.search(body_html)
        if hm2:
            body_html = body_html[:hm2.start()] + body_html[hm2.end():]
        # turn "no-parag" numbers into inline "1. " so the blob reads naturally
        body_html = re.sub(r'<span\b[^>]*class="no-parag"[^>]*>(.*?)</span>', r" \1 ", body_html,
                           flags=re.S | re.I)
        content = _strip(body_html)
        out.append(dict(token=token, label=f"Article {token}", heading=heading or None,
                        citation=f"Directive {short} Art. {token}", content=content))
    return out


def ingest_one(conn, key: str) -> dict:
    t = TARGETS[key]
    path = os.path.join(ART_DIR, t["artifact"])
    if not os.path.exists(path):
        raise SystemExit(f"artifact missing: {path}")
    html = open(path, encoding="utf-8").read()
    row = conn.execute("SELECT id FROM instruments WHERE jurisdiction='EU' AND ext_id_scheme='CELEX' "
                       "AND ext_id=?", (t["ext_id"],)).fetchone()
    if not row:
        raise SystemExit(f"{key}: instrument {t['ext_id']} not loaded")
    iid = row[0]
    arts = parse_articles(html, t["short"])
    st = {"key": key, "iid": iid, "articles": len(arts), "versions_new": 0,
          "unchanged": 0, "created_provisions": 0}
    for a in arts:
        if not a["content"]:
            continue
        pv = conn.execute("SELECT id FROM provisions WHERE instrument_id=? AND citation=?",
                          (iid, a["citation"])).fetchone()
        if pv:
            pid = pv[0]                                        # NO-CLOBBER: version only
        else:                                                 # genuinely new article (e.g. 10a)
            m = re.match(r"(\d+)([a-z]*)", a["token"])
            si, su = int(m.group(1)), m.group(2).upper()
            cur = conn.execute("INSERT INTO provisions (instrument_id, parent_id, sort_int, "
                               "sort_suffix, label, heading, kind, role, citation) "
                               "VALUES (?,?,?,?,?,?, 'article','enacting', ?)",
                               (iid, None, si, su, a["label"], a["heading"], a["citation"]))
            pid = cur.lastrowid
            st["created_provisions"] += 1
        digest = hashlib.sha256(a["content"].encode()).hexdigest()
        cur = conn.execute("SELECT content_sha256 FROM versions WHERE instrument_id=? AND "
                           "provision_id=? AND is_current=1", (iid, pid)).fetchone()
        if cur and cur[0] == digest:
            st["unchanged"] += 1
            continue
        conn.execute("UPDATE versions SET is_current=0 WHERE instrument_id=? AND provision_id=?",
                     (iid, pid))
        c = conn.execute(
            "INSERT INTO versions (instrument_id, provision_id, version_label, point_in_time, "
            "language, is_official_language, is_consolidated, is_authentic, content, "
            "content_sha256, source_url, retrieved_at, is_current) "
            "VALUES (?,?,?,?, 'en', 1, 1, 0, ?,?,?,?, 1)",
            (iid, pid, f"EUR-Lex consolidated ({t['pit']})", t["pit"], a["content"], digest,
             t["source_url"], now_iso()))
        conn.execute("DELETE FROM versions_fts WHERE rowid=?", (c.lastrowid,))
        conn.execute("INSERT INTO versions_fts (rowid, title, citation, body) VALUES (?,?,?,?)",
                     (c.lastrowid, f"Directive {t['short']}", a["citation"], a["content"]))
        conn.execute("DELETE FROM provisions_fts WHERE rowid=?", (pid,))
        conn.execute("INSERT INTO provisions_fts (rowid, citation, heading, body) VALUES (?,?,?,?)",
                     (pid, a["citation"], a["heading"] or "", a["content"]))
        st["versions_new"] += 1
    return st


def main() -> None:
    ap = argparse.ArgumentParser(description="Re-base EU directives onto latest consolidated (ELI HTML).")
    ap.add_argument("--db", required=True)
    ap.add_argument("--which", default="all", help="term | database | infosoc | all")
    ap.add_argument("--allow-corpus", action="store_true")
    a = ap.parse_args()
    if os.path.basename(a.db) == "corpus.db" and not a.allow_corpus:
        raise SystemExit("refusing to write live corpus.db — pass --allow-corpus")
    keys = list(TARGETS) if a.which == "all" else [a.which]
    conn = sqlite3.connect(a.db)
    conn.execute("PRAGMA foreign_keys = ON")
    for k in keys:
        s = ingest_one(conn, k)
        print(f"[{k}] instrument #{s['iid']}: {s['articles']} articles parsed; "
              f"versions new {s['versions_new']} (unchanged {s['unchanged']}, "
              f"new provisions {s['created_provisions']})")
    conn.commit()
    conn.close()


if __name__ == "__main__":
    main()
