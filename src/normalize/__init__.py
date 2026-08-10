"""Source-native format -> canonical FetchedVersion text.

Each source speaks a different dialect (UK CLML/XML, US USLM XML, EUR-Lex XHTML, treaty
PDFs). Normalizers here strip source chrome and produce clean canonical text WITHOUT
rewording — the sha256 must be stable across runs, so normalization is deterministic
(no model, no reflow that varies). Phase 0 adds one normalizer per Phase-0 source.
"""
from __future__ import annotations

import re

_WS = re.compile(r"[ \t]+")
_BLANKS = re.compile(r"\n{3,}")


def clean_text(s: str) -> str:
    """Deterministic whitespace normalization (stable sha256). No wording changes."""
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = "\n".join(_WS.sub(" ", line).rstrip() for line in s.split("\n"))
    return _BLANKS.sub("\n\n", s).strip()
