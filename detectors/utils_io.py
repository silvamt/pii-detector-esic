from __future__ import annotations

from pathlib import Path

import pandas as pd

REQUIRED_COLUMNS = {"id", "texto_mascarado"}


def carregar_amostra(path: Path) -> pd.DataFrame:
    """Carrega a planilha de amostra, normaliza nomes de colunas e valida estrutura."""
    if not path.exists():
        raise FileNotFoundError(f"Arquivo de amostra nao encontrado: {path}")
    try:
        df = pd.read_excel(path)
    except Exception as exc:
        raise RuntimeError(f"Nao foi possivel ler a planilha de amostra ({exc})") from exc

    df = df.rename(columns={"ID": "id", "Texto Mascarado": "texto_mascarado"})
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"Amostra sem colunas obrigatorias {missing} em {path}")
    return df
