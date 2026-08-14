"""Generalized ingest for the EU copyright directives — EUR-Lex act HTML.  DRAFT.

Completes Tier-1 EU: the remaining copyright/related directives beyond InfoSoc
(which is already loaded from `ingest_formex.py` — this module does NOT touch it).
One parser handles the whole family by fetching the ORIGINAL adopted act HTML from
EUR-Lex (`legal-content/EN/TXT/HTML/?uri=CELEX:<CELEX>`), which carries BOTH the
numbered recitals `(1)…(N)` in the preamble AND the enacting Articles. NO fake law:
every provision's text comes from the retained fetched page (spike/artifacts/eu_*.html);
nothing is typed from memory. If a directive's HTML won't parse cleanly it is skipped
and reported, never fabricated (prime rule 1).

This is the ORIGINAL adopted act (the OJ text as published), so its version rows carry
is_authentic=1, is_consolidated=0, is_official_language=1 (English is an official EU
language). For directives that were later amended, `ingest_eu_consolidated.py` layers the
current consolidated text (is_authentic=0) over the article provisions. Same idempotency +
corpus.db guard as the other ingests, via `_common`.

Two EUR-Lex HTML families are handled (auto-detected):
  * MODERN OJ (DSM 2019/790, Software 2009/24, Term 2006/116, Rental 2006/115,
    Orphan Works 2012/28): `<div id="art_N">` blocks with `<p class="oj-ti-art">Article N`
    + `<p class="oj-sti-art">heading` + `<p class="oj-normal">` text; recitals as
    `<div id="rct_N"><table>…(N)…text…</table>`; chapters via `oj-ti-section-*`.
  * LEGACY OJ (Database 96/9, Enforcement 2004/48): `<p class="ti-art">…Article N…`
    (no div anchors) + `<p class="sti-art">heading` + `<p class="normal">` text;
    recitals in the `Whereas:` table, cells `(N)` | text.

Provision model (labels source-derived):
  CHAPTER  -> kind 'chapter'  container grouping articles (label 'Chapter I' / 'Title I')
  ARTICLE  -> kind 'article'  role 'enacting'; text versioned at the article level.
  RECITAL  -> kind 'recital'  role 'recital'; interpretive, addressable + searchable.

Run one directive:
    python src/store/ingest_eu_directive.py --db /tmp/eu.db --celex 32019L0790 \
        --html spike/artifacts/eu_dsm.html \
        --source-url 'https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:32019L0790'
Run ALL seven (loops the built-in registry over their retained artifacts):
    python src/store/ingest_eu_directive.py --db /tmp/eu.db --all
"""
from __future__ import annotations

import argparse
import html as htmlmod
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from store._common import RecordSet, ordinal, run_ingest  # noqa: E402

# ── the seven directives (jurisdiction EU, type='directive') ────────────────────
# short_num is what appears in citations ("Directive 2019/790 Art. 17").
DIRECTIVES = {
    "32019L0790": dict(
        slug="dsm", short_num="2019/790", official_citation="Directive (EU) 2019/790",
        artifact="eu_dsm.html",
        title=("Directive (EU) 2019/790 of the European Parliament and of the Council of "
               "17 April 2019 on copyright and related rights in the Digital Single Market "
               "and amending Directives 96/9/EC and 2001/29/EC")),
    "32009L0024": dict(
        slug="software", short_num="2009/24", official_citation="Directive 2009/24/EC",
        artifact="eu_software.html",
        title=("Directive 2009/24/EC of the European Parliament and of the Council of "
               "23 April 2009 on the legal protection of computer programs (Codified version)")),
    "31996L0009": dict(
        slug="database", short_num="96/9", official_citation="Directive 96/9/EC",
        artifact="eu_database.html",
        title=("Directive 96/9/EC of the European Parliament and of the Council of "
               "11 March 1996 on the legal protection of databases")),
    "32006L0116": dict(
        slug="term", short_num="2006/116", official_citation="Directive 2006/116/EC",
        artifact="eu_term.html",
        title=("Directive 2006/116/EC of the European Parliament and of the Council of "
               "12 December 2006 on the term of protection of copyright and certain "
               "related rights (codified version)")),
    "32006L0115": dict(
        slug="rental_lending", short_num="2006/115", official_citation="Directive 2006/115/EC",
        artifact="eu_rental_lending.html",
        title=("Directive 2006/115/EC of the European Parliament and of the Council of "
               "12 December 2006 on rental right and lending right and on certain rights "
               "related to copyright in the field of intellectual property (codified version)")),
    "32012L0028": dict(
        slug="orphan_works", short_num="2012/28", official_citation="Directive 2012/28/EU",
        artifact="eu_orphan_works.html",
        title=("Directive 2012/28/EU of the European Parliament and of the Council of "
               "25 October 2012 on certain permitted uses of orphan works")),
    "32004L0048": dict(
        slug="enforcement", short_num="2004/48", official_citation="Directive 2004/48/EC",
        artifact="eu_enforcement.html",
        title=("Directive 2004/48/EC of the European Parliament and of the Council of "
               "29 April 2004 on the enforcement of intellectual property rights")),
}

ARTIFACT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "spike", "artifacts")

ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8,
         "IX": 9, "X": 10, "XI": 11, "XII": 12, "XIII": 13, "XIV": 14, "XV": 15}


def _instrument(celex: str) -> dict:
    d = DIRECTIVES[celex]
    return dict(jurisdiction="EU", type="directive",
                official_citation=d["official_citation"], ext_id_scheme="CELEX",
                ext_id=celex, title=d["title"])


def _clean(frag: str) -> str:
    """HTML fragment -> collapsed plain text: drop footnote anchors, strip tags, unescape."""
    frag = re.sub(r"<a\b[^>]*>.*?</a>", " ", frag, flags=re.S)     # footnote refs (1)(2)…
    frag = re.sub(r"<[^>]+>", " ", frag)
    return re.sub(r"\s+", " ", htmlmod.unescape(frag)).strip()


def _block_text(frag: str) -> str:
    """Join the paragraph texts of a block (article body / recital cell) in document order,
    excluding the article/section title paragraphs (handled separately)."""
    parts: list[str] = []
    for m in re.finditer(r'<p\b[^>]*class="(?:oj-)?(normal|ti-art|sti-art|ti-section-\d|sti-section-\d)"[^>]*>(.*?)</p>',
                         frag, re.S):
        cls, body = m.group(1), m.group(2)
        if cls in ("ti-art", "sti-art") or cls.startswith(("ti-section", "sti-section")):
            continue                                              # labels/headings, not body
        t = _clean(body)
        if t:
            parts.append(t)
    if not parts:                                                 # no class'd <p> — take all text
        t = _clean(frag)
        if t:
            parts.append(t)
    return "\n".join(parts)


# Article title paragraph: <p ... class="[oj-]ti-art">…Article N…</p>  (N may carry a/b suffix)
_ART_TITLE = re.compile(
    r'<p\b[^>]*class="(?:oj-)?ti-art"[^>]*>(.*?)</p>', re.S)
_ART_NUM = re.compile(r'Article\s+(\d+)([a-z]*)', re.I)
_STI_ART = re.compile(r'<p\b[^>]*class="(?:oj-)?sti-art"[^>]*>(.*?)</p>', re.S)
# Chapter/Title heading: <p ... class="[oj-]ti-section-1">CHAPTER II / TITLE I</p>
_CHAP = re.compile(
    r'<p\b[^>]*class="(?:oj-)?ti-section-1"[^>]*>(.*?)</p>'
    r'(?:\s*(?:<div[^>]*>\s*)?<p\b[^>]*class="(?:oj-)?ti-section-2"[^>]*>(.*?)</p>)?', re.S)
_CHAP_LABEL = re.compile(r'(CHAPTER|TITLE)\s+([IVXLC]+)', re.I)


def _enacting_region(h: str) -> tuple[int, int]:
    """Bound the enacting terms: after 'HAVE ADOPTED THIS DIRECTIVE' (or 'Whereas'),
    up to the signature block ('Done at' / signatory)."""
    start = 0
    for anchor in ("HAVE ADOPTED THIS DIRECTIVE", "HAS ADOPTED THIS DIRECTIVE"):
        i = h.find(anchor)
        if i != -1:
            start = i
            break
    end = len(h)
    for anchor in ("Done at", 'class="signatory"'):
        i = h.find(anchor, start)
        if i != -1:
            end = min(end, i)
    return start, end


def parse_recitals(h: str) -> list[dict]:
    """Numbered recitals from the preamble. Both families put each recital in a table
    cell after 'Whereas:'; modern also wraps it in <div id="rct_N">. We anchor on the
    '(N)' number cell and read the sibling text — robust to both."""
    # Scan the whole PRE-ADOPTION preamble for numbered recital rows. Anchoring on the first
    # literal "Whereas" is unsafe: in the legacy format recital 1's own text begins "Whereas
    # databases…", so that anchor swallows its (1) number cell. The <tr>…(N)…text pattern
    # only occurs for recitals, so scanning up to 'HAVE/HAS ADOPTED' is both safe and complete.
    a = h.find("HAVE ADOPTED")
    if a == -1:
        a = h.find("HAS ADOPTED")
    seg = h[:a] if a != -1 else h
    out: list[dict] = []
    seen: set[int] = set()
    # Each recital = a <tr> whose first cell is a '(N)' paragraph and second cell the text.
    for tr in re.finditer(r"<tr\b[^>]*>(.*?)</tr>", seg, re.S):
        cells = re.findall(r"<td\b[^>]*>(.*?)</td>", tr.group(1), re.S)
        if len(cells) < 2:
            continue
        num_txt = _clean(cells[0])
        m = re.match(r"^\((\d+)\)$", num_txt)
        if not m:
            continue
        n = int(m.group(1))
        if n in seen:
            continue
        text = _block_text(cells[1]) or _clean(cells[1])
        if text:
            seen.add(n)
            out.append(dict(num=n, text=text))
    return out


def parse_articles(h: str) -> list[dict]:
    """Articles with any CHAPTER/TITLE containers, from the enacting region. Splits on
    the `ti-art` article-title paragraphs (works with or without div anchors); each
    article's body is the HTML up to the next article title / chapter / region end."""
    start, end = _enacting_region(h)
    region = h[start:end]

    # Positions of chapter headings and article titles within the region.
    chapters = []
    for m in _CHAP.finditer(region):
        cm = _CHAP_LABEL.search(_clean(m.group(1)))
        if not cm:
            continue
        kind_word, roman = cm.group(1).title(), cm.group(2).upper()
        heading = _clean(m.group(2)) if m.group(2) else None
        chapters.append(dict(pos=m.start(), word=kind_word, roman=roman, heading=heading))

    arts = []
    for m in _ART_TITLE.finditer(region):
        nm = _ART_NUM.search(_clean(m.group(1)))
        if not nm:
            continue
        arts.append(dict(pos=m.start(), body_start=m.end(),
                         num=nm.group(1), suffix=(nm.group(2) or "").lower()))
    if not arts:
        return []

    records: list[dict] = []
    for i, art in enumerate(arts):
        body_end = arts[i + 1]["pos"] if i + 1 < len(arts) else len(region)
        # trim trailing chapter heading that belongs to the NEXT article's chapter
        for ch in chapters:
            if art["body_start"] < ch["pos"] < body_end:
                body_end = min(body_end, ch["pos"])
        frag = region[art["body_start"]:body_end]
        hm = _STI_ART.search(frag)
        heading = _clean(hm.group(1)) if hm else None
        text = _block_text(frag)
        # which chapter is this article under? the last chapter heading before it.
        chap = None
        for ch in chapters:
            if ch["pos"] < art["pos"]:
                chap = ch
            else:
                break
        records.append(dict(num=art["num"], suffix=art["suffix"], heading=heading,
                            content=text, chapter=chap))
    return records


def parse(html_path: str, celex: str) -> RecordSet:
    """Build a RecordSet: recitals (top-level) + chapters (containers) + articles."""
    d = DIRECTIVES[celex]
    short = d["short_num"]
    h = open(html_path, encoding="utf-8").read()
    rs = RecordSet()

    for rec in parse_recitals(h):
        n = rec["num"]
        rs.add(kind="recital", label=f"Recital {n}", heading=None,
               sort_int=n, sort_suffix="", role="recital",
               citation=f"Directive {short} Recital {n}", content=rec["text"])

    chapter_local: dict[str, int] = {}                            # roman -> local id
    articles = parse_articles(h)
    for art in articles:
        parent = None
        ch = art["chapter"]
        if ch:
            key = f"{ch['word']} {ch['roman']}"
            if key not in chapter_local:
                si = ROMAN.get(ch["roman"], len(rs.records) + 1)
                label = f"{ch['word']} {ch['roman']}"
                chapter_local[key] = rs.add(
                    kind="chapter", label=label, heading=ch["heading"],
                    sort_int=si, sort_suffix="", role="enacting",
                    citation=f"Directive {short} {label}", content=None)
            parent = chapter_local[key]
        token = f"{art['num']}{art['suffix']}"
        si, su = ordinal(token, len(rs.records) + 1)
        rs.add(kind="article", label=f"Article {token}", heading=art["heading"],
               sort_int=si, sort_suffix=su, role="enacting", parent_local=parent,
               citation=f"Directive {short} Art. {token}", content=art["content"] or None)
    return rs


def ingest_one(db_path: str, celex: str, html_path: str, source_url: str,
               allow_corpus: bool = False) -> dict:
    inst = _instrument(celex)
    rs = parse(html_path, celex)
    stats = run_ingest(db_path, inst, rs, source_url, allow_corpus=allow_corpus,
                       is_authentic=1, is_consolidated=0, is_official_language=1,
                       version_label="EUR-Lex (original OJ act)",
                       fts_title=inst["official_citation"])
    stats["celex"] = celex
    stats["articles"] = stats["by_kind"].get("article", 0)
    stats["recitals"] = stats["by_kind"].get("recital", 0)
    stats["chapters"] = stats["by_kind"].get("chapter", 0)
    return stats


def _default_source_url(celex: str) -> str:
    return f"https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:{celex}"


def main() -> None:
    ap = argparse.ArgumentParser(description="Ingest EU copyright directives (EUR-Lex act HTML) — draft.")
    ap.add_argument("--db", required=True, help="target SQLite DB (must have migration 001 applied)")
    ap.add_argument("--all", action="store_true", help="loop the built-in registry over retained artifacts")
    ap.add_argument("--celex", help="single CELEX id to ingest (e.g. 32019L0790)")
    ap.add_argument("--html", help="act HTML path (defaults to the registry artifact for --celex)")
    ap.add_argument("--source-url", help="provenance URL (defaults to the EUR-Lex act URL)")
    ap.add_argument("--citation", help="override official_citation (default from registry)")
    ap.add_argument("--title", help="override full title (default from registry)")
    ap.add_argument("--allow-corpus", action="store_true", help="permit writing the live corpus.db")
    a = ap.parse_args()

    if a.all:
        targets = list(DIRECTIVES.keys())
    elif a.celex:
        targets = [a.celex]
    else:
        ap.error("pass --all or --celex <CELEX>")

    for celex in targets:
        if celex not in DIRECTIVES:
            print(f"!! {celex}: not in registry — skipping"); continue
        if a.citation:
            DIRECTIVES[celex]["official_citation"] = a.citation
        if a.title:
            DIRECTIVES[celex]["title"] = a.title
        html_path = a.html if (a.celex and a.html) else os.path.join(ARTIFACT_DIR, DIRECTIVES[celex]["artifact"])
        source_url = a.source_url if (a.celex and a.source_url) else _default_source_url(celex)
        if not os.path.exists(html_path):
            print(f"!! {celex}: artifact missing ({html_path}) — skipping"); continue
        s = ingest_one(a.db, celex, html_path, source_url, a.allow_corpus)
        oc = DIRECTIVES[celex]["official_citation"]
        print(f"#{s['instrument_id']:>3}  {oc:22s} CELEX {celex}: "
              f"{s['articles']} articles, {s['recitals']} recitals, {s['chapters']} chapters  "
              f"(versions new {s['versions_new']}, unchanged {s['versions_unchanged']})")


if __name__ == "__main__":
    main()
