"""
Detecta padroes de registros de identificacao/profissionais em
`entrada/AMOSTRA.xlsx` e salva o resultado em `saida/`.

Uso:
    python rg_detection.py
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
SAIDA_PATH = SAIDA_DIR / "AMOSTRA_com_rg.xlsx"

# Padroes para registros de identificacao/profissionais:
# - Rotulos explicitos de RG seguidos de numeros.
# - Registros OAB com UF opcional.
# - "matricula" de servidor/estudante seguida de codigo.
# - Registro numerico no formato 21-1205-1999 quando acompanhado de rotulo.
# - Rotulos NIS, usados como identificadores no dataset.
RG_LABEL_REGEX = re.compile(r"\brg\s*[:\-]?\s*\d[\d.\-]{1,}", re.IGNORECASE)
OAB_REGEX = re.compile(r"\boab\s*(?:/[A-Z]{2})?[ -]?\d[\d.\-]{3,}", re.IGNORECASE)
MATRICULA_REGEX = re.compile(
    r"\bmatr[iヴ]cul(?:a|o)\b\s*[:=]?\s*[\w\d][\w\d.\-/]{3,}", re.IGNORECASE
)
SERIAL_2_4_4_WITH_LABEL_REGEX = re.compile(
    r"\b(?:rg|registro|identidade)\b[\w\s:.-]{0,10}\d{2}-\d{4}-\d{4}\b",
    re.IGNORECASE,
)
NIS_REGEX = re.compile(r"\bnis\s*[:=]?\s*\d{5,}\b", re.IGNORECASE)
IMOVEL_CONTEXT_REGEX = re.compile(r"\bim[oó]vel|imobili[aá]ri", re.IGNORECASE)


def detectar_rg(texto: str) -> int:
    """Retorna 1 se existir padrao de RG/registro profissional no texto."""
    if not isinstance(texto, str):
        return 0

    if RG_LABEL_REGEX.search(texto):
        return 1
    if OAB_REGEX.search(texto):
        return 1
    if SERIAL_2_4_4_WITH_LABEL_REGEX.search(texto):
        return 1
    if NIS_REGEX.search(texto):
        return 1

    matricula_match = MATRICULA_REGEX.search(texto)
    if matricula_match:
        # Evita marcar matriculas de imoveis quando o contexto indica esse assunto.
        contexto_local = texto[
            max(0, matricula_match.start() - 40) : matricula_match.end() + 40
        ]
        if not IMOVEL_CONTEXT_REGEX.search(contexto_local):
            return 1
    return 0


def adicionar_coluna_rg(df: pd.DataFrame) -> pd.DataFrame:
    """Adiciona a coluna binaria 'rg' ao DataFrame."""
    df = df.copy()
    df["rg"] = df["texto_mascarado"].apply(detectar_rg)
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
        raise SystemExit("Uso: python rg_detection.py [amostra.xlsx] [saida.xlsx]")
    if len(argv) >= 1:
        amostra_path = _resolve_input_path(argv[0])
    else:
        amostra_path = AMOSTRA_PATH

    if len(argv) == 2:
        saida_path = _resolve_output_path(argv[1])
    else:
        saida_path = SAIDA_DIR / f"{Path(amostra_path).stem}_com_rg.xlsx"
    return amostra_path, saida_path


def main() -> None:
    try:
        amostra_path, saida_path = _parse_cli_paths(sys.argv[1:])
        amostra = carregar_amostra(amostra_path)
        amostra_com_rg = adicionar_coluna_rg(amostra)
        saida_path.parent.mkdir(parents=True, exist_ok=True)
        amostra_com_rg.to_excel(saida_path, index=False)
        print(f"Arquivo salvo em: {saida_path}")
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        print(f"Erro: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
