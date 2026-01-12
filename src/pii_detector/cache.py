"""JSON cache for LLM results."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass
class CacheEntry:
    key: str
    payload: Dict[str, Any]


class JsonCache:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._data: Dict[str, Dict[str, Any]] = {}
        if self.path.exists():
            try:
                self._data = json.loads(self.path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                self._data = {}

    @staticmethod
    def normalize_text(text: str) -> str:
        return " ".join(text.lower().strip().split())

    @classmethod
    def make_key(cls, text: str) -> str:
        normalized = cls.normalize_text(text)
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def get(self, text: str) -> Optional[CacheEntry]:
        key = self.make_key(text)
        payload = self._data.get(key)
        if payload is None:
            return None
        return CacheEntry(key=key, payload=payload)

    def set(self, text: str, payload: Dict[str, Any]) -> CacheEntry:
        key = self.make_key(text)
        stored = {
            **payload,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._data[key] = stored
        return CacheEntry(key=key, payload=stored)

    def save(self) -> None:
        self.path.write_text(json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8")
