"""Tier-2 ingest — Canada, Copyright Act (R.S.C., 1985, c. C-42).

Follows the reference template (ingest_de_urhg.py): an INSTRUMENT dict + a `parse()` that
returns a `_common.RecordSet` + a thin `main()`. All DB/versioning/idempotency lives in
`_common`.

Source: the OFFICIAL consolidated Justice Laws XML for C-42 (laws-lois.justice.gc.ca). This
is an OFFICIAL, authentic, consolidated ENGLISH text (Canada enacts bilingually; the English
is authentic) → is_official_language=1, is_authentic=1, is_consolidated=1.

Structure of the XML:
  * The Act is a flat sequence (max <Section> nesting depth = 1 — sections never nest).
  * <Heading level="1"> with a <Label>PART …</Label> = a formal Part → kind='part'. Other
    level-1 headings (Short Title, Interpretation) carry no Part label and are skipped as
    grouping-only rubrics (they still let their sections sit at top level).
  * Each <Section> carries <Label> (the number, incl. decimals: 2.1, 14.1, 29.21) and a
    <MarginalNote> (its heading). Subsections/Definitions nest inside; their text is folded
    into the section's operative content (tags stripped) so the section versions + searches.
  * Schedules contain no Sections and are not ingested as citable units here.

NO fake law: every provision's text is stripped from the fetched Section block.

Run:
    python src/store/ingest_ca.py --db db/corpus.db --allow-corpus \
        --html spike/artifacts/ca_copyright.html \
        --source-url https://laws-lois.justice.gc.ca/eng/acts/C-42/FullText.html
"""
from __future__ import annotations

import argparse
import html as htmlmod
import re

from _common import RecordSet, ordinal, run_ingest

INSTRUMENT = dict(jurisdiction="CA", type="statute",
                  official_citation="Copyright Act (R.S.C. 1985, c. C-42)",
                  ext_id_scheme="NATIONAL", ext_id="ca-c-42",
                  title="Copyright Act (R.S.C., 1985, c. C-42)")

# A formal Part: a level-1 Heading whose <Label> is "PART …" (e.g. "PART I").
_PART_RE = re.compile(
    r'<Heading\b[^>]*\blevel="1"[^>]*>(?P<inner>(?:(?!</Heading>).)*?)</Heading>', re.S)
# A top-level Section block (sections never nest, so a non-greedy match to </Section> is safe).
_SECTION_RE = re.compile(r'<Section\b[^>]*>(?P<inner>(?:(?!</Section>).)*?)</Section>', re.S)
_LABEL_RE = re.compile(r'<Label>(.*?)</Label>', re.S)
_MARGINAL_RE = re.compile(r'<MarginalNote\b[^>]*>(.*?)</MarginalNote>', re.S)


def _clean(frag: str) -> str:
    frag = re.sub(r"<[^>]+>", " ", frag or "")
    return re.sub(r"\s+", " ", htmlmod.unescape(frag)).strip()


def _section_content(inner: str) -> str:
    """Operative text of a section: the whole Section block minus the leading Label and the
    HistoricalNote provenance trailer, tags stripped. MarginalNotes (headings) are dropped so
    the body is the enacted text, not editorial rubrics."""
    body = _MARGINAL_RE.sub(" ", inner)                     # drop marginal-note headings
    body = re.sub(r'<Label>.*?</Label>', " ", body, count=1, flags=re.S)  # drop the section number
    body = re.sub(r'<HistoricalNote\b.*?</HistoricalNote>', " ", body, flags=re.S)  # drop provenance
    return _clean(body)


def parse(html_path: str) -> RecordSet:
    xml = open(html_path, encoding="utf-8", errors="replace").read()
    # Cut the "RELATED PROVISIONS" appendix (<Schedule id="RelatedProvs">): it reproduces sections
    # of amending Acts (s.280, s.54.1, …) that are NOT part of C-42 — ingesting them mints fake
    # Copyright-Act citations (prime rule 1: no fake law).
    cut = xml.find('RelatedProvs')
    if cut != -1:
        xml = xml[:cut]
    rs = RecordSet()

    # Build one document-ordered marker list of Parts and Sections, so each section attaches
    # to the Part that most recently opened before it.
    markers = []
    for m in _PART_RE.finditer(xml):
        lab = _LABEL_RE.search(m.group("inner"))
        if lab and re.match(r'\s*PART\b', lab.group(1), re.I):
            markers.append(("part", m.start(), lab.group(1).strip(), m.group("inner")))
    for m in _SECTION_RE.finditer(xml):
        markers.append(("section", m.start(), None, m.group("inner")))
    markers.sort(key=lambda t: t[1])

    open_part = None                                        # local id of the current Part
    for i, (kind, _pos, part_label, inner) in enumerate(markers):
        if kind == "part":
            num = re.sub(r'(?i)^\s*PART\s+', "", part_label)   # "PART I" → "I"
            tt = re.search(r'<TitleText>(.*?)</TitleText>', inner, re.S)
            si, su = ordinal(num, i)
            open_part = rs.add(parent_local=None, kind="part", label=part_label,
                               heading=_clean(tt.group(1)) if tt else None,
                               sort_int=si, sort_suffix=su,
                               citation=f"Copyright Act (Canada) {part_label}")
        else:
            lab = _LABEL_RE.search(inner)
            if not lab:
                continue
            num = _clean(lab.group(1))
            # A real section number is bare (1, 2.1, 14.1). A parenthesized first Label means
            # this <Section> is a transitional fragment from the "RELATED PROVISIONS" appendix
            # (an amending Act's own subsection, e.g. "1993, c. 44, ss. 60(2)") — not a section
            # of C-42; skip it rather than mint a bogus "s. (2)" citation.
            if num.startswith("("):
                continue
            note = _MARGINAL_RE.search(inner)
            si, su = ordinal(num, i)                        # decimals/letters fall back to doc order
            body = _section_content(inner)
            rs.add(parent_local=open_part, kind="section", label=f"s. {num}",
                   heading=_clean(note.group(1)) if note else None,
                   sort_int=si, sort_suffix=su,
                   citation=f"Copyright Act (Canada) s. {num}", content=body or None)
    return rs


def main() -> None:
    ap = argparse.ArgumentParser(description="Ingest Canada Copyright Act (Justice Laws XML, EN).")
    ap.add_argument("--db", required=True)
    ap.add_argument("--html", required=True)
    ap.add_argument("--source-url", required=True)
    ap.add_argument("--point-in-time", default=None)
    ap.add_argument("--allow-corpus", action="store_true")
    a = ap.parse_args()
    s = run_ingest(a.db, INSTRUMENT, parse(a.html), a.source_url, point_in_time=a.point_in_time,
                   allow_corpus=a.allow_corpus, is_official_language=1,   # authentic English
                   version_label="laws-lois.justice.gc.ca (consolidated EN)",
                   fts_title="Copyright Act (Canada)")
    print(f"instrument #{s['instrument_id']}  Canada Copyright Act — {s['provisions']} provisions "
          f"({s['by_kind'].get('section', 0)} sections, {s['by_kind'].get('part', 0)} parts); "
          f"versions new {s['versions_new']}, unchanged {s['versions_unchanged']} "
          f"(is_official_language=1)")


if __name__ == "__main__":
    main()
