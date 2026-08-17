"""Tier-2 ingest — Japan, Copyright Act (Act No. 48 of 1970, as amended).

Per the Tier-2 fan-out contract (see ingest_de_urhg.py): an INSTRUMENT dict + a `parse()`
returning a `_common.RecordSet` + a thin `main()`. All DB/versioning/idempotency lives in
`_common`. NEVER originates text — every article body is lifted from the fetched source.

Source: the Japanese Law Translation database (japaneselawtranslation.go.jp), the Japanese
government's official English-translation portal. This is a GOVERNMENT TRANSLATION (the
authentic language is Japanese; the site itself states only the Japanese text has legal
effect) → `run_ingest(..., is_official_language=0)` (flagged in the UI), but it is an
authentic, consolidated rendering of the Act as amended (is_authentic=1, is_consolidated=1).

Structure (from the clean HTML on view/3379/en):
    Chapter I..VIII → Section N → Subsection N → Article N
Not every chapter has sections/subsections; an article hangs off its nearest open container.
Articles carry hyphenated insertions (Article 30-2, Article 122-2) — handed to `_jp_ordinal`,
which sorts an insertion after its base article and before the next integer
((120,'') < (120,'-02') < (121,''), branch zero-padded for the BINARY collation). Articles
RAIL in the reader (kind='article', operative content); containers are
chapter/section/subsection.

Scope: the Act's OPERATIVE MAIN BODY (Chapters I–VIII, Articles 1–124) PLUS the trailing
"Supplementary Provisions" (附則) blocks — the original 1970 Act's 附則 plus one block per
amending act. These carry OPERATIVE transitional rules (application to pre-existing
works/phonograms, effective dates), so they are captured — but they are NOT part of the
main-body article sequence: each block locally RE-numbers "Article 1", "Article 2"…, so if
merged into the body they would collide dozens of times over. Model (TRIPS-annex precedent,
see ingest_treaty.py):

  * each Supplementary-Provisions block  → a kind='schedule' CONTAINER, role='schedule',
    citation DISAMBIGUATED by its amending act/date, e.g.
    'Copyright Act (Japan) Supplementary Provisions (Act No. 48 of 1970)'.
  * each "Article N" inside a block       → a kind='schedule_para' child, role='schedule',
    cited under its container ('… Supplementary Provisions (Act No. …) Art. N'), so the
    restarting numbering never collides with the main body or across blocks.
  * a block with NO "Article N" divs (just numbered paragraphs) has no children; its full
    text is stored on the container itself.

The main-body run is bounded first-Chapter → first `SupplProvision` block (UNCHANGED); the
supplementary run is bounded first `SupplProvision` block → the page's <form>/footer, so the
last block's last article never swallows the footer scripts (segmentation rule 3).

Citations: "Copyright Act (Japan) Art. 30" — stable, unique across the main body.

Run:
    python src/store/ingest_jp.py --db db/corpus.db --allow-corpus \
        --html spike/artifacts/jp_copyright.html \
        --source-url https://www.japaneselawtranslation.go.jp/en/laws/view/3379/en
"""
from __future__ import annotations

import argparse
import html as htmlmod
import re

from _common import RecordSet, ordinal, run_ingest

INSTRUMENT = dict(jurisdiction="JP", type="statute",
                  official_citation="Copyright Act (Act No. 48 of 1970)",
                  ext_id_scheme="NATIONAL", ext_id="jp-copyright-1970",
                  title="Copyright Act (Act No. 48 of 1970), Japan")

# Structural markers in document order. Each alternative captures either a container title
# (Chapter/Section/Subsection) or the opening of an Article div (whose number/caption we read
# from the segment that follows). japaneselawtranslation renders these as flat, labelled divs.
_MARK = re.compile(
    r'<div class="Chapter anchor"[^>]*>\s*<div class="ChapterTitle">([^<]*)</div>'
    r'|<div class="Section anchor"[^>]*>\s*<div class="SectionTitle">([^<]*)</div>'
    r'|<div class="Subsection anchor"[^>]*>\s*<div class="SubsectionTitle">([^<]*)</div>'
    r'|<div class="Article anchor" id="[^"]*">')
_ART_TITLE = re.compile(r'<span class="ArticleTitle">Article ([0-9]+(?:-[0-9]+)?)</span>')
_CAPTION = re.compile(r'<div class="ArticleCaption">([^<]*)</div>')
# Container title splits into a label ("Chapter I") + heading (the rest).
_CONTAINER = re.compile(r'^(Chapter|Section|Subsection)\s+(\S+)\s*(.*)$')

# ── Supplementary Provisions (附則) ──────────────────────────────────────────
# A block opens with `<div class="SupplProvision anchor" id="je_sN">` then a
# `<div class="SupplProvisionLabel"><span>Supplementary Provisions[Act No. …]</span></div>`.
# The label carries the amending act (number + date) — the disambiguator for the block's
# citation. The original 1970 Act's own 附則 and the file's last block carry a bare
# "[Extract]" (no act); the original maps to the enacting Act No. 48 of 1970, the bare last
# block falls back to its stable DOM id.
_SUPPL = re.compile(r'<div class="SupplProvision anchor" id="([^"]*)">\s*'
                    r'<div class="SupplProvisionLabel"><span>(.*?)</span></div>', re.S)
# "Act No. 49 of May 18, 1978" / "Act No. 75 of 2005" / the malformed "Act No. 23 May 1, of
# 1984" → act number + the (only) 4-digit year in the label.
_SUPPL_ACT = re.compile(r'Act No\.\s*(\d+)\b.*?(\d{4})', re.S)
# An Article inside a block: its opening div, then (tag-tolerant) caption + title span.
_SUPPL_ART = re.compile(r'<div class="Article anchor" id="[^"]*">')
_SUPPL_CAP = re.compile(r'<div class="ArticleCaption">(.*?)</div>', re.S)


def _clean(frag: str) -> str:
    frag = re.sub(r"<[^>]+>", " ", frag or "")
    return re.sub(r"\s+", " ", htmlmod.unescape(frag)).strip()


def _jp_ordinal(num: str, doc_index: int) -> tuple[int, str]:
    """Sort key for a Japanese article number, incl. hyphenated insertions ('120-2').
    `_common.ordinal` can't read the hyphen form and fell back to DOCUMENT ORDER, which
    filed the insertions after the whole chapter (Ch. VIII read 119…124, then 120-2,
    121-2, 122-2 — the Wave-E sort defect). An inserted article must sort AFTER its base
    and BEFORE the next integer: (120,'') < (120,'-02') < (121,''). The branch is
    zero-padded so '-10' sorts after '-09' under the column's pinned BINARY collation
    (Art. 104-10 exists)."""
    m = re.match(r"^(\d+)(?:-(\d+))?$", num or "")
    if not m:
        return doc_index, ""
    return int(m.group(1)), (f"-{int(m.group(2)):02d}" if m.group(2) else "")


def _suppl_citation(block_id: str, label: str) -> str:
    """Block container citation, disambiguated by amending act/date. The original 1970 Act's
    own 附則 → the enacting act; a labelled amendment → its Act No. + year; a bare '[Extract]'
    with no act → the stable DOM id (never a fabricated act reference)."""
    base = "Copyright Act (Japan) Supplementary Provisions"
    if block_id == "je_s1":                        # original Act's own 附則
        return f"{base} (Act No. 48 of 1970)"
    m = _SUPPL_ACT.search(label)
    if m:
        return f"{base} (Act No. {m.group(1)} of {m.group(2)})"
    return f"{base} ({block_id})"                   # bare "[Extract]", no act → DOM id


def _parse_supplementary(html: str, rs: RecordSet) -> None:
    """Append every Supplementary-Provisions (附則) block as a schedule container + its
    articles as schedule_para children. Bounded first block → the page <form>/footer so a
    block's last article never swallows the footer scripts."""
    heads = list(_SUPPL.finditer(html))
    if not heads:
        return
    # hard stop: the post-body <form>/footer (falls back to </main>, then EOF).
    stop = html.find('<form id="hiddenForm"')
    if stop < 0:
        stop = html.find("</main>")
    if stop < 0:
        stop = len(html)
    base_sort = 10000                              # file AFTER the main body (Arts 1–124)
    for bi, h in enumerate(heads):
        end = heads[bi + 1].start() if bi + 1 < len(heads) else stop
        block = html[h.start():end]
        block_id, label = h.group(1), _clean(h.group(2))
        cite = _suppl_citation(block_id, label)
        arts = list(_SUPPL_ART.finditer(block))
        if arts:
            # Container groups the block's articles; its own text is the pre-article intro
            # (usually empty), never the whole block (that would duplicate the children).
            intro = _clean(block[h.end() - h.start():arts[0].start()]) or None
            cid = rs.add(kind="schedule", label=label or "Supplementary Provisions",
                         heading=label or None, sort_int=base_sort + bi, sort_suffix="",
                         role="schedule", citation=cite, content=intro)
            for ai, am in enumerate(arts):
                aend = arts[ai + 1].start() if ai + 1 < len(arts) else len(block)
                seg = block[am.end():aend]
                at = _ART_TITLE.search(seg)
                num = at.group(1) if at else str(ai + 1)
                cap = _SUPPL_CAP.search(seg)
                heading = (_clean(cap.group(1)).strip("() ") or None) if cap else None
                inner = seg
                if cap:
                    inner = inner.replace(cap.group(0), " ", 1)
                if at:
                    inner = _ART_TITLE.sub(" ", inner, count=1)
                content = _clean(inner) or None
                si, su = _jp_ordinal(num, ai)
                rs.add(parent_local=cid, kind="schedule_para", label=f"Article {num}",
                       heading=heading, sort_int=si, sort_suffix=su, role="schedule",
                       citation=f"{cite} Art. {num}", content=content)
        else:
            # No "Article N" divs — the block is bare numbered paragraphs; store its full
            # text (minus the label) on the container itself.
            body = _clean(block[h.end() - h.start():]) or None
            rs.add(kind="schedule", label=label or "Supplementary Provisions",
                   heading=label or None, sort_int=base_sort + bi, sort_suffix="",
                   role="schedule", citation=cite, content=body)


def parse(html_path: str) -> RecordSet:
    html = open(html_path, encoding="utf-8", errors="replace").read()
    # Operative main body: first Chapter div → first Supplementary Provisions block.
    start = html.find('<div class="Chapter anchor"')
    end = html.find('<div class="SupplProvision anchor"')
    if start < 0:
        raise SystemExit("could not locate the Act body (no Chapter anchor) — wrong source file?")
    body = html[start: end if end > start else len(html)]

    marks = list(_MARK.finditer(body))
    rs = RecordSet()
    container = {"chapter": None, "section": None, "subsection": None}   # open container local ids

    for i, m in enumerate(marks):
        seg = body[m.end(): marks[i + 1].start() if i + 1 < len(marks) else len(body)]
        ch_t, sc_t, sb_t = m.group(1), m.group(2), m.group(3)

        if ch_t or sc_t or sb_t:                       # a container marker
            title = _clean(ch_t or sc_t or sb_t)
            cm = _CONTAINER.match(title)
            unit = (cm.group(1) if cm else ("Chapter" if ch_t else "Section" if sc_t else "Subsection"))
            num = cm.group(2) if cm else ""
            heading = (cm.group(3).strip() or None) if cm else title
            kind = {"Chapter": "chapter", "Section": "section", "Subsection": "subsection"}[unit]
            si, su = ordinal(num, i)                    # roman/int → falls back to doc order
            label = f"{unit} {num}".strip()
            if kind == "chapter":
                container["section"] = container["subsection"] = None
                parent = None
            elif kind == "section":
                container["subsection"] = None
                parent = container["chapter"]
            else:  # subsection
                parent = container["section"] or container["chapter"]
            container[kind] = rs.add(parent_local=parent, kind=kind, label=label,
                                     heading=heading, sort_int=si, sort_suffix=su,
                                     citation=f"Copyright Act (Japan) {label}")
            continue

        # an Article div — read its number (from the segment) and caption
        at = _ART_TITLE.search(seg)
        if not at:
            continue
        num = at.group(1)
        cap = _CAPTION.search(seg)
        heading = _clean(cap.group(1)).strip("() ") or None if cap else None
        # Body text = the segment with its leading caption + the Article-title span removed, so
        # the stored content reads as clean provision prose (no duplicated caption/label).
        inner = seg
        if cap:
            inner = inner.replace(cap.group(0), " ", 1)
        inner = _ART_TITLE.sub(" ", inner, count=1)
        content = _clean(inner) or None
        parent = container["subsection"] or container["section"] or container["chapter"]
        si, su = _jp_ordinal(num, i)                    # hyphenated (30-2) → (30, '-02')
        rs.add(parent_local=parent, kind="article", label=f"Article {num}", heading=heading,
               sort_int=si, sort_suffix=su, citation=f"Copyright Act (Japan) Art. {num}",
               content=content)
    # Append the Supplementary Provisions (附則) as schedule containers + schedule_para
    # children (main body above is untouched — this only ADDS trailing records).
    _parse_supplementary(html, rs)
    return rs


def main() -> None:
    ap = argparse.ArgumentParser(description="Ingest Japan Copyright Act (Japanese Law "
                                             "Translation, government EN translation).")
    ap.add_argument("--db", required=True)
    ap.add_argument("--html", required=True, help="path to jp_copyright.html (view/3379/en)")
    ap.add_argument("--source-url", required=True)
    ap.add_argument("--point-in-time", default=None)
    ap.add_argument("--allow-corpus", action="store_true")
    a = ap.parse_args()
    s = run_ingest(a.db, INSTRUMENT, parse(a.html), a.source_url, point_in_time=a.point_in_time,
                   allow_corpus=a.allow_corpus, is_official_language=0,   # government EN translation
                   version_label="Japanese Law Translation (government EN translation)",
                   fts_title="Copyright Act (Japan)")
    print(f"instrument #{s['instrument_id']}  Japan Copyright Act — {s['provisions']} provisions "
          f"({s['by_kind'].get('article', 0)} articles, {s['by_kind'].get('chapter', 0)} chapters, "
          f"{s['by_kind'].get('section', 0)} sections, {s['by_kind'].get('subsection', 0)} "
          f"subsections, {s['by_kind'].get('schedule', 0)} supplementary-provisions blocks, "
          f"{s['by_kind'].get('schedule_para', 0)} supplementary articles); versions new "
          f"{s['versions_new']}, unchanged {s['versions_unchanged']} (is_official_language=0)")


if __name__ == "__main__":
    main()
