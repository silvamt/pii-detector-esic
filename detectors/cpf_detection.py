"""
Detecta padroes de CPF em `entrada/AMOSTRA.xlsx` e salva o resultado em `saida/`.

Uso:
    python cpf_detection.py
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
SAIDA_PATH = SAIDA_DIR / "AMOSTRA_com_cpf.xlsx"

# Detecao em duas etapas:
# 1) Preferir numeros explicitamente marcados como CPF (formatados ou crus).
# 2) Sem o rotulo, aceitar apenas CPFs formatados (###.###.###-##) para reduzir falsos positivos.
CPF_WITH_LABEL_REGEX = re.compile(
    r"(?i)cpf\s*[:\-]?\s*(\d{3}[\.\s-]?\d{3}[\.\s-]?\d{3}[\.\s-]?\d{2}|\d{11})"
)
CPF_FORMATTED_REGEX = re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b")
CPF_CANDIDATE_REGEX = re.compile(r"\b(?:\d{3}[\.\s-]?){3}\d{2}\b")


def _only_digits(value: str) -> str:
    return re.sub(r"\D", "", value)


def _validar_cpf(cpf: str) -> bool:
    """Valida CPF por digitos verificadores."""
    cpf = _only_digits(cpf)
    if len(cpf) != 11:
        return False
    if cpf == cpf[0] * 11:
        return False

    def _digito(base: str) -> int:
        soma = sum(int(d) * peso for d, peso in zip(base, range(len(base) + 1, 1, -1)))
        resto = soma % 11
        return 0 if resto < 2 else 11 - resto

    d1 = _digito(cpf[:9])
    d2 = _digito(cpf[:9] + str(d1))
    return cpf[-2:] == f"{d1}{d2}"


def detectar_cpf(texto: str) -> int:
    """Retorna 1 se existir padrao de CPF no texto, senao 0."""
    if not isinstance(texto, str):
        return 0
    # Preferir CPFs acompanhados do rotulo textual "CPF".
    label_match = CPF_WITH_LABEL_REGEX.search(texto)
    if label_match:
        return int(_validar_cpf(label_match.group(1)))
    # Sem o rotulo, exigir formato canonico para evitar numeros de protocolo.
    formatted_match = CPF_FORMATTED_REGEX.search(texto)
    if formatted_match:
        return int(_validar_cpf(formatted_match.group(0)))
    # Variante sem rotulo mas com separadores variados ou espacos.
    for match in CPF_CANDIDATE_REGEX.finditer(texto):
        if _validar_cpf(match.group(0)):
            return 1
    return 0


def adicionar_coluna_cpf(df: pd.DataFrame) -> pd.DataFrame:
    """Adiciona a coluna binaria 'cpf' ao DataFrame."""
    df = df.copy()
    df["cpf"] = df["texto_mascarado"].apply(detectar_cpf)
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
        raise SystemExit("Uso: python cpf_detection.py [amostra.xlsx] [saida.xlsx]")
    if len(argv) >= 1:
        amostra_path = _resolve_input_path(argv[0])
    else:
        amostra_path = AMOSTRA_PATH

    if len(argv) == 2:
        saida_path = _resolve_output_path(argv[1])
    else:
        saida_path = SAIDA_DIR / f"{Path(amostra_path).stem}_com_cpf.xlsx"
    return amostra_path, saida_path


def main() -> None:
    try:
        amostra_path, saida_path = _parse_cli_paths(sys.argv[1:])
        amostra = carregar_amostra(amostra_path)
        amostra_com_cpf = adicionar_coluna_cpf(amostra)
        saida_path.parent.mkdir(parents=True, exist_ok=True)
        amostra_com_cpf.to_excel(saida_path, index=False)
        print(f"Arquivo salvo em: {saida_path}")
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        print(f"Erro: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
