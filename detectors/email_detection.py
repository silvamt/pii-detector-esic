"""
Detecta enderecos de e-mail em `entrada/AMOSTRA.xlsx` e salva o resultado em `saida/`.

Uso:
    python email_detection.py
"""

from __future__ import annotations

import re
from pathlib import Path
import sys

import pandas as pd

from utils_io import carregar_amostra

BASE_DIR = Path(__file__).resolve().parent.parent
ENTRADA_DIR = BASE_DIR / "entrada"
SAIDA_DIR = BASE_DIR / "saida"
AMOSTRA_PATH = ENTRADA_DIR / "AMOSTRA.xlsx"
SAIDA_PATH = SAIDA_DIR / "AMOSTRA_com_email.xlsx"

# Regex simples para padroes usuais de e-mail.
EMAIL_REGEX = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
EMAIL_OBFUSCATED_REGEX = re.compile(
    r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", re.IGNORECASE
)

AT_PATTERN = re.compile(r"\s*(?:\[|\()?\s*(?:at|arroba)\s*(?:\]|\))?\s*", re.I)
DOT_PATTERN = re.compile(r"\s*(?:\[|\()?\s*(?:dot|ponto)\s*(?:\]|\))?\s*", re.I)


def _normalizar_email_obfuscado(texto: str) -> str:
    """Normaliza variantes comuns como 'nome arroba dominio ponto com'."""
    texto = AT_PATTERN.sub("@", texto)
    texto = DOT_PATTERN.sub(".", texto)
    texto = re.sub(r"\s*@\s*", "@", texto)
    texto = re.sub(r"\s*\.\s*", ".", texto)
    return texto


def detectar_email(texto: str) -> int:
    """Retorna 1 se houver padrao de e-mail no texto, caso contrario 0."""
    if not isinstance(texto, str):
        return 0
    if EMAIL_REGEX.search(texto):
        return 1
    normalizado = _normalizar_email_obfuscado(texto)
    return int(bool(EMAIL_OBFUSCATED_REGEX.search(normalizado)))


def adicionar_coluna_email(df: pd.DataFrame) -> pd.DataFrame:
    """Adiciona coluna binaria 'email' ao DataFrame de amostra."""
    df = df.copy()
    df["email"] = df["texto_mascarado"].apply(detectar_email)
    return df


def _resolve_input_path(arg: str) -> Path:
    """Resolve caminhos de entrada, preferindo entrada/ quando relativo."""
    path = Path(arg)
    if path.is_absolute():
        return path
    candidate = ENTRADA_DIR / path
    if candidate.exists():
        return candidate
    return path


def _resolve_output_path(arg: str) -> Path:
    """Resolve caminho de saida, ancorando em saida/ quando relativo."""
    path = Path(arg)
    if path.is_absolute():
        return path
    return SAIDA_DIR / path


def _parse_cli_paths(argv: list[str]) -> tuple[Path, Path]:
    if len(argv) > 2:
        raise SystemExit("Uso: python email_detection.py [amostra.xlsx] [saida.xlsx]")
    if len(argv) >= 1:
        amostra_path = _resolve_input_path(argv[0])
    else:
        amostra_path = AMOSTRA_PATH

    if len(argv) == 2:
        saida_path = _resolve_output_path(argv[1])
    else:
        saida_path = SAIDA_DIR / f"{Path(amostra_path).stem}_com_email.xlsx"
    return amostra_path, saida_path


def main() -> None:
    try:
        amostra_path, saida_path = _parse_cli_paths(sys.argv[1:])
        amostra = carregar_amostra(amostra_path)
        amostra_com_email = adicionar_coluna_email(amostra)
        saida_path.parent.mkdir(parents=True, exist_ok=True)
        amostra_com_email.to_excel(saida_path, index=False)
        print(f"Arquivo salvo em: {saida_path}")
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        print(f"Erro: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
