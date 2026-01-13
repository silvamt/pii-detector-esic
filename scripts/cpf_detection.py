"""
Detecta padroes de CPF em `entrada/AMOSTRA.xlsx` e avalia resultados com
`entrada/gabarito.json`. Salva o resultado em `saida/`.

Uso:
    python cpf_detection.py
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
SAIDA_PATH = SAIDA_DIR / "AMOSTRA_com_cpf.xlsx"

# Detecao em duas etapas:
# 1) Preferir numeros explicitamente marcados como CPF (formatados ou crus).
# 2) Sem o rotulo, aceitar apenas CPFs formatados (###.###.###-##) para reduzir falsos positivos.
CPF_WITH_LABEL_REGEX = re.compile(
    r"(?i)cpf\s*[:\-]?\s*(\d{3}\.?\d{3}\.?\d{3}-?\d{1,2}|\d{11})"
)
CPF_FORMATTED_REGEX = re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{1,2}\b")


def carregar_amostra() -> pd.DataFrame:
    """Carrega a planilha de amostra e normaliza nomes de colunas."""
    df = pd.read_excel(AMOSTRA_PATH)
    df = df.rename(columns={"ID": "id", "Texto Mascarado": "texto_mascarado"})
    return df


def carregar_gabarito() -> pd.DataFrame:
    """Carrega o gabarito JSON."""
    return pd.read_json(GABARITO_PATH)


def detectar_cpf(texto: str) -> int:
    """Retorna 1 se existir padrao de CPF no texto, senao 0."""
    if not isinstance(texto, str):
        return 0
    # Preferir CPFs acompanhados do rotulo textual "CPF".
    if CPF_WITH_LABEL_REGEX.search(texto):
        return 1
    # Sem o rotulo, exigir formato canonico para evitar numeros de protocolo.
    return int(bool(CPF_FORMATTED_REGEX.search(texto)))


def adicionar_coluna_cpf(df: pd.DataFrame) -> pd.DataFrame:
    """Adiciona a coluna binaria 'cpf' ao DataFrame."""
    df = df.copy()
    df["cpf"] = df["texto_mascarado"].apply(detectar_cpf)
    return df


def calcular_metricas(merged: pd.DataFrame) -> dict[str, float]:
    """Calcula metricas basicas a partir de cpf_pred e cpf_true."""
    tp = ((merged["cpf_pred"] == 1) & (merged["cpf_true"] == 1)).sum()
    fp = ((merged["cpf_pred"] == 1) & (merged["cpf_true"] == 0)).sum()
    fn = ((merged["cpf_pred"] == 0) & (merged["cpf_true"] == 1)).sum()

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

    amostra_com_cpf = adicionar_coluna_cpf(amostra)
    SAIDA_PATH.parent.mkdir(parents=True, exist_ok=True)
    amostra_com_cpf.to_excel(SAIDA_PATH, index=False)

    merged = amostra_com_cpf[["id", "cpf"]].merge(
        gabarito[["id", "cpf"]],
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
