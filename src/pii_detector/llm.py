"""LLM helper for optional classification."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Dict, List

import requests

from .fragment import fragment_text

MODEL_VERSION = "gpt-4o-mini"
PROMPT_VERSION = "v1"


@dataclass
class LlmResult:
    contains_pii: bool
    pii_types: List[str]
    evidence: List[Dict[str, object]]
    confidence: float
    raw: Dict[str, object]


def _score_fragment(fragment: str) -> int:
    keywords = ["nome", "cpf", "rg", "telefone", "email", "rua", "avenida", "whats", "contato"]
    lower = fragment.lower()
    return sum(1 for keyword in keywords if keyword in lower)


def select_suspect_fragments(text: str, max_fragments: int = 3) -> List[Dict[str, object]]:
    fragments = fragment_text(text)
    scored = [(idx, frag, _score_fragment(frag)) for idx, frag in enumerate(fragments)]
    scored.sort(key=lambda item: item[2], reverse=True)
    selected = scored[:max_fragments]
    return [
        {"fragment_idx": idx, "text": frag}
        for idx, frag, _score in selected
        if frag
    ]


def call_openai(text: str, timeout_s: int = 20, max_retries: int = 2) -> LlmResult:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY environment variable is not set")

    fragments = select_suspect_fragments(text)
    prompt = {
        "role": "user",
        "content": (
            "Você é um classificador de dados pessoais. Analise os fragmentos e responda apenas com JSON estrito. "
            "Retorne contains_pii=true somente se houver evidência explícita. "
            "JSON esperado: {\n"
            "  \"contains_pii\": boolean,\n"
            "  \"pii_types\": [\"name\",\"email\",\"cpf\",\"rg\",\"phone\"],\n"
            "  \"evidence\": [{\"type\": string, \"span\": string, \"fragment_idx\": number}],\n"
            "  \"confidence\": number\n"
            "}\n\n"
            f"Fragmentos: {json.dumps(fragments, ensure_ascii=False)}"
        ),
    }

    payload = {
        "model": MODEL_VERSION,
        "messages": [prompt],
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }

    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    last_error = None
    for _ in range(max_retries + 1):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=timeout_s)
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            return LlmResult(
                contains_pii=bool(parsed.get("contains_pii")),
                pii_types=list(parsed.get("pii_types", [])),
                evidence=list(parsed.get("evidence", [])),
                confidence=float(parsed.get("confidence", 0.0)),
                raw=parsed,
            )
        except (requests.RequestException, json.JSONDecodeError, KeyError, ValueError) as exc:
            last_error = exc
    raise RuntimeError(f"Failed to call OpenAI API: {last_error}")
