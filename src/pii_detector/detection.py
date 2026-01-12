"""PII detection logic."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional

from .fragment import fragment_text

CPF_RE = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_BASE_RE = re.compile(
    r"(?:\+?55\s*)?(?:\(?\d{2}\)?\s*)?(?:9?\d{4})[-\s]?\d{4}"
)
CEP_RE = re.compile(r"\b\d{5}-\d{3}\b")
ADDRESS_STRONG_RE = re.compile(
    r"\b(rua|avenida|av\.|rodovia|travessa|quadra|lote|bloco|apto|apartamento|conjunto|condominio|condomínio)\b\s*[,\-]?\s*\d+",
    re.IGNORECASE,
)
RG_MARKER_RE = re.compile(r"\b(rg|identidade)\b", re.IGNORECASE)
RG_VALUE_RE = re.compile(r"\b\d{5,12}[\w-]?\b")
PHONE_MARKER_RE = re.compile(r"\b(tel|telefone|whats|whatsapp)\b", re.IGNORECASE)
PROCESS_MARKER_RE = re.compile(r"\b(processo|sei)\b", re.IGNORECASE)

NAME_HINTS = ["me chamo", "meu nome é", "nome:", "ass:", "atenciosamente"]
ADDRESS_HINTS = [
    "rua",
    "avenida",
    "av.",
    "travessa",
    "quadra",
    "lote",
    "bloco",
    "apto",
    "apartamento",
    "conjunto",
    "condominio",
    "condomínio",
]


@dataclass
class DetectionResult:
    flags: Dict[str, int]
    evidence: List[Dict[str, object]]
    used_llm: bool = False


def _cpf_valid(value: str) -> bool:
    digits = re.sub(r"\D", "", value)
    if len(digits) != 11:
        return False
    if digits == digits[0] * 11:
        return False
    nums = [int(d) for d in digits]
    for i in range(9, 11):
        total = sum(nums[num] * ((i + 1) - num) for num in range(i))
        check = ((total * 10) % 11) % 10
        if nums[i] != check:
            return False
    return True


def _match_with_evidence(pattern: re.Pattern[str], fragment: str) -> Optional[str]:
    match = pattern.search(fragment)
    return match.group(0) if match else None


def detect_cpf(fragment: str) -> Optional[str]:
    match = _match_with_evidence(CPF_RE, fragment)
    if match and _cpf_valid(match):
        return match
    return None


def detect_email(fragment: str) -> Optional[str]:
    return _match_with_evidence(EMAIL_RE, fragment)


def detect_phone(fragment: str) -> Optional[str]:
    if PROCESS_MARKER_RE.search(fragment) and not PHONE_MARKER_RE.search(fragment):
        return None
    match = _match_with_evidence(PHONE_BASE_RE, fragment)
    if not match:
        return None
    if not PHONE_MARKER_RE.search(fragment):
        if not re.search(r"\+55", match) and not re.search(r"\(\d{2}\)", match) and not re.search(r"^\s*\d{2}\b", match):
            return None
    return match


def detect_address_strong(fragment: str) -> Optional[str]:
    match = _match_with_evidence(CEP_RE, fragment)
    if match:
        return match
    return _match_with_evidence(ADDRESS_STRONG_RE, fragment)


def detect_rg(fragment: str) -> Optional[str]:
    if not RG_MARKER_RE.search(fragment):
        return None
    return _match_with_evidence(RG_VALUE_RE, fragment)


def detect_name(fragment: str) -> Optional[str]:
    lower = fragment.lower()
    for hint in NAME_HINTS:
        if hint in lower:
            return hint
    return None


def detect_address_weak(fragment: str) -> Optional[str]:
    lower = fragment.lower()
    for hint in ADDRESS_HINTS:
        if hint in lower:
            return hint
    return None


def analyze_text(text: str) -> DetectionResult:
    fragments = fragment_text(text)
    flags = {"cpf": 0, "email": 0, "telefone": 0, "endereco": 0, "rg": 0, "nome": 0}
    evidence: List[Dict[str, object]] = []

    detectors = [
        ("cpf", detect_cpf),
        ("email", detect_email),
        ("telefone", detect_phone),
        ("endereco", detect_address_strong),
        ("rg", detect_rg),
    ]

    for idx, fragment in enumerate(fragments):
        for label, detector in detectors:
            match = detector(fragment)
            if match:
                flags[label] = 1
                evidence.append({"type": label, "span": match, "fragment_idx": idx})
                flags["nao_publico"] = 1
                return DetectionResult(flags=flags, evidence=evidence)

    flags["nao_publico"] = 0
    for idx, fragment in enumerate(fragments):
        name_match = detect_name(fragment)
        if name_match:
            flags["nome"] = 1
            evidence.append({"type": "nome", "span": name_match, "fragment_idx": idx})
        address_match = detect_address_weak(fragment)
        if address_match:
            flags["endereco"] = 1
            evidence.append({"type": "endereco", "span": address_match, "fragment_idx": idx})

    if any(flags[key] for key in ["nome", "endereco"]):
        flags["nao_publico"] = 1

    return DetectionResult(flags=flags, evidence=evidence)
