"""
Detecta padroes de telefone em `entrada/AMOSTRA.xlsx` e avalia resultados com
`entrada/gabarito.json`. Salva o resultado em `saida/`.

Uso:
    python telefone_detection.py
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
ENTRADA_DIR = BASE_DIR / "entrada"
SAIDA_DIR = BASE_DIR / "saida"
AMOSTRA_PATH = ENTRADA_DIR / "AMOSTRA.xlsx"
GABARITO_PATH = ENTRADA_DIR / "gabarito.json"
SAIDA_PATH = SAIDA_DIR / "AMOSTRA_com_telefone.xlsx"

# Heuristica: exige DDD brasileiro (dois digitos, sem iniciar com 0) com
# parenteses ou separador, seguido de numero local de 8 ou 9 digitos.
PHONE_REGEX = re.compile(
    r"""
    (?<!\d)
    (?:
        \([1-9]\d\)\s*                   # (11) optionally followed by space
        |
        [1-9]\d[\s-]+                    # 11 or 11- plus at least one separator
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


def carregar_amostra() -> pd.DataFrame:
    """Carrega a planilha de amostra e normaliza nomes de colunas."""
    df = pd.read_excel(AMOSTRA_PATH)
    df = df.rename(columns={"ID": "id", "Texto Mascarado": "texto_mascarado"})
    return df


def carregar_gabarito() -> pd.DataFrame:
    """Carrega o gabarito JSON."""
    return pd.read_json(GABARITO_PATH)


def detectar_telefone(texto: str) -> int:
    """Retorna 1 se houver padrao de telefone no texto, senao 0."""
    if not isinstance(texto, str):
        return 0
    return int(bool(PHONE_REGEX.search(texto)))


def adicionar_coluna_telefone(df: pd.DataFrame) -> pd.DataFrame:
    """Adiciona a coluna binaria 'telefone' ao DataFrame."""
    df = df.copy()
    df["telefone"] = df["texto_mascarado"].apply(detectar_telefone)
    return df


def calcular_metricas(merged: pd.DataFrame) -> dict[str, float]:
    """Calcula metricas basicas a partir de telefone_pred e telefone_true."""
    tp = ((merged["telefone_pred"] == 1) & (merged["telefone_true"] == 1)).sum()
    fp = ((merged["telefone_pred"] == 1) & (merged["telefone_true"] == 0)).sum()
    fn = ((merged["telefone_pred"] == 0) & (merged["telefone_true"] == 1)).sum()

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0

    return {
        "tp": int(tp),
        "fp": int(fp),
        "fn": int(fn),
        "precision": precision,
        "recall": recall,
    }


def main() -> None:
    amostra = carregar_amostra()
    gabarito = carregar_gabarito()

    amostra_com_telefone = adicionar_coluna_telefone(amostra)
    SAIDA_PATH.parent.mkdir(parents=True, exist_ok=True)
    amostra_com_telefone.to_excel(SAIDA_PATH, index=False)

    merged = amostra_com_telefone[["id", "telefone"]].merge(
        gabarito[["id", "telefone"]],
        on="id",
        how="inner",
        suffixes=("_pred", "_true"),
    )

    metricas = calcular_metricas(merged)

    print("Contagem:")
    print(f"  Verdadeiros Positivos: {metricas['tp']}")
    print(f"  Falsos Positivos:     {metricas['fp']}")
    print(f"  Falsos Negativos:     {metricas['fn']}")
    print("Metricas:")
    print(f"  Precisao: {metricas['precision']:.3f}")
    print(f"  Recall:   {metricas['recall']:.3f}")
    print(f"Arquivo salvo em: {SAIDA_PATH}")


if __name__ == "__main__":
    main()
