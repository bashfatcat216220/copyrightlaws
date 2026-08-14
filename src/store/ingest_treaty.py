"""Generalized hand-loaded ingest for the core copyright TREATIES — the no-XML source shape.

Generalizes `ingest_berne.py` (which stays untouched) to the rest of the Tier-1 treaty
group: WCT, WPPT, Rome, Beijing, Marrakesh (WIPO Lex) + TRIPS (WTO). Each is `type='treaty'`,
`jurisdiction='INT'`, authentic official-English text → is_authentic=1, is_consolidated=0,
is_official_language=1. NO fake law: every article's text comes from a fetched, retained
artifact under spike/artifacts/; nothing is typed from memory. Idempotent + corpus.db guard
come from `_common.run_ingest` (keyed on the stable per-article citation).

Three real-world source shapes were needed — the treaty group is heterogeneous even within
WIPO Lex, so `parse()` dispatches on a per-instrument `mode`:

  * "wipo_html"  — server-rendered WIPO Lex HTML. Article heading is a centred
                   `<strong>`/`<b>` block: `<a name="…"></a>Article N<br>Heading`.
                   Used by Rome, Beijing, Marrakesh (same family as Berne). Agreed
                   Statements, where WIPO interleaves them inline after an article, are
                   RETAINED as part of that article's body (adopted interpretive text).
  * "wipo_pdf"   — WCT/WPPT ship as a CloudFront-presigned PDF inside the page's <iframe>;
                   we pdftotext -layout it. Heading is a centred (indented) line `Article N`
                   then a heading line, then the body. The trailing "Note: The agreed
                   statements…" block is the boundary — articles stop there; the Agreed
                   Statements are SKIPPED for these two (noted in the report).
  * "wto_html"   — WTO-hosted TRIPS. Heading is `<a name="artN"></a> … <h2>Article N</h2>`
                   with the marginal note in a following `<p class="center">`.

Retained artifacts (provenance URL = the WIPO Lex / WTO page):
  spike/artifacts/wct_wipolex.txt   (PDF→text; page = text/295157)
  spike/artifacts/wppt_wipolex.txt  (PDF→text; page = text/295477)
  spike/artifacts/rome_wipolex.html (page = text/289757)
  spike/artifacts/beijing_wipolex.html   (page = text/295837)
  spike/artifacts/marrakesh_wipolex.html (page = text/301016)
  spike/artifacts/trips_wto.html    (wto.org/english/docs_e/legal_e/trips_e.htm)

Run one treaty:
    python src/store/ingest_treaty.py --treaty wct --db db/corpus.db --allow-corpus
Run all:
    python src/store/ingest_treaty.py --treaty all --db db/corpus.db --allow-corpus
Validate on a scratch DB (no --allow-corpus needed):
    python src/store/ingest_treaty.py --treaty wct --db /tmp/treaty.db
"""
from __future__ import annotations

import argparse
import html as htmlmod
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import RecordSet, ordinal, run_ingest  # noqa: E402

_ART = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..",
                    "spike", "artifacts")


# ── per-treaty config ───────────────────────────────────────────────────────
# cite_prefix drives the pinpoint citation ("WCT Art. 8", "TRIPS Art. 9").
TREATIES: dict[str, dict] = {
    "wct": dict(
        slug="wct-1996", mode="wipo_pdf", cite_prefix="WCT",
        artifact="wct_wipolex.txt",
        source_url="https://www.wipo.int/wipolex/en/text/295157",
        official_citation="WIPO Copyright Treaty (WCT)",
        title="WIPO Copyright Treaty (WCT) (Geneva, 1996)",
        version_label="WIPO Lex (WCT, 1996)"),
    "wppt": dict(
        slug="wppt-1996", mode="wipo_pdf", cite_prefix="WPPT",
        artifact="wppt_wipolex.txt",
        source_url="https://www.wipo.int/wipolex/en/text/295477",
        official_citation="WIPO Performances and Phonograms Treaty (WPPT)",
        title="WIPO Performances and Phonograms Treaty (WPPT) (Geneva, 1996)",
        version_label="WIPO Lex (WPPT, 1996)"),
    "rome": dict(
        slug="rome-1961", mode="wipo_html", cite_prefix="Rome Convention",
        artifact="rome_wipolex.html",
        source_url="https://www.wipo.int/wipolex/en/text/289757",
        official_citation="Rome Convention (1961)",
        title="International Convention for the Protection of Performers, Producers of "
              "Phonograms and Broadcasting Organisations (Rome, 1961)",
        version_label="WIPO Lex (Rome Convention, 1961)"),
    "beijing": dict(
        slug="beijing-2012", mode="wipo_html", cite_prefix="Beijing Treaty",
        artifact="beijing_wipolex.html",
        source_url="https://www.wipo.int/wipolex/en/text/295837",
        official_citation="Beijing Treaty on Audiovisual Performances (2012)",
        title="Beijing Treaty on Audiovisual Performances (2012)",
        version_label="WIPO Lex (Beijing Treaty, 2012)"),
    "marrakesh": dict(
        slug="marrakesh-2013", mode="wipo_html", cite_prefix="Marrakesh Treaty",
        artifact="marrakesh_wipolex.html",
        source_url="https://www.wipo.int/wipolex/en/text/301016",
        official_citation="Marrakesh Treaty (2013)",
        title="Marrakesh Treaty to Facilitate Access to Published Works for Persons Who "
              "Are Blind, Visually Impaired or Otherwise Print Disabled (2013)",
        version_label="WIPO Lex (Marrakesh Treaty, 2013)"),
    "trips": dict(
        slug="trips-1994", mode="wto_html", cite_prefix="TRIPS",
        artifact="trips_wto.html",
        source_url="https://www.wto.org/english/docs_e/legal_e/trips_e.htm",
        official_citation="TRIPS Agreement (1994)",
        title="Agreement on Trade-Related Aspects of Intellectual Property Rights "
              "(TRIPS) (Marrakesh, 1994, as amended 2005)",
        version_label="WTO legal texts (TRIPS)"),
}


def _clean(frag: str) -> str:
    """HTML fragment → plain text: drop script/style + empty anchors + footnote superscripts,
    strip tags. Script/style go FIRST so page-footer JS can't survive as body text."""
    frag = re.sub(r"<(script|style)\b[^>]*>.*?</\1>", " ", frag, flags=re.S | re.I)
    frag = re.sub(r"<a\s+[^>]*name[^>]*>\s*</a>", "", frag)
    frag = re.sub(r"<sup>.*?</sup>", "", frag, flags=re.S)       # WIPO footnote refs
    frag = re.sub(r"<[^>]+>", " ", frag)
    return re.sub(r"\s+", " ", htmlmod.unescape(frag)).strip()


# ── shared: add an Agreed Statement as its own interpretive provision ─────────
# Agreed Statements are adopted interpretive text of the Diplomatic Conference, NOT enacting
# articles. They are ingested VERBATIM from the source artifact and tagged `role='recital'`
# ("interpretive; addressable + searchable, NEVER counted/diffed" per the schema) so they read
# as agreed statements, not enacting text — the schema's kind/role vocabulary has no dedicated
# 'note'/'interpretive', and 'recital' carries exactly these semantics. sort_int is offset past
# the articles (base 10000 + endnote index) so they file after the treaty body. The citation
# carries the article(s) the statement concerns; when two endnotes concern the SAME article the
# RecordSet's `#N` disambiguator keeps them distinct (a note tag, never a fabricated pinpoint).
_AS_SORT_BASE = 10000


def _add_agreed_statement(rs: RecordSet, cite_prefix: str, idx: int, art_ref: str,
                          text: str) -> None:
    art_ref = re.sub(r"\s+", " ", art_ref).strip().rstrip(":").strip()
    plural = "s" if _multi_art(art_ref) else ""
    label = f"Agreed Statement concerning Article{plural} {art_ref}"
    cite = f"{cite_prefix} Agreed Statement concerning Article{plural} {art_ref}"
    rs.add(kind="recital", label=label, heading=None, sort_int=_AS_SORT_BASE + idx,
           sort_suffix="", role="recital", citation=cite, content=text or None)


def _multi_art(art_ref: str) -> bool:
    """True when the reference names more than one article (e.g. '6 and 7', '2(e), 8, 9')."""
    return bool(re.search(r"\band\b|,", art_ref))


# ── shared: add an article + its addressable numbered paragraphs ─────────────
def _add_article(rs: RecordSet, cite_prefix: str, i: int, token: str, heading: str | None,
                 body: str) -> None:
    """token = article number incl. any bis/ter suffix (e.g. '6', '6bis'). Article carries
    the text; numbered paragraphs `(1)(2)` OR `1. 2.` become addressable shareless children."""
    si, su = ordinal(token, i)
    cite = f"{cite_prefix} Art. {token}"
    aid = rs.add(kind="article", label=f"Article {token}", heading=heading or None,
                 sort_int=si, sort_suffix=su, role="enacting", citation=cite,
                 content=body or None)
    # child paragraphs: "(1) …" (WIPO) or "1. …" (WTO). Addressable only; article holds text.
    # GUARD: only a STRICTLY SEQUENTIAL run counts — (1),(2),(3)… A real numbered-paragraph list
    # starts at (1) and increments. Anything out of sequence is a footnote marker ("other use (7)"),
    # a cross-reference ("Article 14(2)"), a year ("(1971)"), or a duplicate — NOT a pinpoint.
    # Minting provisions from those is fabricated citation (prime rule 1: no fake law).
    expected = 1
    for pm in re.finditer(r"(?:^|\s)(?:\((\d+)\)|(\d+)\.\s)", body or ""):
        n = int(pm.group(1) or pm.group(2))
        if n != expected:
            continue
        rs.add(parent_local=aid, kind="paragraph", label=f"({n})", sort_int=n,
               role="enacting", citation=f"{cite}({n})", content=None)
        expected += 1


# ── mode: WIPO server-rendered HTML (Rome / Beijing / Marrakesh) ─────────────
# Heading anchor: <strong>|<b> [<a name=…></a>] Article[ ]N[bis/ter/quater] …
# The number is the reliable marker; the marginal note may sit after a <br> INSIDE the same
# bold run (Rome/Marrakesh) OR in a SECOND bold run after </strong> (Beijing Art 5). So we
# match only up to the number, then read the note + body from what follows.
_HTML_HEAD = re.compile(
    r"<(strong|b)>\s*(?:<a\s+[^>]*name[^>]*>\s*</a>\s*)?"
    r"Article\s*(\d+|[IVXLC]+)\s*(?:<em>\s*(bis|ter|quater)\s*</em>|(bis|ter|quater))?",
    re.S | re.I)
# note candidate right after the number: either "<br>Heading</strong>" (same run) or a
# following "<strong>Heading</strong>" run before the first body <p>.
_HTML_NOTE = re.compile(
    r"\A\s*(?:<br\s*/?>\s*(.*?)</(?:strong|b)>|</(?:strong|b)>\s*<br\s*/?>\s*"
    r"<(?:strong|b)>(.*?)</(?:strong|b)>)", re.S | re.I)


# Agreed Statements in the WIPO HTML sit after the LAST article, below a horizontal rule
# (`<hr align=left …>`), as footnote paragraphs:
#   <p><sup><a name="_ftnN">N</a></sup> <strong|b>Agreed statement concerning Article X:</strong|b> body</p>
_HTML_AS_HR = re.compile(r"<hr\b[^>]*>", re.I)
_HTML_AS_FN = re.compile(
    r"<p>\s*(?:<sup>)?\s*<a\s+[^>]*name=\"_ftn(\d+)\"[^>]*>.*?</a>\s*(?:</sup>)?\s*"
    r"<(?:strong|b)>\s*Agreed\s+statement\s+concerning\s+Articles?\s+(.*?)\s*:\s*</(?:strong|b)>"
    r"(.*?)</p>", re.S | re.I)


def _parse_wipo_html(path: str, cite_prefix: str) -> RecordSet:
    html = open(path, encoding="utf-8", errors="replace").read()
    # BOUND the article run at the Agreed-Statements horizontal rule so the last article does
    # not swallow the endnote block (Beijing Art. 30 / Marrakesh Art. 22 dumped ~11–13 agreed
    # statements). Everything after the rule is parsed separately as interpretive notes.
    hr = _HTML_AS_HR.search(html)
    body_html = html[:hr.start()] if hr else html
    heads = list(_HTML_HEAD.finditer(body_html))
    rs = RecordSet()
    for i, m in enumerate(heads):
        raw_num = m.group(2)
        suffix = (m.group(3) or m.group(4) or "")
        token = f"{raw_num}{suffix}"
        end = heads[i + 1].start() if i + 1 < len(heads) else len(body_html)
        seg = body_html[m.end():end]
        heading, body_start = None, m.end()
        nm = _HTML_NOTE.match(seg)
        if nm:
            heading = _clean(nm.group(1) or nm.group(2) or "") or None
            body_start = m.end() + nm.end()
        body = _clean(body_html[body_start:end])
        _add_article(rs, cite_prefix, i, token, heading, body)
    if hr:
        _parse_html_agreed_statements(rs, cite_prefix, html[hr.end():])
    return rs


def _parse_html_agreed_statements(rs: RecordSet, cite_prefix: str, tail: str) -> None:
    """Parse the footnote-paragraph Agreed Statements after the horizontal rule into their own
    interpretive provisions, verbatim. The footnote number (_ftnN) is the endnote index."""
    for m in _HTML_AS_FN.finditer(tail):
        idx = int(m.group(1))
        art_ref = _clean(m.group(2))
        body = _clean(m.group(3))
        # store the full statement verbatim, prefixed with its "Agreed statement concerning…" head
        multi = _multi_art(art_ref)
        text = (f"Agreed statement concerning Article{'s' if multi else ''} {art_ref}: {body}").strip()
        _add_agreed_statement(rs, cite_prefix, idx, art_ref, text)


# ── mode: WIPO PDF → pdftotext text (WCT / WPPT) ─────────────────────────────
_PDF_HEAD = re.compile(r"^[ \t\x0c]*Article\s+(\d+)([A-Za-z]*)\s*$")
_PDF_NOISE = re.compile(r"^\s*(page\s+\d+/\d+|\x0c)\s*$", re.I)


# An endnote in the PDF is: a lone number line (the endnote marker, e.g. "         1"),
# then a body line beginning "Agreed statement concerning Article(s) <ref>: <text>". The
# marker numbers run 1..N sequentially.
_PDF_AS_MARK = re.compile(r"^\s*(\d+)\s*$")
_PDF_AS_HEAD = re.compile(
    r"^\s*Agreed statement concerning Articles?\s+(.*?):\s*(.*)$", re.I)


def _parse_wipo_pdf(path: str, cite_prefix: str) -> RecordSet:
    raw = open(path, encoding="utf-8", errors="replace").read()
    lines = raw.split("\n")
    # locate article heading lines; stop the ARTICLE run at "Note: The agreed statements" — the
    # Agreed Statements that follow are ingested separately as their own interpretive provisions.
    stop = len(lines)
    for j, ln in enumerate(lines):
        if re.match(r"\s*Note:\s*The agreed statements", ln):
            stop = j
            break
    heads: list[tuple[int, str, str]] = []
    for j in range(stop):
        m = _PDF_HEAD.match(lines[j])
        if m:
            heads.append((j, m.group(1), m.group(2)))
    rs = RecordSet()
    for k, (j, num, suf) in enumerate(heads):
        token = f"{num}{suf}"
        end = heads[k + 1][0] if k + 1 < len(heads) else stop
        block = lines[j + 1:end]
        block = [ln for ln in block if not _PDF_NOISE.match(ln) and ln.strip() != "\x0c"]
        # heading = the first non-blank line after "Article N"; body = the rest
        heading = None
        rest_start = 0
        for idx, ln in enumerate(block):
            s = ln.strip().replace("\x0c", "")
            if s:
                heading = s
                rest_start = idx + 1
                break
        body_lines = [ln.replace("\x0c", "") for ln in block[rest_start:]]
        body = re.sub(r"\s+", " ", " ".join(body_lines)).strip()
        _add_article(rs, cite_prefix, k, token, heading, body)
    _parse_pdf_agreed_statements(rs, cite_prefix, lines, stop)
    return rs


def _parse_pdf_agreed_statements(rs: RecordSet, cite_prefix: str, lines: list[str],
                                 start: int) -> None:
    """After the "Note: The agreed statements…" boundary the PDF lists the endnotes. Each is a
    lone marker number (1,2,3…) then "Agreed statement concerning Article(s) <ref>: <body>",
    the body flowing across lines until the NEXT marker+"Agreed statement" pair. We slice on the
    STRICTLY SEQUENTIAL marker run so a stray page number / digit never starts a fake note."""
    # gather (line_index, marker_number) for lone-number lines that are immediately followed
    # (skipping blanks/page-noise) by an "Agreed statement concerning" line.
    marks: list[tuple[int, int]] = []
    for j in range(start, len(lines)):
        mm = _PDF_AS_MARK.match(lines[j])
        if not mm:
            continue
        k = j + 1
        while k < len(lines) and (not lines[k].strip() or _PDF_NOISE.match(lines[k])):
            k += 1
        if k < len(lines) and _PDF_AS_HEAD.match(lines[k].replace("\x0c", "")):
            marks.append((j, int(mm.group(1))))
    # keep only the strictly sequential 1,2,3… run
    seq: list[tuple[int, int]] = []
    expected = 1
    for j, n in marks:
        if n == expected:
            seq.append((j, n))
            expected += 1
    for idx, (j, n) in enumerate(seq):
        end = seq[idx + 1][0] if idx + 1 < len(seq) else len(lines)
        block = [ln.replace("\x0c", "") for ln in lines[j + 1:end]
                 if not _PDF_NOISE.match(ln) and ln.strip() != "\x0c"]
        text = re.sub(r"\s+", " ", " ".join(block)).strip()
        hm = _PDF_AS_HEAD.match(text)
        if not hm:
            continue
        art_ref, body = hm.group(1), hm.group(2)
        # store the FULL statement verbatim ("Agreed statement concerning Article N: <body>")
        _add_agreed_statement(rs, cite_prefix, n, art_ref, text)


# ── mode: WTO-hosted HTML (TRIPS) ────────────────────────────────────────────
# Body heading: <h2 class="web_h2 web_ita …">Article N[bis]</h2> then marginal note in
# <p class="center">…</p>. Anchor <a name="artN"> precedes it.
_WTO_HEAD = re.compile(
    r"<h2[^>]*class=\"[^\"]*web_ita[^\"]*\"[^>]*>\s*Article\s+(\d+)\s*(bis|ter)?\s*</h2>",
    re.I)


def _parse_wto_html(path: str, cite_prefix: str) -> RecordSet:
    html = open(path, encoding="utf-8", errors="replace").read()
    heads = list(_WTO_HEAD.finditer(html))
    rs = RecordSet()
    for i, m in enumerate(heads):
        token = f"{m.group(1)}{m.group(2) or ''}"
        end = heads[i + 1].start() if i + 1 < len(heads) else min(len(html), m.end() + 20000)
        seg = html[m.end():end]
        # The LAST article (73) runs to end-of-page and would swallow the ANNEX + APPENDIX +
        # footnotes block (fabricating 73(1)-(9) from the annex's numbered paras). Cut there.
        cut = re.search(r"ANNEX\s+TO\s+THE\s+TRIPS\s+AGREEMENT", seg, re.I)
        if cut:
            seg = seg[:cut.start()]
        # marginal note = first centred paragraph; body = everything after it (so the note
        # isn't duplicated at the head of the text).
        hm = re.search(r"<p[^>]*class=\"[^\"]*center[^\"]*\"[^>]*>(.*?)</p>", seg, re.S | re.I)
        heading = _clean(hm.group(1)) if hm else None
        body = _clean(seg[hm.end():] if hm else seg)
        _add_article(rs, cite_prefix, i, token, heading, body)
    _parse_trips_annex(rs, cite_prefix, html)
    return rs


def _parse_trips_annex(rs: RecordSet, cite_prefix: str, html: str) -> None:
    """Ingest the TRIPS Annex (and its Appendix) as their OWN provisions, verbatim. The Annex
    runs from "ANNEX TO THE TRIPS AGREEMENT" to "APPENDIX TO THE ANNEX"; the Appendix from there
    to the "<h4>Notes:</h4>" block (the treaty-wide footnotes, which are NOT annex content and are
    left out). Body numbered paras (1.,2.…) and inline footnote markers (1),(2) are kept verbatim
    but NOT minted as pinpoint children — these are 'annex' text, not addressable sub-paragraphs."""
    # Anchor on the real annex/appendix HEADINGS (`<h1 class="web_h2">ANNEX…</h1>`), NOT the
    # earlier table-of-contents menu links to the same words.
    a = re.search(r"<h1[^>]*>\s*ANNEX\s+TO\s+THE\s+TRIPS\s+AGREEMENT\s*</h1>", html, re.I)
    if not a:
        return
    ap = re.search(r"<h1[^>]*>\s*APPENDIX\s+TO\s+THE\s+ANNEX", html[a.end():], re.I)
    notes = re.search(r"<h4>\s*Notes:", html[a.end():], re.I)
    ap_start = a.end() + ap.start() if ap else None
    notes_start = a.end() + notes.start() if notes else len(html)
    annex_end = ap_start if ap_start is not None else notes_start
    annex_body = _clean(html[a.start():annex_end])
    if annex_body:
        rs.add(kind="schedule", label="Annex", heading="Annex to the TRIPS Agreement",
               sort_int=_AS_SORT_BASE, sort_suffix="", role="schedule",
               citation=f"{cite_prefix} Annex", content=annex_body)
    if ap_start is not None:
        appx_body = _clean(html[ap_start:notes_start])
        if appx_body:
            rs.add(kind="schedule", label="Appendix to the Annex",
                   heading="Appendix to the Annex to the TRIPS Agreement",
                   sort_int=_AS_SORT_BASE + 1, sort_suffix="", role="schedule",
                   citation=f"{cite_prefix} Annex Appendix", content=appx_body)


# ── public parse() ───────────────────────────────────────────────────────────
_MODES = {"wipo_html": _parse_wipo_html, "wipo_pdf": _parse_wipo_pdf,
          "wto_html": _parse_wto_html}


def parse(artifact_path: str, cite_prefix: str, mode: str) -> RecordSet:
    """Parse a retained treaty artifact into a RecordSet of provisions. `mode` selects the
    source shape (wipo_html | wipo_pdf | wto_html)."""
    if mode not in _MODES:
        raise SystemExit(f"unknown parse mode: {mode}")
    return _MODES[mode](artifact_path, cite_prefix)


def instrument(cfg: dict) -> dict:
    return dict(jurisdiction="INT", type="treaty", ext_id_scheme="TREATY",
                ext_id=cfg["slug"], official_citation=cfg["official_citation"],
                title=cfg["title"])


def ingest_one(key: str, db_path: str, allow_corpus: bool,
               artifact_override: str | None = None) -> dict:
    cfg = TREATIES[key]
    path = artifact_override or os.path.join(_ART, cfg["artifact"])
    if not os.path.exists(path):
        raise SystemExit(f"artifact not found: {path}")
    rs = parse(path, cfg["cite_prefix"], cfg["mode"])
    stats = run_ingest(
        db_path, instrument(cfg), rs, cfg["source_url"],
        allow_corpus=allow_corpus,
        is_authentic=1, is_consolidated=0, is_official_language=1,   # authentic official text
        version_label=cfg["version_label"], fts_title=cfg["official_citation"])
    stats["key"] = key
    stats["official_citation"] = cfg["official_citation"]
    return stats


def main() -> None:
    ap = argparse.ArgumentParser(description="Ingest core copyright treaties (WIPO Lex / WTO).")
    ap.add_argument("--treaty", required=True,
                    help="one of: " + ", ".join(TREATIES) + ", or 'all'")
    ap.add_argument("--db", required=True)
    ap.add_argument("--artifact", default=None, help="override the retained artifact path")
    ap.add_argument("--allow-corpus", action="store_true")
    a = ap.parse_args()
    keys = list(TREATIES) if a.treaty == "all" else [a.treaty]
    for k in keys:
        if k not in TREATIES:
            raise SystemExit(f"unknown treaty '{k}' (choose from: {', '.join(TREATIES)}, all)")
    for k in keys:
        s = ingest_one(k, a.db, a.allow_corpus, a.artifact if a.treaty != "all" else None)
        arts = s["by_kind"].get("article", 0)
        paras = s["by_kind"].get("paragraph", 0)
        print(f"[{k}] instrument #{s['instrument_id']}  {s['official_citation']}")
        print(f"     provisions {s['provisions']}  (articles {arts}, paragraphs {paras})")
        print(f"     versions   new {s['versions_new']}, unchanged {s['versions_unchanged']}")


if __name__ == "__main__":
    main()
