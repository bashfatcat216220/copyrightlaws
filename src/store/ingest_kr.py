"""Tier-2 ingest — Republic of Korea, Copyright Act.

Per the Tier-2 fan-out contract (see ingest_de_urhg.py): an INSTRUMENT dict + a `parse()`
returning a `_common.RecordSet` + a thin `main()`. All DB/versioning/idempotency lives in
`_common`. NEVER originates text — every article body is lifted from the fetched source.

Source: the Korea Law Translation Center (KLRI) English full text of the Copyright Act
(Act No. 432 of 1957, wholly amended; current), served at
elaw.klri.re.kr/eng_service/lawViewContent.do?hseq=32626. The English is a government-
provided TRANSLATION (authentic language = Korean) and KLRI labels its translations
"for reference only, neither official nor legally effective" → `run_ingest(...,
is_official_language=0)` (flagged in the UI).

Structure (from the KLRI HTML):
    CHAPTER (div.chapter) → SECTION (div.section) → SubSection (div.subsection)
      → Article N (div.JO / div.articletitle) — the operative, versioned unit.
Korea uses ARTICLES with "-N" insertions (e.g. Article 2-2, Article 35-3 fair use), which
`_common.ordinal` handles: "35-3" → (35, "") so it document-orders after 35 within the
single authoritative fetch. Articles RAIL in the reader (kind='article'); containers are
chapter / subchapter (Section) / subsection (SubSection). Citations: "Copyright Act (Korea)
Art. N".

Run:
    python src/store/ingest_kr.py --db db/corpus.db --allow-corpus \
        --html spike/artifacts/kr_copyright.html \
        --source-url https://elaw.klri.re.kr/eng_service/lawViewContent.do?hseq=32626
"""
from __future__ import annotations

import argparse
import html as htmlmod
import re

from _common import RecordSet, ordinal, run_ingest

INSTRUMENT = dict(jurisdiction="KR", type="statute",
                  official_citation="Copyright Act (Korea)",
                  ext_id_scheme="NATIONAL", ext_id="kr-copyright",
                  title="Copyright Act, Republic of Korea")

# Structural blocks in the KLRI HTML. Chapter → 'chapter', Section → 'subchapter',
# SubSection → 'subsection'; an Article (div.JO) is the operative provision.
_CHAPTER = re.compile(r'<div class="chapter"[^>]*>(.*?)</div>', re.S)
_SECTION = re.compile(r'<div class="section"[^>]*>(.*?)</div>', re.S)
_SUBSEC = re.compile(r'<div class="subsection"[^>]*>(.*?)</div>', re.S)
# A structural container or article block, in document order.
_BLOCK = re.compile(
    r'<div class="(chapter|section|subsection)"[^>]*>(.*?)</div>'
    r'|<div class="JO" id="\d+">(.*?)(?=<div class="(?:JO|CT|ST|UT|addenda)"|\Z)',
    re.S)
# The article header cell: "Article 35-3 (Fair Use of Works, etc.)".
_ARTTITLE = re.compile(r'<div class="articletitle">(.*?)</table>', re.S)
_ARTNUM = re.compile(r'Article\s+(\d+(?:-\d+)?)\s*(?:\((.*?)\))?', re.S)

# ── Addenda (부칙) ─────────────────────────────────────────────────────────────
# After the last numbered article (Art. 142) the KLRI HTML carries the transitional/
# enforcement Addenda: nine `<div class="addenda">` header blocks, one per amending Act
# (plus the unlabeled base ADDENDA). Each addendum is a SCHEDULE container; its internal
# "Article N …" units are its schedule_para provisions (TRIPS-annex precedent in
# ingest_treaty: kind='schedule'/'schedule_para', role='schedule'). Nothing is originated —
# every body is lifted verbatim from the artifact via the same _clean() used for the body.
_ADDENDA_HEAD = re.compile(r'<div class="addenda">(.*?)</div>', re.S)
# An addendum's internal article header: `<div class="article"><span> … </span></div>`. Its
# body is whatever follows up to the NEXT internal article header or the end of the block.
_AD_ART = re.compile(r'<div class="article">\s*<span>(.*?)</span>\s*</div>', re.S)
# Leading "Article(s) N …" prefix of an addendum article header. group(1) = first number
# (sort order). Whatever follows is the marginal note "(Enforcement Date)" OR an inline
# tombstone "Omitted." / "through 7 Omitted." — captured so a bodyless article keeps its
# source notice (→ _common.is_repealed sets status='repealed') instead of blanking.
_AD_ARTNUM = re.compile(r'Articles?\s+(\d+)(?:\s+through\s+\d+)?\s*(.*)', re.S)
# Act No. / date label inside an addenda header ("ADDENDA <Act No. 8852, Feb. 29, 2008>").
_AD_ACTNO = re.compile(r'Act\s+No\.\s*(\d+)', re.S)
_AD_SORT_BASE = 20000   # file the addenda after the whole numbered body (Art. 142 → doc order)


def _clean(frag: str) -> str:
    frag = re.sub(r"<!--.*?-->", " ", frag or "", flags=re.S)   # drop HTML comments (incl. "-->")
    frag = re.sub(r"<[^>]+>", " ", frag)
    frag = re.sub(r"<[^>]*$", " ", frag)      # drop a dangling unclosed tag at the very end (e.g. "<div")
    frag = frag.replace("법령보기 화면", " ")  # table caption "법령보기 화면"
    # F-KR1: upstream encoding artifact — KLRI serves "Author¡?s" where it means "Author’s"
    # (a proper "’" appears elsewhere in the same file). Normalize known mojibake, never law.
    frag = frag.replace("¡?", "’")
    return re.sub(r"\s+", " ", htmlmod.unescape(frag)).strip()


def _parse_addenda(rs: RecordSet, addenda_html: str) -> None:
    """Parse the trailing Addenda (부칙) region — everything from the first `class="addenda"`
    header to end-of-document. Each `<div class="addenda">` starts a new addendum; its region
    runs to the next header (or EOF). The addendum is a kind='schedule' container and its
    internal "Article N …" units become kind='schedule_para' children (role='schedule').

    Citations disambiguate by the header's Act No. ("… Addenda (Act No. 8852)"); the single
    unlabeled base ADDENDA (no Act No.) cites as "… Addenda" — already unique because every
    other block carries an Act number. No number is ever invented (prime rule 1)."""
    heads = list(_ADDENDA_HEAD.finditer(addenda_html))
    for hi, hm in enumerate(heads):
        label = _clean(hm.group(1))                        # "ADDENDA <Act No. 8852, Feb. 29, 2008>"
        seg_end = heads[hi + 1].start() if hi + 1 < len(heads) else len(addenda_html)
        seg = addenda_html[hm.end():seg_end]               # this addendum's provision region
        actno = _AD_ACTNO.search(label)
        # Container citation: disambiguate by Act No.; the unlabeled base block has none.
        cite = (f"Copyright Act (Korea) Addenda (Act No. {actno.group(1)})" if actno
                else "Copyright Act (Korea) Addenda")
        sched = rs.add(parent_local=None, kind="schedule", label=label, heading=label,
                       sort_int=_AD_SORT_BASE + hi, sort_suffix="", role="schedule",
                       citation=cite, content=None)

        arts = list(_AD_ART.finditer(seg))
        if not arts:
            # No internal article structure — a single enforcement clause (e.g. Act No. 9529:
            # "This Act shall enter into force …"). Store it verbatim as one schedule_para.
            body = _clean(seg)
            if body:
                rs.add(parent_local=sched, kind="schedule_para", label="Enforcement",
                       heading=None, sort_int=_AD_SORT_BASE + hi * 100 + 1, sort_suffix="",
                       role="schedule", citation=f"{cite} — Enforcement", content=body)
            continue

        for ai, am in enumerate(arts):
            head = _clean(am.group(1))                      # "Article 1 (Enforcement Date)"
            a_end = arts[ai + 1].start() if ai + 1 < len(arts) else len(seg)
            body = _clean(seg[am.end():a_end])
            nm = _AD_ARTNUM.match(head)
            n = int(nm.group(1)) if nm else ai + 1
            if not body:
                # e.g. "Article 15 Omitted." / "Articles 2 through 7 Omitted." — no body div;
                # the source's own notice lives in the header. Keep the trailing notice verbatim
                # ("Omitted.") so _common.is_repealed flags status='repealed' (never blank).
                trailing = (nm.group(2).strip() if nm and nm.group(2) else "")
                body = trailing or head
            rs.add(parent_local=sched, kind="schedule_para", label=head, heading=None,
                   sort_int=_AD_SORT_BASE + hi * 100 + n, sort_suffix="", role="schedule",
                   citation=f"{cite} — {head}", content=body)


def parse(html_path: str) -> RecordSet:
    html = open(html_path, encoding="utf-8", errors="replace").read()
    # Split the numbered body (Arts 1–142) from the trailing transitional Addenda. The body is
    # parsed exactly as before (unchanged); the addenda region is captured separately below.
    end = html.find('class="addenda"')
    addenda_html = ""
    if end != -1:
        # back up to the opening "<div " of that first addenda header so the region is intact
        div_start = html.rfind("<div ", 0, end)
        addenda_html = html[div_start if div_start != -1 else end:]
        # Segmentation boundary (rule 3): cut the trailing page footer so the last addendum
        # ("Act No. 12137") does not swallow the "Last updated : …" chrome as body text.
        foot = addenda_html.find('class="lastUpdate"')
        if foot != -1:
            addenda_html = addenda_html[:addenda_html.rfind("<div ", 0, foot)]
        html = html[:end]

    rs = RecordSet()
    container = {"chapter": None, "subchapter": None, "subsection": None}  # open container local ids
    doc_i = 0

    for m in _BLOCK.finditer(html):
        ctype, ctext, jobody = m.group(1), m.group(2), m.group(3)
        doc_i += 1

        if ctype == "chapter":
            heading = _clean(ctext)                       # "CHAPTER I GENERAL PROVISIONS"
            container["subchapter"] = container["subsection"] = None
            si, su = ordinal(str(doc_i), doc_i)
            container["chapter"] = rs.add(parent_local=None, kind="chapter", label=heading,
                                          heading=heading, sort_int=si, sort_suffix=su,
                                          citation=f"Copyright Act (Korea) — {heading}")
            continue
        if ctype == "section":
            heading = _clean(ctext)                       # "Section 1 Works"
            container["subsection"] = None
            si, su = ordinal(str(doc_i), doc_i)
            container["subchapter"] = rs.add(parent_local=container["chapter"], kind="subchapter",
                                             label=heading, heading=heading, sort_int=si,
                                             sort_suffix=su,
                                             citation=f"Copyright Act (Korea) — {heading}")
            continue
        if ctype == "subsection":
            heading = _clean(ctext)                       # "SubSection 1 Kinds of ..."
            si, su = ordinal(str(doc_i), doc_i)
            parent = container["subchapter"] or container["chapter"]
            container["subsection"] = rs.add(parent_local=parent, kind="subsection",
                                             label=heading, heading=heading, sort_int=si,
                                             sort_suffix=su,
                                             citation=f"Copyright Act (Korea) — {heading}")
            continue

        # else: an article block (jobody set)
        tm = _ARTTITLE.search(jobody or "")
        head = _clean(tm.group(1)) if tm else ""
        am = _ARTNUM.match(head)
        if not am:
            continue
        num, title = am.group(1), (am.group(2) or None)
        body = _clean(jobody[tm.end():]) if tm else _clean(jobody)
        if not body:
            # Repealed articles carry their notice INLINE in the title line and have no body,
            # e.g. "Article 121 Deleted. <by Act No. 9625, Apr. 22, 2009>" — keep it verbatim
            # (the source's own repeal notice) so the provision isn't blank. No fabricated text.
            trailing = head[am.end():].strip()
            if trailing:
                body = trailing
        si, su = ordinal(num, doc_i)                       # "35-3" → (35,"") → doc order within 35s
        parent = container["subsection"] or container["subchapter"] or container["chapter"]
        rs.add(parent_local=parent, kind="article", label=f"Article {num}",
               heading=title, sort_int=si, sort_suffix=su,
               citation=f"Copyright Act (Korea) Art. {num}", content=body or None)

    if addenda_html:
        _parse_addenda(rs, addenda_html)
    return rs


def main() -> None:
    ap = argparse.ArgumentParser(description="Ingest Korea Copyright Act (KLRI EN translation).")
    ap.add_argument("--db", required=True)
    ap.add_argument("--html", required=True, help="path to kr_copyright.html (KLRI lawViewContent)")
    ap.add_argument("--source-url", required=True)
    ap.add_argument("--point-in-time", default=None)
    ap.add_argument("--allow-corpus", action="store_true")
    a = ap.parse_args()
    s = run_ingest(a.db, INSTRUMENT, parse(a.html), a.source_url, point_in_time=a.point_in_time,
                   allow_corpus=a.allow_corpus, is_official_language=0,   # English translation
                   version_label="KLRI elaw.klri.re.kr (EN translation)",
                   fts_title="Copyright Act (Korea)")
    print(f"instrument #{s['instrument_id']}  Korea Copyright Act — {s['provisions']} provisions "
          f"({s['by_kind'].get('article', 0)} articles); versions new {s['versions_new']}, "
          f"unchanged {s['versions_unchanged']} (is_official_language=0)")


if __name__ == "__main__":
    main()
