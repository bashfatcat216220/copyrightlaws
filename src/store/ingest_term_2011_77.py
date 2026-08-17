"""Wave D (2f) — Term 2006/116: the AUTHENTIC layer for the inserted Article 10a,
from amending Directive 2011/77/EU (authentic OJ L 265, 11.10.2011).

The corpus holds Term Art 10a ONLY as 2011-10-31 consolidation text (is_authentic=0).
Dir 2011/77 Art 1(4) inserts Article 10a IN FULL, verbatim, inside the amending act
("The following Article shall be inserted: 'Article 10a Transitional measures 1. ... 2. ...'").
Because the whole provision is quoted in the authentic OJ act, we can store the authentic
manifestation of Art 10a WITHOUT originating a word.

What this deliberately does NOT do (prime rule 1 — no fake law):
  - Art 3 / Art 1(7) / Art 10(5)-(6): Dir 2011/77's other amendments are PATCH instructions
    ("in paragraph 1, the second sentence shall be replaced by …", "the following paragraph
    shall be added"). Reconstructing a full amended article from a patch would ORIGINATE a
    text that exists in no single source — refused. Those events are recorded as provenance
    metadata by `record_eu_amendments.py` instead; the consolidated current text already
    carries the amended state (70-year terms), honestly flagged "Consolidated — not authentic".

ADDITIVE ONLY: pinned at point_in_time=2011-10-11 (OJ L 265 publication date — the EUR-Lex
ELI page for dir/2011/77 carries "2011-10-11"; the act's own EIF is +20 days = 2011-10-31,
which is the CONSOLIDATED layer's pit slot and is left untouched), is_current=0, via
`store_pinned_version`. No provision rows created; the change monitor is NOT run (rule 6).

Run (scratch first):
    python src/store/ingest_term_2011_77.py --db db/scratch-corpus.db \
        --html spike/artifacts/eu_term_amend_2011_77.html \
        --source-url "https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:32011L0077"
"""
from __future__ import annotations

import argparse
import html as htmlmod
import os
import re
import sqlite3

from _common import require_migration, store_pinned_version

CELEX = ("EU", "CELEX", "32006L0116")          # the AMENDED instrument (Term) — must exist
POINT_IN_TIME = "2011-10-11"                   # OJ L 265, 11.10.2011 (publication)
VERSION_LABEL = "Dir. 2011/77/EU (authentic OJ L 265)"
CITATION = "Directive 2006/116 Art. 10a"


def _flow(html_path: str) -> str:
    """Whole-page text flow with tags stripped (scripts/styles first — rule 5)."""
    h = open(html_path, encoding="utf-8").read()
    t = re.sub(r"<(script|style)\b.*?</\1>", " ", h, flags=re.S | re.I)
    t = re.sub(r"<[^>]+>", "\n", t)
    return htmlmod.unescape(t)


def parse(html_path: str) -> tuple[str, str]:
    """Extract (heading, content) of the inserted Article 10a, verbatim from the quote."""
    t = _flow(html_path)
    anchor = t.find("The following Article shall be inserted")
    if anchor == -1:
        raise SystemExit("insertion clause not found — is this the Dir 2011/77 OJ HTML?")
    qm = re.search(r"‘Article\s*10a", t[anchor:])   # \s covers the NBSP the OJ uses
    if not qm:
        raise SystemExit("quoted Article 10a block not found")
    q1 = anchor + qm.start()
    q2 = t.find("’.", q1)                            # closing quote of the insertion
    if q2 == -1:
        raise SystemExit("closing quote of the Article 10a block not found")
    inner = re.sub(r"\s+", " ", t[q1 + 1:q2]).strip()
    m = re.match(r"Article\s*10a\s+Transitional measures\s+(1\.\s.*)$", inner)
    if not m:
        raise SystemExit(f"unexpected Article 10a shape: {inner[:120]!r}")
    content = m.group(1).strip()
    if "2." not in content or not content.endswith("."):
        raise SystemExit("Article 10a body incomplete — refusing")
    return "Transitional measures", content


def ingest(db_path: str, html_path: str, source_url: str, allow_corpus: bool = False) -> dict:
    if os.path.basename(db_path) == "corpus.db" and not allow_corpus:
        raise SystemExit("refusing to write the live corpus.db — pass --allow-corpus")
    heading, content = parse(html_path)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    require_migration(conn)
    row = conn.execute("SELECT id FROM instruments WHERE jurisdiction=? AND ext_id_scheme=? "
                       "AND ext_id=?", CELEX).fetchone()
    if not row:
        raise SystemExit("Directive 2006/116 instrument not found — this layer is additive only")
    iid = row[0]
    prow = conn.execute("SELECT id, heading FROM provisions WHERE instrument_id=? AND citation=?",
                        (iid, CITATION)).fetchone()
    if not prow:
        raise SystemExit(f"no existing provision for {CITATION} — refusing to mint one")
    if prow[1] and prow[1] != heading:
        print(f"  note: source heading {heading!r} vs stored {prow[1]!r}")
    outcome = store_pinned_version(
        conn, iid, prow[0], CITATION, content, source_url=source_url,
        point_in_time=POINT_IN_TIME, version_label=VERSION_LABEL,
        fts_title="Directive 2006/116/EC", is_authentic=1, is_consolidated=0)
    conn.commit()
    conn.close()
    return {"instrument_id": iid, "outcome": outcome, "chars": len(content)}


def main() -> None:
    ap = argparse.ArgumentParser(description="Term 2006/116 Art 10a — authentic layer from "
                                             "Dir 2011/77 (OJ L 265), additive pinned version.")
    ap.add_argument("--db", required=True)
    ap.add_argument("--html", required=True, help="Dir 2011/77 OJ HTML (eu_term_amend_2011_77.html)")
    ap.add_argument("--source-url", required=True)
    ap.add_argument("--allow-corpus", action="store_true")
    a = ap.parse_args()
    s = ingest(a.db, a.html, a.source_url, a.allow_corpus)
    print(f"instrument #{s['instrument_id']}  Directive 2006/116 Art. 10a — authentic insertion "
          f"({s['chars']} chars) pinned at {POINT_IN_TIME}: {s['outcome']} "
          f"(is_authentic=1, is_current untouched)")


if __name__ == "__main__":
    main()
