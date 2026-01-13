"""
Calcula metricas de `nao_publico` comparando um resultado com o gabarito.

Uso:
    python avaliar_nao_publico.py <resultado_nao_publico.xlsx> [gabarito.json]

Resolucao de caminhos:
- Arquivo de resultado: se relativo, procurado primeiro em `saida/`.
- Gabarito: se relativo, procurado primeiro em `entrada/` (default: entrada/gabarito.json).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parent
ENTRADA_DIR = ROOT_DIR / "entrada"
SAIDA_DIR = ROOT_DIR / "saida"
DEFAULT_GABARITO_PATH = ENTRADA_DIR / "gabarito.json"
DETECTOR_ORDER = ("email", "cpf", "telefone", "rg", "nome")


def coerce_binary_series(series: pd.Series, column_name: str) -> pd.Series:
    """Normaliza uma serie para 0/1, tratando valores faltantes e nao numericos."""
    numeric = pd.to_numeric(series, errors="coerce")
    invalid_mask = ~numeric.isin([0, 1]) & numeric.notna()
    if invalid_mask.any():
        print(
            f"Aviso: valores nao binarios encontrados em '{column_name}'; convertendo para 0/1."
        )
    return (numeric.fillna(0) > 0).astype(int)


def carregar_resultado(resultado_path: Path) -> pd.DataFrame:
    """Carrega arquivo com coluna nao_publico (Excel) e normaliza campos."""
    if not resultado_path.exists():
        raise FileNotFoundError(f"Resultado nao encontrado: {resultado_path}")
    try:
        df = pd.read_excel(resultado_path)
    except Exception as exc:  # pragma: no cover - depende de IO externo
        raise RuntimeError(f"Nao foi possivel ler o resultado ({exc})") from exc

    if "ID" in df.columns and "id" not in df.columns:
        df = df.rename(columns={"ID": "id"})

    required = {"id", "nao_publico"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Resultado sem colunas obrigatorias {missing} em {resultado_path}")

    df = df[["id", "nao_publico"]].copy()
    df["nao_publico"] = coerce_binary_series(df["nao_publico"], "nao_publico")
    return df


def carregar_gabarito(gabarito_path: Path) -> pd.DataFrame:
    """Carrega o gabarito JSON."""
    if not gabarito_path.exists():
        raise FileNotFoundError(f"Gabarito nao encontrado: {gabarito_path}")
    try:
        df = pd.read_json(gabarito_path)
    except ValueError as exc:
        raise RuntimeError(f"Nao foi possivel ler gabarito.json ({exc})") from exc

    if "ID" in df.columns and "id" not in df.columns:
        df = df.rename(columns={"ID": "id"})
    if "id" not in df.columns:
        raise ValueError("Gabarito sem coluna 'id'; nao e possivel calcular metricas.")
    return df


def preparar_gabarito_nao_publico(gabarito: pd.DataFrame) -> pd.DataFrame:
    """Normaliza colunas do gabarito e gera nao_publico_true."""
    colunas_esperadas = set(DETECTOR_ORDER)
    missing = colunas_esperadas - set(gabarito.columns)
    if missing:
        raise ValueError(f"Gabarito incompleto, faltam colunas: {', '.join(sorted(missing))}")

    normalizado = gabarito.copy()
    for coluna in colunas_esperadas:
        normalizado[coluna] = coerce_binary_series(normalizado[coluna], f"gabarito.{coluna}")
    normalizado["nao_publico_true"] = (
        normalizado[list(colunas_esperadas)].sum(axis=1) > 0
    ).astype(int)
    return normalizado[["id", "nao_publico_true"]]


def calcular_metricas_nao_publico(
    pred_df: pd.DataFrame, gabarito: pd.DataFrame
) -> dict[str, float]:
    """Calcula metricas de nao_publico comparando com gabarito normalizado."""
    gabarito_normalizado = preparar_gabarito_nao_publico(gabarito)

    merged = (
        pred_df[["id", "nao_publico"]]
        .rename(columns={"nao_publico": "nao_publico_pred"})
        .merge(gabarito_normalizado, on="id", how="outer")
    )
    merged["nao_publico_pred"] = coerce_binary_series(
        merged["nao_publico_pred"], "nao_publico_pred"
    )
    merged["nao_publico_true"] = coerce_binary_series(
        merged["nao_publico_true"], "nao_publico_true"
    )

    tp = ((merged["nao_publico_pred"] == 1) & (merged["nao_publico_true"] == 1)).sum()
    fp = ((merged["nao_publico_pred"] == 1) & (merged["nao_publico_true"] == 0)).sum()
    fn = ((merged["nao_publico_pred"] == 0) & (merged["nao_publico_true"] == 1)).sum()

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0

    return {
        "tp": int(tp),
        "fp": int(fp),
        "fn": int(fn),
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def _resolve_input_path(arg: str, base_dir: Path) -> Path:
    """Resolve caminhos de entrada, preferindo base_dir quando relativo."""
    path = Path(arg)
    if path.is_absolute():
        return path
    candidate = base_dir / path
    if candidate.exists():
        return candidate
    return path


def _parse_cli_paths(argv: list[str]) -> tuple[Path, Path]:
    """Interpreta argumentos de linha de comando."""
    if len(argv) == 0 or len(argv) > 2:
        raise SystemExit(
            "Uso: python avaliar_nao_publico.py <resultado_nao_publico.xlsx> [gabarito.json]"
        )
    resultado_path = _resolve_input_path(argv[0], SAIDA_DIR)
    gabarito_path = (
        _resolve_input_path(argv[1], ENTRADA_DIR) if len(argv) >= 2 else DEFAULT_GABARITO_PATH
    )
    return resultado_path, gabarito_path


def main(resultado_path: Path, gabarito_path: Path) -> None:
    resultado = carregar_resultado(resultado_path)
    gabarito = carregar_gabarito(gabarito_path)
    metricas = calcular_metricas_nao_publico(resultado, gabarito)

    print("Contagem:")
    print(f"  Verdadeiros Positivos: {metricas['tp']}")
    print(f"  Falsos Positivos:     {metricas['fp']}")
    print(f"  Falsos Negativos:     {metricas['fn']}")
    print("Metricas:")
    print(f"  Precisao: {metricas['precision']:.3f}")
    print(f"  Recall:   {metricas['recall']:.3f}")
    print(f"  F1-score: {metricas['f1']:.3f}")


if __name__ == "__main__":
    try:
        resultado_cli, gabarito_cli = _parse_cli_paths(sys.argv[1:])
        main(resultado_cli, gabarito_cli)
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        print(f"Erro: {exc}")
        sys.exit(1)
    except Exception as exc:  # pragma: no cover - fallback defensivo
        print(f"Erro inesperado: {exc}")
        sys.exit(1)
