-- ============================================================================
-- Migration 001 — provisions rebuild  (DRAFT — FOR REVIEW, NOT APPLIED)
-- ============================================================================
-- Purpose: give instruments a section-level spine so text can be diffed and
-- cited at the provision level (a US section, a UK section/schedule paragraph,
-- an EU article, a treaty article — all "provisions"). Derived from the parsing
-- spike (spike/parse_spike.py + spike/out/SPIKE-REPORT.md) run against real
-- USLM (17 U.S.C.), CLML (CDPA 1988) and Formex (InfoSoc) source text.
--
-- GATE: this is a data-model change. Do NOT run it against db/corpus.db until
-- Bing signs off on the delta (prime rule: risky seeds gate on human review).
-- Forward-only (adds a column); run once on a fresh/again-migratable DB.
-- Apply later with:  sqlite3 db/corpus.db < db/migrations/001_provisions_rebuild.sql
--
-- OPEN for sign-off:
--   * `role` enum (below) vs a bare `operative` boolean — recommended: the enum.
--   * whether CDPA consequential-amendment/repeal schedules (Sch 7/8) are
--     role='schedule' (operative here) or role='quoted' (they amend other Acts).
--   * recitals: modelled as provisions kind='recital' role='recital' (structural
--     source = original OJ; current text = consolidated, is_authentic=0).
-- ============================================================================

PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------------------
-- PROVISIONS — the section-level tree under an instrument
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS provisions (
  id            INTEGER PRIMARY KEY,
  instrument_id INTEGER NOT NULL REFERENCES instruments(id),
  parent_id     INTEGER REFERENCES provisions(id),   -- chapter→section→subsection tree; NULL at top

  -- Ordinal is TWO columns, not an integer: real statutes insert letter-suffixed
  -- sections (US §106A between 106 and 107; UK §31BA, §296ZA). Sort within a
  -- parent is ORDER BY (sort_int, sort_suffix COLLATE BINARY). The collation is
  -- PINNED on purpose — 296Z < 296ZA < 296ZEA sorts right only under binary
  -- comparison; a locale-aware collation added later would silently break it.
  sort_int      INTEGER NOT NULL,
  sort_suffix   TEXT NOT NULL DEFAULT '' COLLATE BINARY,

  label         TEXT NOT NULL,        -- source-given display: '§ 203', 's. 296ZA', 'Article 5'
  heading       TEXT,                 -- section/article title, from source (NULL if none)

  -- Structural tag, source-derived (USLM element / CLML P-level / Formex element).
  kind          TEXT NOT NULL CHECK (kind IN
                  ('title','part','subpart','chapter','subchapter','section','subsection',
                   'paragraph','subparagraph','clause','subclause','item','subitem',
                   'article','schedule','schedule_para','recital')),

  -- Retrieval semantics (replaces a bare operative boolean — a boolean collapses
  -- recital and quoted-amendment text, which must behave differently):
  --   'enacting' → operative law (counted, diffed)
  --   'schedule' → operative law inside a schedule (counted, diffed; separate numbering)
  --   'recital'  → interpretive; addressable + searchable, NEVER counted/diffed
  --   'quoted'   → other instruments' words reproduced inline; never surfaced as this text
  role          TEXT NOT NULL DEFAULT 'enacting'
                  CHECK (role IN ('enacting','schedule','recital','quoted')),

  citation      TEXT NOT NULL,        -- stable pinpoint & natural re-ingest key
                                       -- e.g. '17 U.S.C. § 203(a)(4)', 'CDPA 1988 s. 296ZA'
  status        TEXT NOT NULL DEFAULT 'in_force'
                  CHECK (status IN ('in_force','repealed','prospective','unknown')),

  UNIQUE (instrument_id, citation)     -- re-ingest re-attaches, never duplicates
);

CREATE INDEX IF NOT EXISTS idx_provisions_instrument ON provisions(instrument_id, sort_int, sort_suffix);
CREATE INDEX IF NOT EXISTS idx_provisions_parent     ON provisions(parent_id);
CREATE INDEX IF NOT EXISTS idx_provisions_role       ON provisions(instrument_id, role);

-- ---------------------------------------------------------------------------
-- VERSIONS — text now hangs off a PROVISION (was: whole instrument)
-- ---------------------------------------------------------------------------
-- Caught while drafting the ingest: adding a column is not enough. The old
-- UNIQUE (instrument_id, point_in_time, language) assumed ONE version per
-- instrument per point-in-time — but per-provision versioning puts many
-- provisions of the same instrument at the same point-in-time, which collides.
-- The key must include provision_id. SQLite can't ALTER a constraint, so rebuild
-- the table (safe: versions is empty today). Forward-only; run once.
DROP TRIGGER IF EXISTS version_requires_sha;
DROP INDEX   IF EXISTS idx_versions_instrument;

CREATE TABLE versions_new (
  id                    INTEGER PRIMARY KEY,
  instrument_id         INTEGER NOT NULL REFERENCES instruments(id),
  provision_id          INTEGER REFERENCES provisions(id),   -- NULL = whole-instrument version
  version_label         TEXT,
  point_in_time         TEXT,
  language              TEXT NOT NULL DEFAULT 'en',
  is_official_language  INTEGER NOT NULL DEFAULT 1,
  is_consolidated       INTEGER NOT NULL DEFAULT 1,
  is_authentic          INTEGER NOT NULL DEFAULT 1,
  has_unapplied_effects INTEGER NOT NULL DEFAULT 0,
  content               TEXT,
  content_sha256        TEXT,
  source_url            TEXT NOT NULL,
  retrieved_at          TEXT NOT NULL,
  is_current            INTEGER NOT NULL DEFAULT 1,
  UNIQUE (instrument_id, provision_id, point_in_time, language)
);
INSERT INTO versions_new
  (id, instrument_id, version_label, point_in_time, language, is_official_language,
   is_consolidated, is_authentic, has_unapplied_effects, content, content_sha256,
   source_url, retrieved_at, is_current)
  SELECT id, instrument_id, version_label, point_in_time, language, is_official_language,
         is_consolidated, is_authentic, has_unapplied_effects, content, content_sha256,
         source_url, retrieved_at, is_current
  FROM versions;                       -- 0 rows today; copy is a no-op but keeps it safe
DROP TABLE versions;
ALTER TABLE versions_new RENAME TO versions;

-- recreate the invariant trigger + indexes on the rebuilt table
CREATE TRIGGER version_requires_sha
BEFORE INSERT ON versions
WHEN NEW.content IS NOT NULL AND (NEW.content_sha256 IS NULL OR NEW.content_sha256 = '')
BEGIN
  SELECT RAISE(ABORT, 'version with content must carry content_sha256');
END;
CREATE INDEX idx_versions_instrument ON versions(instrument_id, is_current);
CREATE INDEX idx_versions_provision  ON versions(provision_id, is_current);

-- ---------------------------------------------------------------------------
-- CASE_TREATMENT — powers the reader's Cases tab (today an honest empty-state)
-- ---------------------------------------------------------------------------
-- Attaches to a PROVISION, not the whole instrument: a decision treats § 203,
-- not "Title 17". Every row carries its own provenance (finding-aid rule).
CREATE TABLE IF NOT EXISTS case_treatment (
  id              INTEGER PRIMARY KEY,
  provision_id    INTEGER NOT NULL REFERENCES provisions(id),
  case_instrument INTEGER REFERENCES instruments(id),   -- the deciding case (instruments.type='case')
  treatment       TEXT CHECK (treatment IN
                    ('followed','cited','applied','distinguished','criticized','overruled')),
  holding         TEXT,                                  -- grounded to fetched source; NULL if not fetched
  source_url      TEXT NOT NULL,
  retrieved_at    TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_case_treatment_provision ON case_treatment(provision_id);

-- ---------------------------------------------------------------------------
-- PROVISION-LEVEL FULL-TEXT SEARCH (contentless FTS5; synced by the store layer)
-- ---------------------------------------------------------------------------
-- rowid = provisions.id. `body` is the current version's text for that provision.
-- Store layer excludes role='quoted' from `body` (never surfaced); role='recital'
-- IS indexed (interpretive text is searchable).
CREATE VIRTUAL TABLE IF NOT EXISTS provisions_fts USING fts5(
  citation, heading, body,
  tokenize = 'porter unicode61'
);

-- ---------------------------------------------------------------------------
-- STRUCTURAL INVARIANTS (no-fake-data enforced by the DB)
-- ---------------------------------------------------------------------------
-- A provision-scoped version must point at a provision of the SAME instrument
-- (a § 203 version can't be filed under a different Act).
CREATE TRIGGER IF NOT EXISTS version_provision_same_instrument
BEFORE INSERT ON versions
WHEN NEW.provision_id IS NOT NULL
 AND (SELECT instrument_id FROM provisions WHERE id = NEW.provision_id) <> NEW.instrument_id
BEGIN
  SELECT RAISE(ABORT, 'version.provision_id must belong to the same instrument');
END;

-- Case treatment is authority only with a source — no ungrounded holdings.
CREATE TRIGGER IF NOT EXISTS case_treatment_needs_source
BEFORE INSERT ON case_treatment
WHEN NEW.source_url IS NULL OR NEW.source_url = ''
BEGIN
  SELECT RAISE(ABORT, 'case_treatment must carry a source_url (finding aid, never a citation)');
END;
