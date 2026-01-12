"""Text fragmentation utilities."""
from __future__ import annotations

import re
from typing import List

WORD_RE = re.compile(r"[\wÀ-ÿ]+", re.UNICODE)


def tokenize_words(text: str) -> List[str]:
    if not text:
        return []
    return WORD_RE.findall(text)


def fragment_text(text: str, window: int = 35, overlap: int = 12) -> List[str]:
    words = tokenize_words(text)
    if not words:
        return [""]
    if window <= overlap:
        raise ValueError("window must be greater than overlap")
    fragments: List[str] = []
    start = 0
    while start < len(words):
        end = min(start + window, len(words))
        fragments.append(" ".join(words[start:end]))
        if end == len(words):
            break
        start = max(0, end - overlap)
    return fragments
