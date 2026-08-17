"""Wave D (2f) — record the EU amendment EVENTS as provenance metadata (`amendments` rows).

The `amendments` table was empty although the corpus embodies three amendment events
(2026-08-16 audit, 2f LOW + Wave D). This script records them — METADATA ONLY, grounded
row-by-row in retained/fetched artifacts. It does NOT feed the change monitor (a
cross-manifestation re-base is not an observed amendment — CLAUDE ingest rule 6) and
does NOT touch provisions/versions.

Grounding (every field traced to a source artifact):
  1. Dir (EU) 2017/1564 Art. 8 ("Amendment to Directive 2001/29/EC": "In Article 5(3) of
     Directive 2001/29/EC, point (b) is replaced by …") — artifact
     spike/artifacts/eu_infosoc_amend_2017_1564.html (fetched 2026-08-16). Effective
     2017-10-10: its Art. 12 enters into force +20 days after OJ publication; the InfoSoc
     consolidated Formex (spike/artifacts/infosoc_act.xml) carries START.DATE="20171010".
  2. Dir (EU) 2019/790 Art. 24(2) ("Directive 2001/29/EC is amended as follows": (a)
     replaces Art. 5(2)(c); (b) replaces Art. 5(3)(a); (c) adds Art. 12(4)(e)-(g)) —
     artifact spike/artifacts/eu_dsm.html. Effective 2019-06-06: Art. 31 EIF +20 days
     after OJ L 130, 17.5.2019 (the OJ cite appears in the act's own Art. 24 footnote);
     the InfoSoc/Database consolidations carry START.DATE="20190606".
  3. Dir 2011/77/EU Art. 1 ("Directive 2006/116/EC is hereby amended as follows": (1) adds
     Art. 1(7); (2) amends Art. 3 (incl. paragraphs (1)-(2e)); (3) adds Art. 10(5)-(6);
     (4) inserts Art. 10a) — artifact spike/artifacts/eu_term_amend_2011_77.html (fetched
     2026-08-16). Effective 2011-10-31: its Art. 4 EIF +20 days after OJ L 265, 11.10.2011;
     matches the 02006L0116-20111031 consolidation the corpus already holds.

Idempotent: keyed on (amended_instrument, source_url) — a re-run inserts nothing.

Run (scratch first):
    python src/store/record_eu_amendments.py --db db/scratch-corpus.db
"""
from __future__ import annotations

import argparse
import os
import sqlite3

from _common import now_iso

# (amending ext_id or None, amended ext_id, sections_affected, effect, effective_date, source_url)
EVENTS = [
    (None, "32001L0029",
     "Art. 5(3)(b) (substituted by Directive (EU) 2017/1564 Art. 8 — Marrakesh Treaty implementation)",
     "substituted", "2017-10-10",
     "https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:32017L1564"),
    ("32019L0790", "32001L0029",
     "Art. 5(2)(c) and Art. 5(3)(a) (substituted); Art. 12(4)(e)-(g) (added) — "
     "Directive (EU) 2019/790 Art. 24(2)",
     "substituted", "2019-06-06",
     "https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:32019L0790"),
    (None, "32006L0116",
     "Art. 1(7) (added); Art. 3(1)-(2e) (amended); Art. 10(5)-(6) (added); Art. 10a "
     "(inserted) — Directive 2011/77/EU Art. 1",
     "inserted", "2011-10-31",
     "https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:32011L0077"),
]


def record(db_path: str, allow_corpus: bool = False) -> dict:
    if os.path.basename(db_path) == "corpus.db" and not allow_corpus:
        raise SystemExit("refusing to write the live corpus.db — pass --allow-corpus")
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")

    def iid(ext_id):
        if ext_id is None:
            return None                       # amending act is not itself a corpus instrument
        r = conn.execute("SELECT id FROM instruments WHERE ext_id_scheme='CELEX' AND ext_id=?",
                         (ext_id,)).fetchone()
        if not r:
            raise SystemExit(f"instrument CELEX:{ext_id} not found")
        return r[0]

    stats = {"inserted": 0, "existing": 0}
    for amending, amended, sections, effect, eff_date, url in EVENTS:
        amended_id = iid(amended)
        if conn.execute("SELECT 1 FROM amendments WHERE amended_instrument=? AND source_url=?",
                        (amended_id, url)).fetchone():
            stats["existing"] += 1
            continue
        conn.execute("INSERT INTO amendments (amending_instrument, amended_instrument, "
                     "sections_affected, effect, effective_date, source_url, retrieved_at) "
                     "VALUES (?,?,?,?,?,?,?)",
                     (iid(amending), amended_id, sections, effect, eff_date, url, now_iso()))
        stats["inserted"] += 1
    conn.commit()
    conn.close()
    return stats


def main() -> None:
    ap = argparse.ArgumentParser(description="Record EU amendment events (provenance metadata "
                                             "only — no text, no monitor).")
    ap.add_argument("--db", required=True)
    ap.add_argument("--allow-corpus", action="store_true")
    a = ap.parse_args()
    s = record(a.db, a.allow_corpus)
    print(f"amendments rows: inserted {s['inserted']}, already present {s['existing']} "
          f"(metadata only; monitor NOT run)")


if __name__ == "__main__":
    main()
