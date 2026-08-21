-- Migration 002 — legal-authority axis (2026-08-14)
-- Authority is NOT a function of publisher or `type`. The U.S. Copyright Office produces both
-- binding legislative rules (37 C.F.R., notice-and-comment under delegated authority) and
-- non-binding guidance (the Compendium, circulars) — same author, different legal status by
-- PROCESS. And "official source" has gradations: eCFR/OLRC-online are government FINDING AIDS,
-- not the official legal edition (GPO annual CFR + Federal Register control; the printed U.S.
-- Code). Title 17 is enacted into POSITIVE LAW, so its Code text is legal evidence of the law
-- itself (not merely prima facie). Caselaw is a distinct category whose weight (binding vs
-- persuasive) is CONTEXTUAL to the reader's court. These are per-instrument facts → new columns.
--
-- SQLite ALTER can't add CHECK constraints; allowed values are enforced in the store layer.
--   authority      : 'binding' (force of law) | 'persuasive' (no force of law) | 'precedent' (caselaw)
--   positive_law   : 1 = enacted into positive law (Code text = legal evidence) | 0 = prima facie only | NULL = n/a
--   source_edition : 'official' | 'finding_aid' | 'consolidated' | 'translation' | 'original_act'
--   court_level    : caselaw only — 'scotus' | 'circuit' | 'district' | 'other' | NULL (compute binding reach; 'other' = state/CFC/bankruptcy, renamed from 'foreign' 2026-08-21)

ALTER TABLE instruments ADD COLUMN authority      TEXT;
ALTER TABLE instruments ADD COLUMN positive_law   INTEGER;
ALTER TABLE instruments ADD COLUMN source_edition TEXT;
ALTER TABLE instruments ADD COLUMN court_level    TEXT;
