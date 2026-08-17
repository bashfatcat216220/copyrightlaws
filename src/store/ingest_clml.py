"""Provision-aware ingest for CLML (legislation.gov.uk) — CDPA 1988 slice.  DRAFT — FOR REVIEW.

Second source shape after USLM. Exercises the Body-vs-Schedule role split the spike found:
Body `P1`s are operative sections (role='enacting'); Schedule `P1`s are operative too but a
separate class (kind='schedule_para', role='schedule'); `BlockAmendment`/`Quotation` reproduce
OTHER Acts' words and are skipped. Same idempotency + corpus.db guard as ingest_uslm.

Run against a scratch/demo DB that has migration 001 applied:
    python src/store/ingest_clml.py --db db/corpus-demo.db --xml spike/artifacts/cdpa.xml \
        --source-url https://www.legislation.gov.uk/ukpga/1988/48/data.xml
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import sqlite3
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

SKIP = {"BlockAmendment", "Quotation"}          # reproduce OTHER instruments' words
PLEVEL = {"P2": "subsection", "P3": "paragraph", "P4": "subparagraph", "P5": "clause", "P6": "subclause"}
NUM_RE = re.compile(r"^\s*(\d+)([A-Za-z]*)\s*$")

INSTRUMENT = dict(jurisdiction="GB", type="statute", official_citation="CDPA 1988",
                  ext_id_scheme="ELI", ext_id="ukpga/1988/48",
                  title="Copyright, Designs and Patents Act 1988")


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


def ordinal(num_val: str | None, doc_index: int) -> tuple[int, str]:
    m = NUM_RE.match(num_val or "")
    if m:
        return int(m.group(1)), m.group(2).upper()
    return doc_index, ""


def _operative_text(el) -> str:
    parts: list[str] = []

    def rec(e):
        if local(e.tag) in SKIP:
            return
        if e.text and e.text.strip():
            parts.append(e.text.strip())
        for c in e:
            rec(c)
            if c.tail and c.tail.strip():
                parts.append(c.tail.strip())

    rec(el)
    return " ".join(parts)


# ── ukm effects metadata (prime rule 3: flag the caveats, never silently) ────
# The CLML <ukm:Metadata> block carries <ukm:UnappliedEffects>: amendments the editors have
# not yet applied to the consolidated text. An effect with RequiresApplied="true" means the
# TEXT WE STORE IS KNOWN NOT TO REFLECT IT — exactly what versions.has_unapplied_effects
# exists to surface. (RequiresApplied="false" effects need no text change — e.g. expired
# SIs, commencement-only entries — and are NOT flagged.) Found 2026-08-16: the snapshot
# carried a live RequiresApplied="true" effect (SI 2026/103 art. 4(1), affecting Pt. 2)
# but every version read has_unapplied_effects=0 because this metadata was never parsed.

def _parse_unapplied_effects(root) -> list[dict]:
    """Collect RequiresApplied="true" effects → [{'paths': [...], 'desc': '...'}].
    `paths` are the affected-provision URI tails under this act (e.g. 'part/II',
    'schedule/3/paragraph/17') from <ukm:AffectedProvisions>/<ukm:Section URI=…> —
    the source's own machine-readable scope, never inferred from prose."""
    act_uri = f"/{INSTRUMENT['ext_id']}/"                 # '/ukpga/1988/48/'
    effects: list[dict] = []
    for el in root.iter():
        if local(el.tag) != "UnappliedEffect" or el.get("RequiresApplied") != "true":
            continue
        paths: list[str] = []
        for ap in el:
            if local(ap.tag) != "AffectedProvisions":     # NOT AffectingProvisions (other acts)
                continue
            for s in ap.iter():
                uri = s.get("URI") if local(s.tag) == "Section" else None
                if uri and act_uri in uri:
                    paths.append(uri.split(act_uri, 1)[1].strip("/"))
        # One pinpoint is often split across Sections ('Sch. 3 ' + 'para. 17' → 'schedule/3'
        # AND 'schedule/3/paragraph/17') — keep only the MOST SPECIFIC path so a paragraph
        # effect never flags its whole schedule.
        paths = [p for p in paths if not any(q != p and q.startswith(p + "/") for q in paths)]
        if paths:
            effects.append({"paths": paths,
                            "desc": f"{el.get('Type')} by {el.get('AffectingYear')} "
                                    f"No. {el.get('AffectingNumber')}"})
    return effects


def _path_citation(path: str) -> str | None:
    """Map a legislation.gov.uk provision-URI tail to our stored citation key."""
    seg = path.split("/")
    if seg[0] == "part" and len(seg) == 2:
        return f"CDPA 1988 Part {seg[1]}"
    if seg[0] == "section" and len(seg) == 2:
        return f"CDPA 1988 s. {seg[1]}"
    if seg[0] == "schedule" and len(seg) == 2:
        return f"CDPA 1988 Schedule {seg[1]}"
    if seg[0] == "schedule" and len(seg) == 4 and seg[2] == "paragraph":
        return f"CDPA 1988 Schedule {seg[1]} para. {seg[3]}"
    return None                                           # e.g. crossheadings — not provisions


def _apply_unapplied_effects(conn, iid: int, effects: list[dict]) -> int:
    """Set has_unapplied_effects on the CURRENT versions inside each affected scope
    (the anchor provision + its whole subtree), and clear it everywhere else — the flag
    always mirrors the snapshot's own metadata, so it self-corrects once the effect is
    applied by the editors. Historic (is_current=0) versions are never touched."""
    ids: set[int] = set()
    for eff in effects:
        for path in eff["paths"]:
            cit = _path_citation(path)
            row = conn.execute("SELECT id FROM provisions WHERE instrument_id=? AND citation=?",
                               (iid, cit)).fetchone() if cit else None
            if not row:
                print(f"  ! unapplied effect scope not resolved to a provision: "
                      f"'{path}' ({eff['desc']}) — flag NOT set; check manually")
                continue
            for (pid,) in conn.execute(
                    "WITH RECURSIVE sub(id) AS (SELECT ? UNION ALL "
                    "SELECT p.id FROM provisions p JOIN sub ON p.parent_id=sub.id) "
                    "SELECT id FROM sub", (row[0],)):
                ids.add(pid)
    conn.execute("UPDATE versions SET has_unapplied_effects=0 "
                 "WHERE instrument_id=? AND is_current=1 AND has_unapplied_effects=1", (iid,))
    n = 0
    if ids:
        qs = ",".join("?" * len(ids))
        cur = conn.execute(
            f"UPDATE versions SET has_unapplied_effects=1 "
            f"WHERE instrument_id=? AND is_current=1 AND provision_id IN ({qs})",
            (iid, *ids))
        n = cur.rowcount
    return n


def parse(xml_path: str) -> tuple[str, list[dict], list[dict]]:
    root = ET.parse(xml_path).getroot()
    records: list[dict] = []
    seen: dict[str, int] = {}          # deterministic citation-uniqueness guard
    sched_para_seq: dict[str, int] = {}  # per-schedule positional counter for unnumbered <P> paras

    # Repealed CDPA sections carry an empty <Text/> (or a row-of-dots Title) and the repeal is
    # in a <Commentary> keyed by the Pnumber's <CommentaryRef>. Map id → notice so a repealed
    # section shows "S. 265 repealed (9.12.2001) by S.I. 2001/3949…" instead of a bare number.
    commentaries = {el.get("id"): re.sub(r"\s+", " ", "".join(el.itertext())).strip()
                    for el in root.iter() if local(el.tag) == "Commentary" and el.get("id")}

    def repeal_notice(c) -> str | None:
        ref = c.find(".//{*}CommentaryRef")
        if ref is None:
            return None
        txt = commentaries.get(ref.get("Ref"))
        return txt if txt and re.search(r"\b(repeal|revok|omitt|cease)", txt, re.I) else None

    def add(**kw) -> int:
        # KNOWN REFINEMENT: some CDPA schedule paragraphs still collide on citation (schedule
        # sub-structure the pinpoint doesn't yet capture). Disambiguate deterministically so a
        # collision never overwrites another provision's text; same input → same suffixes →
        # idempotent. Real fix later: full schedule-part pinpointing in the citation.
        cit = kw.get("citation")
        if cit is not None:
            seen[cit] = seen.get(cit, 0) + 1
            if seen[cit] > 1:
                kw["citation"] = f"{cit} #{seen[cit]}"
        kw["local_id"] = len(records) + 1
        records.append(kw)
        return kw["local_id"]

    def walk(el, parent_local, container_cite, sec_cite, subpath, group_title, in_sched, sched_no):
        sib = 0
        for c in el:
            name = local(c.tag)
            if name in SKIP:
                continue
            if name in ("Part", "Chapter"):
                # A Part/Chapter can appear inside a Schedule (CDPA Sch. 1 has Parts) — PRESERVE
                # the schedule context and make the citation container-relative, else the
                # schedule's paragraphs get misclassified as Body sections and collide.
                sib += 1
                kind = name.lower()
                label = _txt(_child(c, "Number")) or f"{name} {sib}"
                cite = f"{container_cite or 'CDPA 1988'} {label}"
                si, su = ordinal(re.sub(r"[^0-9]", "", label), sib)
                role = "schedule" if in_sched else "enacting"
                lid = add(parent_local=parent_local, kind=kind, label=label,
                          heading=_txt(_child(c, "Title")), sort_int=si, sort_suffix=su,
                          role=role, citation=cite, content=None)
                walk(c, lid, cite, None, [], None, in_sched, sched_no)
            elif name == "Schedule":
                # NOTE (Wave E, 2f/2g audit #11): Schedule 8 (Repeals) has NO P1/P2 paragraph
                # structure — its whole body is one <Tabular> (a 3-column repeals table), which
                # this walker does not inline, so the row below stays a content-less container.
                # Its table text is attached by the TARGETED `backfill_cdpa_sch8.py` (kept out
                # of this parser deliberately: inlining <Tabular> corpus-wide would change many
                # provisions' text on the next nightly refresh and fire false change alerts —
                # rule 7: CDPA is point-in-time monitored, fixes must be surgical).
                sib += 1
                num = (_txt(_child(c, "Number")) or f"SCHEDULE {sib}").replace("SCHEDULE", "").strip()
                label = f"Schedule {num}"
                cite = f"CDPA 1988 {label}"
                si, su = ordinal(num, sib)
                heading = _txt(c.find(".//{*}Title"))
                lid = add(parent_local=parent_local, kind="schedule", label=label, heading=heading,
                          sort_int=si, sort_suffix=su, role="schedule", citation=cite, content=None)
                walk(c, lid, cite, None, [], None, True, num)
            elif name == "P1group":
                # Some schedule paragraphs carry NO <Pnumber> — the source lists them as bare
                # <P> text inside a <P1group> (CDPA Schedule 5A, the s.296ZE permitted-acts list:
                # "section 29 (research and private study)", …). The numbered P1/PLEVEL handling
                # keys on <Pnumber>, so these unnumbered groups would be dropped. Capture each such
                # group as ONE positional schedule paragraph (source has no numbers → doc-order
                # label "para. <n>"). A group with any numbered <P1> child is left to normal walk.
                has_numbered = any(local(d.tag) in ("P1", "P1group") for d in c.iter()
                                   if d is not c)
                bare_ps = [d for d in c.iter() if local(d.tag) == "P"]
                if in_sched and not has_numbered and bare_ps:
                    text = " ".join(t for t in (_operative_text(p) for p in bare_ps) if t).strip()
                    if text:
                        sib += 1
                        key = str(sched_no)
                        sched_para_seq[key] = sched_para_seq.get(key, 0) + 1
                        pn = sched_para_seq[key]
                        # Positional citation is schedule-scoped (numbering runs across the whole
                        # schedule in document order, spanning its Parts) since the source gives
                        # no per-paragraph numbers: "CDPA 1988 Schedule 5A para. <n>".
                        base = f"CDPA 1988 Schedule {sched_no}"
                        cite = f"{base} para. {pn}"
                        add(parent_local=parent_local, kind="schedule_para",
                            label=f"para. {pn}", heading=None, sort_int=pn, sort_suffix="",
                            role="schedule", citation=cite, content=text, status="in_force")
                    continue
                walk(c, parent_local, container_cite, sec_cite, subpath,
                     _txt(_child(c, "Title")), in_sched, sched_no)
            elif name == "P1":
                sib += 1
                # normalize the section number — some CDPA point-in-time XML carries a trailing
                # dot on Pnumber ("205B."), which forked s.205B into a duplicate provision and
                # masked its change-monitor alert. Strip it so the citation is stable across snapshots.
                num = (_txt(_child(c, "Pnumber")) or "").rstrip(". ") or None
                si, su = ordinal(num, sib)
                content = _operative_text(c)
                status = "in_force"
                # _operative_text prefixes the section number; strip it to see if the BODY is an
                # empty <Text/> or a dots-only row → a repealed stub. Show the grounded repeal notice.
                body_only = re.sub(r"^\s*\d+[A-Za-z]*\.?\s*", "", content).strip()
                if not body_only or set(body_only) <= set(". "):
                    notice = repeal_notice(c)
                    if notice:
                        content, status = notice, "repealed"
                if in_sched:
                    # container_cite is the Schedule (or Schedule+Part) — keeps paragraph
                    # numbers unique when a schedule restarts numbering across its Parts.
                    cite = f"{container_cite or 'CDPA 1988 Sch. ' + str(sched_no)} para. {num}"
                    lid = add(parent_local=parent_local, kind="schedule_para", label=f"para. {num}",
                              heading=group_title, sort_int=si, sort_suffix=su, role="schedule",
                              citation=cite, content=content, status=status)
                else:
                    cite = f"CDPA 1988 s. {num}"
                    lid = add(parent_local=parent_local, kind="section", label=f"s. {num}",
                              heading=group_title, sort_int=si, sort_suffix=su, role="enacting",
                              citation=cite, content=content, status=status)
                walk(c, lid, container_cite, cite, [], None, in_sched, sched_no)
            elif name in PLEVEL:
                sib += 1
                num = (_txt(_child(c, "Pnumber")) or "").rstrip(". ") or None
                si, su = ordinal(num, sib)
                newsub = subpath + [num]
                cite = (sec_cite or "CDPA 1988 s.") + "".join(f"({x})" for x in newsub)
                lid = add(parent_local=parent_local, kind=PLEVEL[name], label=f"({num})",
                          heading=None, sort_int=si, sort_suffix=su,
                          role="schedule" if in_sched else "enacting", citation=cite, content=None)
                walk(c, lid, container_cite, sec_cite, newsub, None, in_sched, sched_no)
            else:
                walk(c, parent_local, container_cite, sec_cite, subpath, group_title, in_sched, sched_no)

    walk(root, None, None, None, [], None, False, None)
    return INSTRUMENT["title"], records, _parse_unapplied_effects(root)


# ── DB writers (idempotent) — same contract as ingest_uslm ──────────────────
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
    st = r.get("status") or "in_force"
    if row:
        conn.execute("UPDATE provisions SET parent_id=?, sort_int=?, sort_suffix=?, label=?, "
                     "heading=?, kind=?, role=?, status=? WHERE id=?",
                     (parent_id, r["sort_int"], r["sort_suffix"], r["label"], r["heading"],
                      r["kind"], r["role"], st, row[0]))
        return row[0]
    cur = conn.execute("INSERT INTO provisions (instrument_id, parent_id, sort_int, sort_suffix, "
                       "label, heading, kind, role, citation, status) VALUES (?,?,?,?,?,?,?,?,?,?)",
                       (iid, parent_id, r["sort_int"], r["sort_suffix"], r["label"], r["heading"],
                        r["kind"], r["role"], r["citation"], st))
    return cur.lastrowid


def _store_version(conn, iid, provid, r, source_url, point_in_time) -> str:
    # Idempotent BY CONTENT (matches _common): a re-fetch only versions a provision if its text
    # differs from the current version; on change, update the pit slot in place or insert new.
    content = r["content"]
    digest = sha256(content)
    cur = conn.execute("SELECT content_sha256 FROM versions WHERE instrument_id=? AND "
                       "provision_id=? AND is_current=1", (iid, provid)).fetchone()
    outcome = "unchanged"
    if not cur or cur[0] != digest:
        conn.execute("UPDATE versions SET is_current=0 WHERE instrument_id=? AND provision_id=?",
                     (iid, provid))
        slot = conn.execute("SELECT id FROM versions WHERE instrument_id=? AND provision_id=? "
                            "AND point_in_time IS ? AND language='en'",
                            (iid, provid, point_in_time)).fetchone()
        if slot:
            conn.execute("UPDATE versions SET content=?, content_sha256=?, source_url=?, "
                         "retrieved_at=?, is_current=1 WHERE id=?",
                         (content, digest, source_url, now_iso(), slot[0]))
            vid = slot[0]
            conn.execute("DELETE FROM versions_fts WHERE rowid=?", (vid,))
        else:
            c2 = conn.execute(
                "INSERT INTO versions (instrument_id, provision_id, version_label, point_in_time, "
                "language, content, content_sha256, source_url, retrieved_at, is_current) "
                "VALUES (?,?,?,?, 'en', ?,?,?,?, 1)",
                (iid, provid, "legislation.gov.uk", point_in_time, content, digest, source_url, now_iso()))
            vid = c2.lastrowid
        conn.execute("INSERT INTO versions_fts (rowid, title, citation, body) VALUES (?,?,?,?)",
                     (vid, "CDPA 1988", r["citation"], content))
        outcome = "new"
    conn.execute("DELETE FROM provisions_fts WHERE rowid=?", (provid,))
    conn.execute("INSERT INTO provisions_fts (rowid, citation, heading, body) VALUES (?,?,?,?)",
                 (provid, r["citation"], r["heading"] or "", content))
    return outcome


def ingest(db_path, xml_path, source_url, point_in_time=None, allow_corpus=False) -> dict:
    if os.path.basename(db_path) == "corpus.db" and not allow_corpus:
        raise SystemExit("refusing to write the live corpus.db (schema pending sign-off). "
                         "Pass --allow-corpus only after the migration is approved.")
    title, records, effects = parse(xml_path)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    _require_migration(conn)
    iid = _upsert_instrument(conn, title)
    localmap: dict[int, int] = {}
    stats = {"provisions": 0, "sections": 0, "schedule_paras": 0, "versions_new": 0, "versions_unchanged": 0}
    for r in records:
        parent_id = localmap.get(r["parent_local"]) if r["parent_local"] else None
        pid = _upsert_provision(conn, iid, parent_id, r)
        localmap[r["local_id"]] = pid
        stats["provisions"] += 1
        if r["kind"] == "section":
            stats["sections"] += 1
        elif r["kind"] == "schedule_para":
            stats["schedule_paras"] += 1
        if r["content"]:
            outcome = _store_version(conn, iid, pid, r, source_url, point_in_time)
            stats["versions_new" if outcome == "new" else "versions_unchanged"] += 1
    # Surface the snapshot's own "amendment not yet applied" metadata (prime rule 3).
    stats["unapplied_flagged"] = _apply_unapplied_effects(conn, iid, effects)
    conn.commit()
    conn.close()
    stats.update(instrument_id=iid, title=title)
    return stats


def main() -> None:
    ap = argparse.ArgumentParser(description="Ingest CDPA 1988 CLML into a provisions DB (draft).")
    ap.add_argument("--db", required=True)
    ap.add_argument("--xml", required=True)
    ap.add_argument("--source-url", required=True)
    ap.add_argument("--point-in-time", default=None)
    ap.add_argument("--allow-corpus", action="store_true")
    a = ap.parse_args()
    s = ingest(a.db, a.xml, a.source_url, a.point_in_time, a.allow_corpus)
    print(f"instrument #{s['instrument_id']}  {s['title']} (CDPA 1988)")
    print(f"  provisions upserted   : {s['provisions']}")
    print(f"  Body sections         : {s['sections']}")
    print(f"  Schedule paragraphs   : {s['schedule_paras']}  (role='schedule', separate class)")
    print(f"  versions              : new {s['versions_new']}, unchanged {s['versions_unchanged']}")
    print(f"  unapplied effects     : {s['unapplied_flagged']} current versions flagged "
          f"(has_unapplied_effects, from ukm:UnappliedEffects RequiresApplied=\"true\")")


if __name__ == "__main__":
    main()
