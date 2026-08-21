-- Jurisdiction scope (reference vocabulary, not law content). Tiered per the roadmap.
-- Tier 1: full text, versioned, monitored. Tier 2: text + amendment alerts. Tier 3: metadata/link.
INSERT OR IGNORE INTO jurisdictions (code, name, tier, notes) VALUES
  ('US','United States',1,'17 U.S.C. (Title 17) + 37 C.F.R. (Copyright Office regulations)'),
  ('GB','United Kingdom',1,'CDPA 1988 — legislation.gov.uk (point-in-time + change feed)'),
  ('EU','European Union',1,'InfoSoc/DSM/Software/Database/Term/Enforcement — EUR-Lex (consolidated NOT authentic)'),
  ('INT','International treaties',1,'Berne, TRIPS, WCT, WPPT, Rome, Beijing, Marrakesh — hand-loaded'),
  ('DE','Germany',2,NULL), ('FR','France',2,NULL), ('ES','Spain',2,NULL),
  ('IT','Italy',2,NULL), ('NL','Netherlands',2,NULL), ('CA','Canada',2,NULL),
  ('AU','Australia',2,NULL), ('JP','Japan',2,NULL), ('CN','China',2,'unofficial translations — flag'),
  ('KR','South Korea',2,NULL), ('IN','India',2,NULL), ('BR','Brazil',2,NULL),
  ('MX','Mexico',2,NULL), ('SG','Singapore',2,NULL);
