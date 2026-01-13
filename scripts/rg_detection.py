"""
Detecta padroes de registros de identificacao/profissionais em
`entrada/AMOSTRA.xlsx` e avalia resultados com `entrada/gabarito.json`.
Salva o resultado em `saida/`.

Uso:
    python rg_detection.py
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
SAIDA_PATH = SAIDA_DIR / "AMOSTRA_com_rg.xlsx"

# Padroes para registros de identificacao/profissionais:
# - Rotulos explicitos de RG seguidos de numeros.
# - Registros OAB com UF opcional.
# - "matricula" de servidor/estudante seguida de codigo.
# - Registro numerico no formato 21-1205-1999.
# - Rotulos NIS, usados como identificadores no dataset.
RG_LABEL_REGEX = re.compile(r"\brg\s*[:\-]?\s*\d[\d.\-]{1,}", re.IGNORECASE)
OAB_REGEX = re.compile(r"\boab\s*(?:/[A-Z]{2})?[ -]?\d[\d.\-]{3,}", re.IGNORECASE)
MATRICULA_REGEX = re.compile(
    r"\bmatr[iヴ]cul(?:a|o)\b\s*[:=]?\s*[\w\d][\w\d.\-/]{3,}", re.IGNORECASE
)
SERIAL_2_4_4_REGEX = re.compile(r"\b\d{2}-\d{4}-\d{4}\b")
NIS_REGEX = re.compile(r"\bnis\s*[:=]?\s*\d{5,}\b", re.IGNORECASE)


def carregar_amostra() -> pd.DataFrame:
    """Carrega a planilha de amostra e normaliza nomes de colunas."""
    df = pd.read_excel(AMOSTRA_PATH)
    df = df.rename(columns={"ID": "id", "Texto Mascarado": "texto_mascarado"})
    return df


def carregar_gabarito() -> pd.DataFrame:
    """Carrega o gabarito JSON."""
    return pd.read_json(GABARITO_PATH)


def detectar_rg(texto: str) -> int:
    """Retorna 1 se existir padrao de RG/registro profissional no texto."""
    if not isinstance(texto, str):
        return 0

    patterns = (
        RG_LABEL_REGEX,
        OAB_REGEX,
        MATRICULA_REGEX,
        SERIAL_2_4_4_REGEX,
        NIS_REGEX,
    )
    return int(any(pattern.search(texto) for pattern in patterns))


def adicionar_coluna_rg(df: pd.DataFrame) -> pd.DataFrame:
    """Adiciona a coluna binaria 'rg' ao DataFrame."""
    df = df.copy()
    df["rg"] = df["texto_mascarado"].apply(detectar_rg)
    return df


def calcular_metricas(merged: pd.DataFrame) -> dict[str, float]:
    """Calcula metricas basicas a partir de rg_pred e rg_true."""
    tp = ((merged["rg_pred"] == 1) & (merged["rg_true"] == 1)).sum()
    fp = ((merged["rg_pred"] == 1) & (merged["rg_true"] == 0)).sum()
    fn = ((merged["rg_pred"] == 0) & (merged["rg_true"] == 1)).sum()

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

    amostra_com_rg = adicionar_coluna_rg(amostra)
    SAIDA_PATH.parent.mkdir(parents=True, exist_ok=True)
    amostra_com_rg.to_excel(SAIDA_PATH, index=False)

    merged = amostra_com_rg[["id", "rg"]].merge(
        gabarito[["id", "rg"]],
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
