"""
Gera a coluna binaria `nao_publico` combinando detectores existentes
(email, cpf, telefone, rg, nome). O circuito e priorizado
(email -> cpf -> telefone -> rg -> nome) e para assim que marcar 1,
registrando o primeiro detector em `detector_prioritario`.

Uso (amostra obrigatoria):
    python nao_publico.py <amostra.xlsx> [saida.xlsx] [--recalcular]

Resolucao de caminhos:
- Se a amostra/saida for relativa, o script tenta primeiro em `entrada/` (amostra)
  ou `saida/` (saida); se nao existir la, usa o caminho relativo informado.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable, Iterable

import pandas as pd

try:
    from tqdm.auto import tqdm
except Exception:  # pragma: no cover - dependencia opcional para feedback visual
    tqdm = None

# Garanta que os caminhos relativos de data/ funcionem mesmo se o script for
# executado de outro diretorio.
ROOT_DIR = Path(__file__).resolve().parent
DETECTORS_DIR = ROOT_DIR / "detectors"
if str(DETECTORS_DIR) not in sys.path:
    sys.path.insert(0, str(DETECTORS_DIR))

from cpf_detection import detectar_cpf
from email_detection import detectar_email
from nome_detection import detectar_nome
from rg_detection import detectar_rg
from telefone_detection import detectar_telefone
from utils_io import carregar_amostra

ENTRADA_DIR = ROOT_DIR / "entrada"
SAIDA_DIR = ROOT_DIR / "saida"

DETECTOR_PIPELINE: tuple[tuple[str, Callable[[str], int]], ...] = (
    ("email", detectar_email),
    ("cpf", detectar_cpf),
    ("telefone", detectar_telefone),
    ("rg", detectar_rg),
    ("nome", detectar_nome),
)
DETECTOR_PRIORITY = tuple(det[0] for det in DETECTOR_PIPELINE)


def coerce_binary_series(series: pd.Series, column_name: str) -> pd.Series:
    """Normaliza uma serie para 0/1, tratando valores faltantes e nao numericos."""
    numeric_series = pd.to_numeric(series, errors="coerce")
    invalid_mask = ~numeric_series.isin([0, 1]) & numeric_series.notna()
    if invalid_mask.any():
        print(
            f"Aviso: valores nao binarios encontrados em '{column_name}'; convertendo para 0/1."
        )
    return (numeric_series.fillna(0) > 0).astype(int)


def executar_detectores(
    df: pd.DataFrame, reuse_existing: bool = True
) -> pd.DataFrame:
    """
    Aplica os detectores conhecidos em ordem de menor para maior complexidade.

    Quando reuse_existing=True, colunas ja presentes sao apenas normalizadas,
    evitando sobrescrita ou execucoes desnecessarias.
    """
    result_df = df.copy()

    detector_iter = (
        tqdm(DETECTOR_PIPELINE, desc="Executando detectores", unit="coluna")
        if tqdm is not None
        else DETECTOR_PIPELINE
    )

    for coluna, detectar in detector_iter:
        if reuse_existing and coluna in result_df.columns:
            # Preserva resultados ja calculados, apenas garantindo 0/1.
            result_df[coluna] = coerce_binary_series(result_df[coluna], coluna)
            continue

        result_df[coluna] = _progress_apply(
            result_df["texto_mascarado"], detectar, desc=f"Detectando {coluna}"
        )
        if coluna not in result_df.columns:
            raise KeyError(f"Detector nao adicionou a coluna esperada '{coluna}'.")
        result_df[coluna] = coerce_binary_series(result_df[coluna], coluna)
    return result_df


def _progress_apply(
    series: pd.Series, detector: Callable[[str], int], desc: str
) -> pd.Series:
    """Aplica um detector exibindo barra de progresso quando tqdm estiver instalado."""
    if tqdm is None:
        return series.apply(detector)
    # tqdm.pandas registra o hook global, por isso chamamos por detector.
    tqdm.pandas(desc=desc)
    return series.progress_apply(detector)


def preencher_nao_publico(
    df: pd.DataFrame, detector_order: Iterable[str] = DETECTOR_PRIORITY
) -> pd.DataFrame:
    """Cria nao_publico e o detector prioritario da primeira marcacao."""
    df = df.copy()
    for coluna in detector_order:
        if coluna not in df.columns:
            raise ValueError(f"Coluna esperada ausente: '{coluna}'. Rode os detectores antes.")
        df[coluna] = coerce_binary_series(df[coluna], coluna)

    df["nao_publico"] = 0
    df["detector_prioritario"] = None
    for coluna in detector_order:
        # A primeira coluna que marca 1 define o detector prioritario.
        pendentes = df["nao_publico"] == 0
        matches = pendentes & (df[coluna] == 1)
        df.loc[matches, "detector_prioritario"] = coluna
        df.loc[pendentes, "nao_publico"] = df.loc[pendentes, coluna]
    return df


def _resolve_input_path(arg: str, base_dir: Path) -> Path:
    """Resolve caminhos de entrada, preferindo base_dir quando relativo."""
    path = Path(arg)
    if path.is_absolute():
        return path
    candidate = base_dir / path
    if candidate.exists():
        return candidate
    return path


def _resolve_output_path(arg: str, base_dir: Path) -> Path:
    """Resolve caminho de saida, ancorando em base_dir quando relativo."""
    path = Path(arg)
    if path.is_absolute():
        return path
    return base_dir / path


def _parse_cli_paths(argv: list[str]) -> tuple[Path, Path | None, bool]:
    """Interpreta argumentos de linha de comando com defaults."""
    reuse_existing = True
    positional_args = []
    for arg in argv:
        if arg == "--recalcular":
            reuse_existing = False
        else:
            positional_args.append(arg)

    if len(positional_args) == 0 or len(positional_args) > 2:
        raise SystemExit(
            "Uso: python nao_publico.py <amostra.xlsx> [saida.xlsx] [--recalcular]"
        )

    amostra_path = _resolve_input_path(positional_args[0], ENTRADA_DIR)
    if amostra_path is None:
        raise SystemExit("O caminho da amostra e obrigatorio.")

    if len(positional_args) >= 2:
        saida_path = _resolve_output_path(positional_args[1], SAIDA_DIR)
    else:
        saida_path = SAIDA_DIR / f"{Path(amostra_path).stem}_com_nao_publico.xlsx"

    return amostra_path, saida_path, reuse_existing


def main(
    amostra_path: Path,
    saida_path: Path | None = None,
    reuse_existing: bool = True,
) -> None:
    amostra = carregar_amostra(amostra_path)

    if saida_path is None:
        saida_path = SAIDA_DIR / f"{Path(amostra_path).stem}_com_nao_publico.xlsx"

    com_detectores = executar_detectores(amostra, reuse_existing=reuse_existing)
    com_flag = preencher_nao_publico(com_detectores)

    saida_path.parent.mkdir(parents=True, exist_ok=True)
    com_flag.to_excel(saida_path, index=False)

    print(f"Arquivo salvo em: {saida_path}")


if __name__ == "__main__":
    try:
        amostra_cli, saida_cli, reuse_existing = _parse_cli_paths(sys.argv[1:])
        main(amostra_cli, saida_cli, reuse_existing=reuse_existing)
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        print(f"Erro: {exc}")
        sys.exit(1)
    except Exception as exc:  # pragma: no cover - fallback defensivo
        print(f"Erro inesperado: {exc}")
        sys.exit(1)
