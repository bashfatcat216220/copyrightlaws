"""Provision-aware ingest for Formex (EUR-Lex) — Directive 2001/29 (InfoSoc) slice.  DRAFT — FOR REVIEW.

Third source shape after USLM (US) and CLML (UK). Exercises the Formex act structure
(CONS.ACT > CONS.DOC > ENACTING.TERMS > DIVISION[chapter] > ARTICLE > PARAG > ALINEA >
LIST > ITEM) and — importantly — the FIRST real use of the authenticity flags: this is a
CONSOLIDATED manifestation, so its version rows carry is_authentic=0, is_consolidated=1,
is_official_language=1 (English is an official EU language). It NEVER originates text.

Provision model (labels are SOURCE-derived, never inferred from jurisdiction):
  DIVISION   -> kind 'chapter'  container grouping articles (label 'Chapter I', from TITLE > TI)
  ARTICLE    -> kind 'article'  role 'enacting'; label from TI.ART ('Article 5'),
                heading from STI.ART; operative text versioned at the ARTICLE level.
  PARAG      -> kind 'paragraph' label '(N)' from NO.PARAG; citation '... Art. 5(3)'
  ITEM/LIST  -> kind 'clause'   label '(k)' from NP > NO.P; citation '... Art. 5(3)(k)'
                (deepest real pinpoint in this act: Article 5(3)(k)).

Recitals: this consolidated manifestation FLATTENS recitals into the PREAMBLE — they are
NOT individually CONSID-tagged here, so they are NOT extractable as addressable nodes from
this artifact. Per the agreed provenance split (PROJECT_STATE "Recitals — resolved"), the
ORIGINAL OJ act is the structural source for recitals; the consolidated is the current text.
We therefore ingest the 15 ARTICLES + paragraphs now and DEFER recitals to the original-OJ
manifestation (no fake law — prime rule 1). If a future CONSID-carrying manifestation is
supplied, the recital path is a small addition (kind='recital', role='recital').

Re-runnable / idempotent: instrument keyed on (jurisdiction, ext_id_scheme, ext_id);
provisions on (instrument_id, citation); versions dedup on content_sha256. Refuses to write
the live db/corpus.db unless --allow-corpus is passed, and requires migration 001.

Run against a scratch/demo DB that has migration 001 applied:
    python src/store/ingest_formex.py --db db/corpus-demo.db --xml spike/artifacts/infosoc_act.xml \
        --source-url http://publications.europa.eu/resource/celex/02001L0029-20171010.ENG.fmx4
"""
from __future__ import annotations

import argparse
import hashlib
import html as htmlmod
import os
import re
import sqlite3
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

# Recitals live in the ORIGINAL OJ act (EUR-Lex HTML), as <p>(N) ...</p> in the preamble
# between "Whereas" and "HAVE ADOPTED THIS DIRECTIVE". The consolidated Formex flattens them.
RECITAL_P = re.compile(r"<p[^>]*>\s*\((\d+)\)\s*(.*?)</p>", re.S)

# Subtrees that reproduce OTHER instruments' words / notes — never this act's operative text.
SKIP = {"GR.MOD.ACT", "MOD.ACT", "GR.CORRIG", "CORRIG"}
NUM_RE = re.compile(r"^\s*\(?(\d+)([A-Za-z]*)\)?\.?\s*$")   # '3.', '(3)', '3' -> (3,'')
ALPHA_RE = re.compile(r"^\s*\(?([A-Za-z]+)\)?\.?\s*$")      # '(k)', 'k' -> alphabetic marker

INSTRUMENT = dict(
    jurisdiction="EU", type="directive", official_citation="Directive 2001/29/EC",
    ext_id_scheme="CELEX", ext_id="32001L0029",
    title=("Directive 2001/29/EC of the European Parliament and of the Council of 22 May "
           "2001 on the harmonisation of certain aspects of copyright and related rights "
           "in the information society"),
)

# Chapter roman numerals -> arabic, so 'Chapter IV' sorts after 'Chapter III'.
ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8,
         "IX": 9, "X": 10, "XI": 11, "XII": 12}


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


def ordinal(marker: str | None, doc_index: int) -> tuple[int, str]:
    """(sort_int, sort_suffix). Numbered markers ('3.', '(3)') -> (3, ''); alphabetic
    markers ('(k)') fall back to document order (authoritative from the single fetch),
    exactly as the USLM/CLML templates do for alpha/roman levels."""
    m = NUM_RE.match(marker or "")
    if m:
        return int(m.group(1)), m.group(2).upper()
    return doc_index, ""


def _num(marker: str | None) -> str:
    """Bare number for citation/label building: '3.' -> '3', '(k)' -> 'k'."""
    m = NUM_RE.match(marker or "")
    if m:
        return m.group(1) + m.group(2)
    a = ALPHA_RE.match(marker or "")
    if a:
        return a.group(1)
    return (marker or "").strip().strip("().")


def _block_text(el) -> str:
    """Full operative text of a subtree, skipping amendment/correction material and the
    element's own structural label children (TI.ART/STI.ART/NO.PARAG/NO.P) so a paragraph's
    text is its prose, not '3. 3. ...'."""
    label_tags = {"TI.ART", "STI.ART", "NO.PARAG", "NO.P", "TITLE"}
    parts: list[str] = []

    def rec(e, is_root):
        for c in e:
            name = local(c.tag)
            if name in SKIP or name in label_tags:
                continue
            if c.text and c.text.strip():
                parts.append(c.text.strip())
            rec(c, False)
            if c.tail and c.tail.strip():
                parts.append(c.tail.strip())

    if el.text and el.text.strip():
        parts.append(el.text.strip())
    rec(el, True)
    return " ".join(parts)


def parse(xml_path: str) -> tuple[str, list[dict]]:
    """Return (instrument_title, provision_records) in document order, parents first,
    each with a local_id + parent_local for wiring."""
    root = ET.parse(xml_path).getroot()
    records: list[dict] = []
    seen: dict[str, int] = {}          # deterministic citation-uniqueness guard (as in CLML)

    def add(**kw) -> int:
        cit = kw.get("citation")
        if cit is not None:
            seen[cit] = seen.get(cit, 0) + 1
            if seen[cit] > 1:
                kw["citation"] = f"{cit} #{seen[cit]}"
        kw["local_id"] = len(records) + 1
        records.append(kw)
        return kw["local_id"]

    et = None
    for e in root.iter():
        if local(e.tag) == "ENACTING.TERMS":
            et = e
            break
    if et is None:
        raise SystemExit("no ENACTING.TERMS found — is this a Formex CONS.ACT?")

    def walk_article(art, parent_local):
        ti = _txt(_child(art, "TI.ART"))                        # 'Article 5'
        m = re.search(r"(\d+[A-Za-z]*)\s*$", ti or "")          # -> '5' (survives '5a' insertions)
        art_num = m.group(1) if m else _num(ti)
        art_label = ti or f"Article {art_num}"
        heading = _txt(_child(art, "STI.ART"))
        si, su = ordinal(art_num, len(records) + 1)
        art_cite = f"Directive 2001/29 Art. {art_num}"
        aid = add(parent_local=parent_local, kind="article", label=art_label, heading=heading,
                  sort_int=si, sort_suffix=su, role="enacting", citation=art_cite,
                  content=_block_text(art))

        parags = art.findall("./{*}PARAG")
        for pi, parag in enumerate(parags, 1):
            pnum = _num(_txt(_child(parag, "NO.PARAG")))        # '3.' -> '3'
            psi, psu = ordinal(pnum, pi)
            p_cite = f"{art_cite}({pnum})"
            pid = add(parent_local=aid, kind="paragraph", label=f"({pnum})", heading=None,
                      sort_int=psi, sort_suffix=psu, role="enacting", citation=p_cite,
                      content=_block_text(parag))
            # sub-points: LIST > ITEM > NP > (NO.P, TXT). Emit each cited point as its own node.
            _emit_points(parag, pid, p_cite)

        # articles with NO PARAG carry a single ALINEA block — already captured in the
        # article's own _block_text; but a bare ALINEA may itself hold a LIST of points.
        if not parags:
            for al in art.findall("./{*}ALINEA"):
                _emit_points(al, aid, art_cite)

    def _emit_points(container, parent_local, parent_cite):
        idx = 0
        for lst in container.iter():
            if local(lst.tag) != "LIST":
                continue
            for item in lst:
                if local(item.tag) != "ITEM":
                    continue
                idx += 1
                np = _child(item, "NP")
                if np is None:
                    np = item
                marker = _txt(_child(np, "NO.P"))               # '(k)'
                pt = _num(marker)                               # 'k'
                text_el = _child(np, "TXT")
                content = _txt(text_el) if text_el is not None else _block_text(item)
                si, su = ordinal(marker, idx)
                cite = f"{parent_cite}({pt})"
                add(parent_local=parent_local, kind="clause", label=f"({pt})", heading=None,
                    sort_int=si, sort_suffix=su, role="enacting", citation=cite, content=content)

    for div in et.findall("./{*}DIVISION"):
        title = _child(div, "TITLE")
        ch_label = _txt(_child(title, "TI")) if title is not None else None   # 'Chapter I'
        ch_head = _txt(_child(title, "STI")) if title is not None else None
        parent = None
        if ch_label:
            roman = ch_label.replace("CHAPTER", "").replace("Chapter", "").strip()
            si = ROMAN.get(roman.upper(), len(records) + 1)
            label = f"Chapter {roman}"
            cite = f"Directive 2001/29 {label}"
            parent = add(parent_local=None, kind="chapter", label=label,
                         heading=(ch_head.title() if ch_head else None), sort_int=si,
                         sort_suffix="", role="enacting", citation=cite, content=None)
        for art in div.findall("./{*}ARTICLE"):
            walk_article(art, parent)

    return INSTRUMENT["title"], records


def parse_recitals(html_path: str) -> list[dict]:
    """Extract numbered recitals from the ORIGINAL OJ act HTML (kind='recital')."""
    h = open(html_path, encoding="utf-8").read()
    w, a = h.find("Whereas"), h.find("HAVE ADOPTED")
    seg = h[w:a] if (w != -1 and a != -1 and a > w) else h
    out: list[dict] = []
    for m in RECITAL_P.finditer(seg):
        n = int(m.group(1))
        text = re.sub(r"\s+", " ", htmlmod.unescape(re.sub(r"<[^>]+>", " ", m.group(2)))).strip()
        if text:
            out.append({"num": n, "label": f"Recital {n}", "heading": None,
                        "sort_int": n, "sort_suffix": "", "kind": "recital", "role": "recital",
                        "citation": f"Directive 2001/29 Recital {n}", "content": text})
    return out


# ── DB writers (idempotent) — same contract as ingest_uslm / ingest_clml ────────
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


def _store_version(conn, iid, provid, r, source_url, point_in_time,
                   version_label="EUR-Lex Formex (consolidated)",
                   is_authentic=0, is_consolidated=1) -> str:
    """Insert a provision version. FIRST place is_authentic earns its place: the consolidated
    Formex ARTICLES are NOT authentic (is_authentic=0, is_consolidated=1). RECITALS come from
    the ORIGINAL OJ act, which IS authentic (is_authentic=1, is_consolidated=0) — the
    provenance split, made concrete WITHIN one instrument. is_official_language=1 either way
    (English is an official EU language)."""
    content = r["content"]
    digest = sha256(content)
    existing = conn.execute(
        "SELECT id, content_sha256 FROM versions WHERE instrument_id=? AND provision_id=? "
        "AND point_in_time IS ? AND language='en'", (iid, provid, point_in_time)).fetchone()
    outcome = "unchanged"
    if existing and existing[1] != digest:
        # A row already occupies this (provision, point_in_time, language) slot — e.g. an
        # earlier stopgap manifestation of the SAME consolidation date. UNIQUE forbids a
        # second row, so supersede IN PLACE with this manifestation's text + provenance.
        conn.execute("UPDATE versions SET is_current=0 WHERE instrument_id=? AND provision_id=?",
                     (iid, provid))
        conn.execute(
            "UPDATE versions SET version_label=?, is_official_language=1, is_consolidated=?, "
            "is_authentic=?, content=?, content_sha256=?, source_url=?, retrieved_at=?, "
            "is_current=1 WHERE id=?",
            (version_label, is_consolidated, is_authentic, content, digest, source_url,
             now_iso(), existing[0]))
        conn.execute("DELETE FROM versions_fts WHERE rowid=?", (existing[0],))
        conn.execute("INSERT INTO versions_fts (rowid, title, citation, body) VALUES (?,?,?,?)",
                     (existing[0], "Directive 2001/29/EC", r["citation"], content))
        outcome = "new"
    elif not existing:
        conn.execute("UPDATE versions SET is_current=0 WHERE instrument_id=? AND provision_id=?",
                     (iid, provid))
        cur = conn.execute(
            "INSERT INTO versions (instrument_id, provision_id, version_label, point_in_time, "
            "language, is_official_language, is_consolidated, is_authentic, content, "
            "content_sha256, source_url, retrieved_at, is_current) "
            "VALUES (?,?,?,?, 'en', 1, ?, ?, ?,?,?,?, 1)",
            (iid, provid, version_label, point_in_time, is_consolidated, is_authentic,
             content, digest, source_url, now_iso()))
        conn.execute("INSERT INTO versions_fts (rowid, title, citation, body) VALUES (?,?,?,?)",
                     (cur.lastrowid, "Directive 2001/29/EC", r["citation"], content))
        outcome = "new"
    conn.execute("DELETE FROM provisions_fts WHERE rowid=?", (provid,))
    conn.execute("INSERT INTO provisions_fts (rowid, citation, heading, body) VALUES (?,?,?,?)",
                 (provid, r["citation"], r["heading"] or "", content))
    return outcome


def ingest(db_path, xml_path, source_url, point_in_time=None, allow_corpus=False,
           recitals_html=None, recitals_source_url=None) -> dict:
    if os.path.basename(db_path) == "corpus.db" and not allow_corpus:
        raise SystemExit("refusing to write the live corpus.db (schema is pending sign-off). "
                         "Pass --allow-corpus only after the migration is approved.")
    title, records = parse(xml_path)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    _require_migration(conn)
    iid = _upsert_instrument(conn, title)
    localmap: dict[int, int] = {}
    stats = {"provisions": 0, "chapters": 0, "articles": 0, "paragraphs": 0, "points": 0,
             "recitals": 0, "versions_new": 0, "versions_unchanged": 0}
    for r in records:
        parent_id = localmap.get(r["parent_local"]) if r["parent_local"] else None
        pid = _upsert_provision(conn, iid, parent_id, r)
        localmap[r["local_id"]] = pid
        stats["provisions"] += 1
        stats[{"chapter": "chapters", "article": "articles", "paragraph": "paragraphs",
               "clause": "points", "recital": "recitals"}.get(r["kind"], "provisions")] += 1
        if r["content"]:
            outcome = _store_version(conn, iid, pid, r, source_url, point_in_time)
            stats["versions_new" if outcome == "new" else "versions_unchanged"] += 1
    # Recitals from the ORIGINAL OJ act (authentic text) — top-level nodes (they precede Art. 1).
    if recitals_html:
        for r in parse_recitals(recitals_html):
            pid = _upsert_provision(conn, iid, None, r)
            stats["provisions"] += 1
            stats["recitals"] += 1
            outcome = _store_version(conn, iid, pid, r, recitals_source_url or source_url,
                                     point_in_time, version_label="EUR-Lex (original OJ)",
                                     is_authentic=1, is_consolidated=0)
            stats["versions_new" if outcome == "new" else "versions_unchanged"] += 1
    conn.commit()
    conn.close()
    stats.update(instrument_id=iid, title=title)
    return stats


def main() -> None:
    ap = argparse.ArgumentParser(description="Ingest Directive 2001/29 (InfoSoc) Formex into a provisions DB (draft).")
    ap.add_argument("--db", required=True, help="target SQLite DB (must have migration 001 applied)")
    ap.add_argument("--xml", required=True, help="EUR-Lex Formex CONS.ACT (infosoc_act.xml)")
    ap.add_argument("--source-url", required=True, help="the consolidated fmx4 manifestation URL (provenance)")
    ap.add_argument("--point-in-time", default=None, help="ISO date the consolidated text is in force from")
    ap.add_argument("--allow-corpus", action="store_true", help="permit writing the live corpus.db")
    ap.add_argument("--recitals-html", default=None, help="ORIGINAL OJ act HTML (EUR-Lex) for recitals")
    ap.add_argument("--recitals-source-url", default=None, help="provenance URL for the recitals (original OJ)")
    a = ap.parse_args()
    s = ingest(a.db, a.xml, a.source_url, a.point_in_time, a.allow_corpus,
               a.recitals_html, a.recitals_source_url)
    print(f"instrument #{s['instrument_id']}  Directive 2001/29/EC (InfoSoc)")
    print(f"  provisions upserted : {s['provisions']}")
    print(f"  chapters            : {s['chapters']}")
    print(f"  articles            : {s['articles']}  (role='enacting', versioned at article level)")
    print(f"  paragraphs          : {s['paragraphs']}")
    print(f"  points (clauses)    : {s['points']}")
    print(f"  recitals            : {s['recitals']}  (deferred to original-OJ manifestation if 0)")
    print(f"  versions            : new {s['versions_new']}, unchanged {s['versions_unchanged']} "
          f"(is_authentic=0, is_consolidated=1)")


if __name__ == "__main__":
    main()
