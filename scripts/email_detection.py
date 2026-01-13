"""
Detecta enderecos de e-mail em `entrada/AMOSTRA.xlsx` e avalia resultados em
relacao a `entrada/gabarito.json`. Salva o resultado em `saida/`.

Uso:
    python email_detection.py
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
SAIDA_PATH = SAIDA_DIR / "AMOSTRA_com_email.xlsx"

# Regex simples para padroes usuais de e-mail.
EMAIL_REGEX = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def carregar_amostra() -> pd.DataFrame:
    """Carrega a planilha de amostra e normaliza nomes de colunas."""
    df = pd.read_excel(AMOSTRA_PATH)
    df = df.rename(columns={"ID": "id", "Texto Mascarado": "texto_mascarado"})
    return df


def carregar_gabarito() -> pd.DataFrame:
    """Carrega o gabarito JSON."""
    return pd.read_json(GABARITO_PATH)


def detectar_email(texto: str) -> int:
    """Retorna 1 se houver padrao de e-mail no texto, caso contrario 0."""
    if not isinstance(texto, str):
        return 0
    return int(bool(EMAIL_REGEX.search(texto)))


def adicionar_coluna_email(df: pd.DataFrame) -> pd.DataFrame:
    """Adiciona coluna binaria 'email' ao DataFrame de amostra."""
    df = df.copy()
    df["email"] = df["texto_mascarado"].apply(detectar_email)
    return df


def calcular_metricas(merged: pd.DataFrame) -> dict[str, float]:
    """Calcula metricas basicas a partir de colunas email_pred e email_true."""
    tp = ((merged["email_pred"] == 1) & (merged["email_true"] == 1)).sum()
    fp = ((merged["email_pred"] == 1) & (merged["email_true"] == 0)).sum()
    fn = ((merged["email_pred"] == 0) & (merged["email_true"] == 1)).sum()

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

    amostra_com_email = adicionar_coluna_email(amostra)
    SAIDA_PATH.parent.mkdir(parents=True, exist_ok=True)
    amostra_com_email.to_excel(SAIDA_PATH, index=False)

    merged = amostra_com_email[["id", "email"]].merge(
        gabarito[["id", "email"]],
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
