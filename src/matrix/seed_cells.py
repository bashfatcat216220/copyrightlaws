"""Comparative-matrix SEED — the first reviewable batch (Phase 4, vertical slice).

Each cell was DRAFTED by claude-opus-4-8 (prime rule 5) strictly from the cited provision's stored
current text in this corpus (prime rule 1 — summarize FETCHED text, never originate). `load_cells.py`
resolves (instrument_ext_id, source_citation) -> the provision's is_current version = `source_version`
and stores the cell with drafted_by='model:claude-opus-4-8', verified_by=NULL (a DRAFT). It is shown
as authority ONLY after a human runs `verify.py` (prime rule 4 — the schema trigger refuses to verify
a cell with no source_version).

THIS FILE IS THE ARTIFACT TO REVIEW. Bing signs off cell-by-cell via `verify.py --list` then
`verify.py --by "…"`. A cell with `source_citation=None` is a DOCUMENTED GAP (the governing text is
not in this corpus) — it loads with source_version=NULL and can never be verified until sourced.

Slice: 6 jurisdictions (US, GB, EU, CA, AU, DE) x 6 attributes = 36 cells.
"""
from __future__ import annotations

# ext_id per jurisdiction/instrument the cell draws from
US = "t17"                    # 17 U.S.C.
GB = "ukpga/1988/48"          # CDPA 1988
EU_TERM = "32006L0116"        # Term Directive 2006/116
EU_INFOSOC = "32001L0029"     # InfoSoc Directive 2001/29
EU_DSM = "32019L0790"         # DSM Directive 2019/790
CA = "ca-c-42"               # Copyright Act (Canada)
AU = "au-copyright-1968"      # Copyright Act 1968 (Cth)
DE = "de-urhg"               # UrhG

# (jurisdiction, attribute, instrument_ext_id, source_citation, value)
CELLS = [
    # ── term_individual ─────────────────────────────────────────────────────────────────────
    ("US", "term_individual", US, "17 U.S.C. § 302", "Life + 70 years (works created on/after Jan 1, 1978); § 302(a)."),
    ("GB", "term_individual", GB, "CDPA 1988 s. 12", "Life + 70 years — to the end of the 70th calendar year after the author's death."),
    ("EU", "term_individual", EU_TERM, "Directive 2006/116 Art. 1", "Life + 70 years, harmonised across the EU (Art 1(1))."),
    ("CA", "term_individual", CA, "Copyright Act (Canada) s. 6", "Life + 70 years (extended from +50 in 2022)."),
    ("AU", "term_individual", AU, "Copyright Act 1968 (Australia) s. 33", "Life + 70 years."),
    ("DE", "term_individual", DE, "UrhG § 64", "Life + 70 years (expires 70 years after the author's death)."),

    # ── term_corporate (works made for hire / corporate / anonymous) ────────────────────────
    ("US", "term_corporate", US, "17 U.S.C. § 302", "Works made for hire (and anonymous/pseudonymous): 95 years from publication or 120 from creation, whichever first (§ 302(c))."),
    ("GB", "term_corporate", GB, "CDPA 1988 s. 12", "No for-hire/corporate term — always measured by the author's life (+70); computer-generated works get 50 years from creation (s. 12(7))."),
    ("EU", "term_corporate", EU_TERM, "Directive 2006/116 Art. 1", "No corporate-authorship term; anonymous/pseudonymous & collective works run 70 years from lawful publication (Art 1(3)-(5))."),
    ("CA", "term_corporate", CA, "Copyright Act (Canada) s. 6", "No corporate/for-hire term — measured by the author's life (+70)."),
    ("AU", "term_corporate", AU, "Copyright Act 1968 (Australia) s. 33", "No corporate-authorship term; anonymous/pseudonymous works run 70 years from first publication."),
    ("DE", "term_corporate", DE, "UrhG § 66", "No work-made-for-hire — the natural creator is always the author; anonymous/pseudonymous works run 70 years from publication (§ 66)."),

    # ── fair_use_vs_closed_list ─────────────────────────────────────────────────────────────
    ("US", "fair_use_vs_closed_list", US, "17 U.S.C. § 107", "Open standard — four-factor fair use; enumerated purposes are illustrative, not exhaustive (§ 107)."),
    ("GB", "fair_use_vs_closed_list", GB, "CDPA 1988 s. 30", "Closed list — enumerated fair-dealing purposes (criticism/review, quotation, news; research/study in s. 29); no general fair use."),
    ("EU", "fair_use_vs_closed_list", EU_INFOSOC, "Directive 2001/29 Art. 5", "Closed, exhaustive list of exceptions Member States may adopt (Art 5); no open standard."),
    ("CA", "fair_use_vs_closed_list", CA, "Copyright Act (Canada) s. 29", "Closed list — fair dealing for enumerated purposes (research, private study, education, parody, satire); purpose-gated."),
    ("AU", "fair_use_vs_closed_list", AU, "Copyright Act 1968 (Australia) s. 40", "Closed list — enumerated fair-dealing purposes (research/study, criticism, news, parody/satire); no general fair use."),
    ("DE", "fair_use_vs_closed_list", DE, "UrhG § 51", "Closed statutory catalogue of permitted uses (§§ 44a-63; quotation § 51); no open standard."),

    # ── tdm_commercial (text-and-data-mining incl. commercial AI training) ──────────────────
    ("US", "tdm_commercial", US, "17 U.S.C. § 107", "No express TDM exception; commercial text-and-data-mining / AI training assessed case-by-case under § 107 fair use."),
    ("GB", "tdm_commercial", GB, "CDPA 1988 s. 29A", "TDM permitted for non-commercial research only (s. 29A); no commercial / AI-training exception."),
    ("EU", "tdm_commercial", EU_DSM, "Directive 2019/790 Art. 4", "Commercial TDM/AI-training permitted subject to a machine-readable opt-out by rightholders (Art 4); the research-body exception (Art 3) cannot be overridden."),
    ("CA", "tdm_commercial", CA, "Copyright Act (Canada) s. 29", "No express TDM exception; would fall to fair dealing (s. 29); commercial AI-training use untested."),
    ("AU", "tdm_commercial", AU, "Copyright Act 1968 (Australia) s. 40", "No express TDM exception; only fair dealing for research/study (s. 40); no commercial TDM/AI provision."),
    ("DE", "tdm_commercial", DE, "UrhG § 44b", "General TDM exception including commercial use, subject to a machine-readable opt-out (§ 44b); non-commercial scientific research separately covered (§ 60d)."),

    # ── moral_rights_waivable ───────────────────────────────────────────────────────────────
    ("US", "moral_rights_waivable", US, "17 U.S.C. § 106A", "Waivable — visual-art moral rights may be waived by a signed written instrument; not transferable (§ 106A(e))."),
    ("GB", "moral_rights_waivable", GB, "CDPA 1988 s. 87", "Waivable — by written instrument, and defeated by consent (s. 87)."),
    ("EU", "moral_rights_waivable", EU_TERM, "Directive 2006/116 Art. 9", "Not harmonised at EU level — left to Member State law (Art 9, 'without prejudice to … moral rights')."),
    ("CA", "moral_rights_waivable", CA, "Copyright Act (Canada) s. 14.1", "Waivable — may be waived in whole or part (but not assigned) (s. 14.1(2))."),
    ("AU", "moral_rights_waivable", AU, "Copyright Act 1968 (Australia) s. 195AW", "Not waivable — but the author may give written consent to specified acts/omissions (s. 195AW/195AWA)."),
    ("DE", "moral_rights_waivable", DE, "UrhG § 29", "Not waivable — the author's right is inalienable and non-transferable except by inheritance (§ 29); moral rights cannot be surrendered."),

    # ── safe_harbor_regime (intermediary liability / notice mechanism) ──────────────────────
    ("US", "safe_harbor_regime", US, "17 U.S.C. § 512", "DMCA notice-and-takedown safe harbours (conduit/caching/hosting/search), conditioned on takedown + a repeat-infringer policy (§ 512)."),
    ("GB", "safe_harbor_regime", GB, "CDPA 1988 s. 97A", "No safe harbour in the CDPA; hosting immunity sits in the retained E-Commerce rules (not in corpus). s. 97A allows injunctions against service providers with actual knowledge."),
    ("EU", "safe_harbor_regime", EU_DSM, "Directive 2019/790 Art. 17", "Content-sharing platforms (OCSSPs) are directly liable for user uploads absent best-efforts licensing/takedown/stay-down (Art 17); the baseline hosting safe harbour is in E-Commerce Dir 2000/31 (not in corpus)."),
    ("CA", "safe_harbor_regime", CA, "Copyright Act (Canada) s. 41.25", "Notice-and-notice (not takedown) — an intermediary must forward a rightholder's infringement notice to the user; no takedown duty (s. 41.25-41.26)."),
    ("AU", "safe_harbor_regime", AU, "Copyright Act 1968 (Australia) s. 116AG", "Safe-harbour scheme limiting remedies against service providers that meet the statutory conditions (s. 116AG, Div 2AA)."),
    ("DE", "safe_harbor_regime", None, None, "Platform liability sits in the Copyright Service Provider Act (UrhDaG 2021, transposing DSM Art 17) — a separate statute not in this corpus; general hosting immunity historically under the Telemedia Act. [documented gap — not sourced here]"),
]
