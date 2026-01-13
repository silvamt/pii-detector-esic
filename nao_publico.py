"""
Gera a coluna binaria `nao_publico` combinando detectores existentes
(email, cpf, telefone, rg, nome). O circuito e priorizado
(email -> cpf -> telefone -> rg -> nome) e para assim que marcar 1.

Uso (amostra obrigatoria):
    python nao_publico.py <amostra.xlsx> [saida.xlsx]

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
SCRIPTS_DIR = ROOT_DIR / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from cpf_detection import detectar_cpf
from email_detection import detectar_email
from nome_detection import detectar_nome
from rg_detection import detectar_rg
from telefone_detection import detectar_telefone

ENTRADA_DIR = ROOT_DIR / "entrada"
SAIDA_DIR = ROOT_DIR / "saida"

DETECTORS: tuple[tuple[str, Callable[[str], int]], ...] = (
    ("email", detectar_email),
    ("cpf", detectar_cpf),
    ("telefone", detectar_telefone),
    ("rg", detectar_rg),
    ("nome", detectar_nome),
)
DETECTOR_ORDER = tuple(det[0] for det in DETECTORS)


def coerce_binary_series(series: pd.Series, column_name: str) -> pd.Series:
    """Normaliza uma serie para 0/1, tratando valores faltantes e nao numericos."""
    numeric = pd.to_numeric(series, errors="coerce")
    invalid_mask = ~numeric.isin([0, 1]) & numeric.notna()
    if invalid_mask.any():
        print(
            f"Aviso: valores nao binarios encontrados em '{column_name}'; convertendo para 0/1."
        )
    return (numeric.fillna(0) > 0).astype(int)


def carregar_amostra(amostra_path: Path) -> pd.DataFrame:
    """Carrega a planilha de amostra, checa estrutura e normaliza colunas."""
    if not amostra_path.exists():
        raise FileNotFoundError(f"Arquivo de amostra nao encontrado: {amostra_path}")
    try:
        df = pd.read_excel(amostra_path)
    except Exception as exc:  # pragma: no cover - leitura depende de IO externo
        raise RuntimeError(f"Nao foi possivel ler a planilha de amostra ({exc})") from exc

    df = df.rename(columns={"ID": "id", "Texto Mascarado": "texto_mascarado"})
    required = {"id", "texto_mascarado"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Amostra sem colunas obrigatorias {missing} em {amostra_path}")
    return df


def executar_detectores(
    df: pd.DataFrame, reuse_existing: bool = True
) -> pd.DataFrame:
    """
    Aplica os detectores conhecidos em ordem de menor para maior complexidade.

    Quando reuse_existing=True, colunas ja presentes sao apenas normalizadas,
    evitando sobrescrita ou execucoes desnecessarias.
    """
    out = df.copy()

    detector_iter = (
        tqdm(DETECTORS, desc="Executando detectores", unit="coluna")
        if tqdm is not None
        else DETECTORS
    )

    for coluna, detectar in detector_iter:
        if reuse_existing and coluna in out.columns:
            out[coluna] = coerce_binary_series(out[coluna], coluna)
            continue

        out[coluna] = _progress_apply(
            out["texto_mascarado"], detectar, desc=f"Detectando {coluna}"
        )
        if coluna not in out.columns:
            raise KeyError(f"Detector nao adicionou a coluna esperada '{coluna}'.")
        out[coluna] = coerce_binary_series(out[coluna], coluna)
    return out


def _progress_apply(
    series: pd.Series, detector: Callable[[str], int], desc: str
) -> pd.Series:
    """Aplica um detector exibindo barra de progresso quando tqdm estiver instalado."""
    if tqdm is None:
        return series.apply(detector)
    tqdm.pandas(desc=desc)
    return series.progress_apply(detector)


def preencher_nao_publico(
    df: pd.DataFrame, detector_order: Iterable[str] = DETECTOR_ORDER
) -> pd.DataFrame:
    """Cria a coluna nao_publico interrompendo na primeira marcacao positiva."""
    df = df.copy()
    for coluna in detector_order:
        if coluna not in df.columns:
            raise ValueError(f"Coluna esperada ausente: '{coluna}'. Rode os detectores antes.")
        df[coluna] = coerce_binary_series(df[coluna], coluna)

    df["nao_publico"] = 0
    for coluna in detector_order:
        pendentes = df["nao_publico"] == 0
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


def _parse_cli_paths(argv: list[str]) -> tuple[Path, Path | None]:
    """Interpreta argumentos de linha de comando com defaults."""
    if len(argv) == 0 or len(argv) > 2:
        raise SystemExit(
            "Uso: python nao_publico.py <amostra.xlsx> [saida.xlsx]"
        )

    amostra_path = _resolve_input_path(argv[0], ENTRADA_DIR)
    if amostra_path is None:
        raise SystemExit("O caminho da amostra e obrigatorio.")

    if len(argv) >= 2:
        saida_path = _resolve_output_path(argv[1], SAIDA_DIR)
    else:
        saida_path = SAIDA_DIR / f"{Path(amostra_path).stem}_com_nao_publico.xlsx"

    return amostra_path, saida_path


def main(
    amostra_path: Path,
    saida_path: Path | None = None,
) -> None:
    amostra = carregar_amostra(amostra_path)

    if saida_path is None:
        saida_path = SAIDA_DIR / f"{Path(amostra_path).stem}_com_nao_publico.xlsx"

    com_detectores = executar_detectores(amostra)
    com_flag = preencher_nao_publico(com_detectores)

    saida_path.parent.mkdir(parents=True, exist_ok=True)
    com_flag.to_excel(saida_path, index=False)

    positivos = int((com_flag["nao_publico"] == 1).sum())
    total = len(com_flag)
    print(f"Registros marcados como nao_publico=1: {positivos}/{total}")

    print(f"Arquivo salvo em: {saida_path}")


if __name__ == "__main__":
    try:
        amostra_cli, saida_cli = _parse_cli_paths(sys.argv[1:])
        main(amostra_cli, saida_cli)
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        print(f"Erro: {exc}")
        sys.exit(1)
    except Exception as exc:  # pragma: no cover - fallback defensivo
        print(f"Erro inesperado: {exc}")
        sys.exit(1)
