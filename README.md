# Copyright Corpus

A private, source-grounded reference and change-monitor for copyright law across
jurisdictions. It fetches official statute, regulation, directive, and treaty text, stores
each as a point-in-time version with its source URL and retrieval date, detects when a law
changes, and (later) presents a comparative attribute matrix across jurisdictions.

It is a **finding aid, not a citation**. Every screen shows the official source URL and when
the text was retrieved; consolidated, translated, and non-authentic texts are flagged.

## Scope
- Tier 1 (full text, versioned, monitored): US (17 U.S.C., 37 C.F.R.), UK (CDPA 1988),
  EU (InfoSoc, DSM, and the other copyright directives), and the core treaties
  (Berne, TRIPS, WCT, WPPT, Rome, Beijing, Marrakesh).
- Tier 2 (text + amendment alerts): DE, FR, ES, IT, NL, CA, AU, JP, CN, KR, IN, BR, MX, SG.
- Tier 3 (metadata + link only): the remaining jurisdictions, from WIPO Lex, link-out only.

## Sources
legislation.gov.uk (UK, keyless), GovInfo + eCFR + Federal Register (US), EUR-Lex CELLAR
(EU, keyless), LegiScan and Congress.gov for the bill pipeline, and hand-loaded treaty texts.
See `CLAUDE.md` for the source-of-truth table and the connector contract.

## Layout
- `db/schema.sql` — instruments / versions / amendments / bills / alerts / matrix + FTS.
- `src/connectors/` — one module per source (uniform `discover` / `fetch` interface).
- `src/store/` — canonicalizes fetched text into versions (sha256, FTS sync).
- `src/monitor/` — change detection and redlines.
- `src/matrix/` — the comparative attribute matrix (human-verified).
- `src/app.py` + `templates/` — the website.

## Run
    python src/db.py            # initialize db/corpus.db
    uvicorn src.app:app         # http://localhost:8000
    pytest -q                   # schema + store invariants

Status: scaffold. Connectors are stubs pending Phase 0 (see `CLAUDE.md` → roadmap).
