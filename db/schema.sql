-- Copyright Corpus — canonical schema (v0.1)
--
-- RETRIEVAL-FIRST. Connectors fetch OFFICIAL source text + provenance; the model only
-- classifies / summarizes / redlines text already fetched. It NEVER originates a law,
-- a citation, a date, or a version. If it is not in a fetched source, the field is NULL.
--
-- The load-bearing table is `versions`: the consolidated text of an instrument AS IN
-- FORCE at a point in time. Every version carries source_url + retrieved_at (shown on
-- EVERY screen — the tool is a finding aid, never a citation) and, when it has text, a
-- content_sha256 (the change-monitor key). These are structural, not conventions.

PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------------------
-- JURISDICTIONS (US, GB, EU, DE, ... ; treaty bodies use 'INT')
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS jurisdictions (
  code   TEXT PRIMARY KEY,                 -- 'US', 'GB', 'EU', 'DE', 'JP', 'INT'
  name   TEXT NOT NULL,
  tier   INTEGER NOT NULL CHECK (tier IN (1, 2, 3)),
  notes  TEXT
);

-- ---------------------------------------------------------------------------
-- INSTRUMENTS — a law/reg/treaty/directive/bill as an IDENTITY (not a text)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS instruments (
  id                INTEGER PRIMARY KEY,
  jurisdiction      TEXT NOT NULL REFERENCES jurisdictions(code),
  type              TEXT NOT NULL CHECK (type IN
                      ('statute','regulation','treaty','directive','bill','guidance','case')),
  title             TEXT NOT NULL,
  official_citation TEXT,                  -- '17 U.S.C.', 'CDPA 1988', 'Directive (EU) 2019/790'
  ext_id            TEXT,                  -- ELI / CELEX / WIPO-Lex id / USC title / CFR part
  ext_id_scheme     TEXT,                  -- 'ELI' | 'CELEX' | 'WIPO' | 'USC' | 'CFR' | 'TREATY'
  status            TEXT NOT NULL DEFAULT 'in_force'
                      CHECK (status IN ('in_force','proposed','repealed','superseded','unknown')),
  enacted_date      TEXT,                  -- ISO8601
  in_force_date     TEXT,
  repealed_date     TEXT,
  first_seen_at     TEXT NOT NULL,
  last_updated_at   TEXT NOT NULL,
  UNIQUE (jurisdiction, ext_id_scheme, ext_id)
);

-- ---------------------------------------------------------------------------
-- VERSIONS — consolidated text AS IN FORCE at a point in time (the core table)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS versions (
  id                    INTEGER PRIMARY KEY,
  instrument_id         INTEGER NOT NULL REFERENCES instruments(id),
  version_label         TEXT,              -- source's own label (e.g. UK point-in-time date)
  point_in_time         TEXT,              -- ISO8601 date this text is in force FROM
  language              TEXT NOT NULL DEFAULT 'en',
  is_official_language  INTEGER NOT NULL DEFAULT 1,  -- 0 = unofficial translation (FLAG in UI)
  is_consolidated       INTEGER NOT NULL DEFAULT 1,
  is_authentic          INTEGER NOT NULL DEFAULT 1,  -- EU consolidated = 0 (NOT authentic — FLAG)
  has_unapplied_effects INTEGER NOT NULL DEFAULT 0,  -- UK consolidated can carry these (FLAG)
  content               TEXT,              -- canonical full text (NULL for metadata-only Tier 3)
  content_sha256        TEXT,              -- REQUIRED when content present (change key)
  source_url            TEXT NOT NULL,     -- official source page (shown on EVERY screen)
  retrieved_at          TEXT NOT NULL,     -- when WE fetched it (shown on EVERY screen)
  is_current            INTEGER NOT NULL DEFAULT 1,   -- latest point-in-time we hold
  UNIQUE (instrument_id, point_in_time, language)
);

-- ---------------------------------------------------------------------------
-- AMENDMENTS — amending instrument -> amended instrument
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS amendments (
  id                  INTEGER PRIMARY KEY,
  amending_instrument INTEGER REFERENCES instruments(id),
  amended_instrument  INTEGER NOT NULL REFERENCES instruments(id),
  sections_affected   TEXT,
  effect              TEXT,               -- 'inserted' | 'substituted' | 'repealed' | 'in force'
  effective_date      TEXT,
  source_url          TEXT NOT NULL,
  retrieved_at        TEXT NOT NULL
);

-- ---------------------------------------------------------------------------
-- BILLS — pipeline items (in-progress law), linked to the instrument they touch
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bills (
  id                INTEGER PRIMARY KEY,
  jurisdiction      TEXT NOT NULL REFERENCES jurisdictions(code),
  chamber           TEXT,
  number            TEXT,
  session           TEXT,
  title             TEXT NOT NULL,
  sponsor           TEXT,
  status            TEXT,
  last_action       TEXT,
  last_action_date  TEXT,
  linked_instrument INTEGER REFERENCES instruments(id),
  source_url        TEXT NOT NULL,
  retrieved_at      TEXT NOT NULL,
  first_seen_at     TEXT NOT NULL,
  UNIQUE (jurisdiction, chamber, number, session)
);

-- ---------------------------------------------------------------------------
-- ALERTS — a fired change-monitor rule (a version diff was detected)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS alerts (
  id            INTEGER PRIMARY KEY,
  rule          TEXT NOT NULL,
  instrument_id INTEGER REFERENCES instruments(id),
  old_version   INTEGER REFERENCES versions(id),
  new_version   INTEGER REFERENCES versions(id),
  summary       TEXT,                     -- AI/human redline summary (grounded + labeled)
  notified_at   TEXT
);

-- ---------------------------------------------------------------------------
-- COMPARATIVE MATRIX (the product) — one row per (jurisdiction, attribute).
-- The model DRAFTS value from a cited source version; it is shown as authority ONLY
-- when verified_by is set (human sign-off). NULL verified_by = DRAFT, labeled as such.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS matrix_cells (
  id              INTEGER PRIMARY KEY,
  jurisdiction    TEXT NOT NULL REFERENCES jurisdictions(code),
  attribute       TEXT NOT NULL,          -- 'term_individual','tdm_commercial','moral_waivable',...
  value           TEXT,
  source_version  INTEGER REFERENCES versions(id),   -- the provision it was drawn from
  source_citation TEXT,                   -- pinpoint (section / article)
  drafted_by      TEXT,                   -- 'model:claude-opus-4-8' | 'human'
  verified_by     TEXT,                   -- NULL = DRAFT (not shown as authority)
  verified_at     TEXT,
  UNIQUE (jurisdiction, attribute)
);

-- ---------------------------------------------------------------------------
-- FULL-TEXT SEARCH over version text (contentless FTS5; synced by the store layer)
-- ---------------------------------------------------------------------------
CREATE VIRTUAL TABLE IF NOT EXISTS versions_fts USING fts5(
  title, citation, body,
  tokenize = 'porter unicode61'
);

-- ---------------------------------------------------------------------------
-- STRUCTURAL INVARIANTS (no-fake-data enforced by the DB, not by convention)
-- ---------------------------------------------------------------------------
-- A version that carries text MUST carry its sha256 (the change key can't be faked-blank).
CREATE TRIGGER IF NOT EXISTS version_requires_sha
BEFORE INSERT ON versions
WHEN NEW.content IS NOT NULL AND (NEW.content_sha256 IS NULL OR NEW.content_sha256 = '')
BEGIN
  SELECT RAISE(ABORT, 'version with content must carry content_sha256');
END;

-- A matrix cell shown as authority (verified) MUST cite a real source version.
CREATE TRIGGER IF NOT EXISTS matrix_verified_needs_source
BEFORE UPDATE OF verified_by ON matrix_cells
WHEN NEW.verified_by IS NOT NULL AND NEW.source_version IS NULL
BEGIN
  SELECT RAISE(ABORT, 'a verified matrix cell must cite a source version');
END;

CREATE INDEX IF NOT EXISTS idx_versions_instrument ON versions(instrument_id, is_current);
CREATE INDEX IF NOT EXISTS idx_instruments_jur     ON instruments(jurisdiction, type, status);
CREATE INDEX IF NOT EXISTS idx_bills_jur           ON bills(jurisdiction, last_action_date);
