"""
Detecta padroes de telefone em `entrada/AMOSTRA.xlsx` e salva o resultado em `saida/`.

Uso:
    python telefone_detection.py
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
SAIDA_PATH = SAIDA_DIR / "AMOSTRA_com_telefone.xlsx"

# Heuristica: exige DDD brasileiro (dois digitos, sem iniciar com 0) com
# parenteses ou separador, seguido de numero local de 8 ou 9 digitos.
# Suporta prefixo +55 e numeros 0800.
PHONE_REGEX = re.compile(
    r"""
    (?<!\d)
    (?:
        (?:\+?55\s*)?                   # +55 opcional
        \([1-9]\d\)\s*                   # (11) optionally followed by space
        |
        (?:\+?55\s*)?[1-9]\d[\s-]+       # 11 or 11- plus at least one separator
    )
    (?:
        [2-9]\d{4}[\s-]?\d{4}             # 9-digit local part with optional hyphen/space
        |
        [2-9]\d{3}[\s-]?\d{4}             # 8-digit local part with optional hyphen/space
        |
        [2-9]\d{7,8}                      # compact 8-9 digit local part
    )
    (?![\d-])
    """,
    re.VERBOSE,
)

PHONE_LABEL_COMPACT_REGEX = re.compile(
    r"""
    (?i)
    \b(?:tel(?:efone)?|cel(?:ular)?|whats(?:app)?|contato)\b
    [^\d]{0,6}
    (?:\+?55\s*)?
    \s*\(?[1-9]\d\)?\s*
    [2-9]\d{7,8}
    \b
    """,
    re.VERBOSE,
)
# 0800 sem rotulo e comum em textos genericos; exige indicio de contato.
PHONE_0800_WITH_LABEL_REGEX = re.compile(
    r"(?i)\b(?:tel(?:efone)?|contato)\b[^\d]{0,6}0?800[\s-]?\d{3}[\s-]?\d{4}\b"
)


def detectar_telefone(texto: str) -> int:
    """Retorna 1 se houver padrao de telefone no texto, senao 0."""
    if not isinstance(texto, str):
        return 0
    if PHONE_REGEX.search(texto):
        return 1
    if PHONE_LABEL_COMPACT_REGEX.search(texto):
        return 1
    return int(bool(PHONE_0800_WITH_LABEL_REGEX.search(texto)))


def adicionar_coluna_telefone(df: pd.DataFrame) -> pd.DataFrame:
    """Adiciona a coluna binaria 'telefone' ao DataFrame."""
    df = df.copy()
    df["telefone"] = df["texto_mascarado"].apply(detectar_telefone)
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
        raise SystemExit("Uso: python telefone_detection.py [amostra.xlsx] [saida.xlsx]")
    if len(argv) >= 1:
        amostra_path = _resolve_input_path(argv[0])
    else:
        amostra_path = AMOSTRA_PATH

    if len(argv) == 2:
        saida_path = _resolve_output_path(argv[1])
    else:
        saida_path = SAIDA_DIR / f"{Path(amostra_path).stem}_com_telefone.xlsx"
    return amostra_path, saida_path


def main() -> None:
    try:
        amostra_path, saida_path = _parse_cli_paths(sys.argv[1:])
        amostra = carregar_amostra(amostra_path)
        amostra_com_telefone = adicionar_coluna_telefone(amostra)
        saida_path.parent.mkdir(parents=True, exist_ok=True)
        amostra_com_telefone.to_excel(saida_path, index=False)
        print(f"Arquivo salvo em: {saida_path}")
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        print(f"Erro: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
