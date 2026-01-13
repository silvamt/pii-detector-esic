"""
Detecta mencoes a nomes de pessoas em `entrada/AMOSTRA.xlsx` e avalia os
resultados usando `entrada/gabarito.json`. Salva o resultado em `saida/`.

Estrategia:
- Usa pesos precomputados de tokens (`data/nome_weights.csv`) aprendidos fora do
  conjunto de controle para priorizar sequencias que parecam nomes, mesmo sem
  depender de capitalizacao.
- Pesos negativos penalizam termos institucionais/assunto (ex.: edital,
  protocolo, concurso), reduzindo falsos positivos.
- Mantem pistas simples ("meu nome e", "me chamo", assinaturas) para aumentar
  o recall.

Uso:
    python nome_detection.py
"""

from __future__ import annotations

import json
import os
import re
import unicodedata
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
ENTRADA_DIR = BASE_DIR / "entrada"
SAIDA_DIR = BASE_DIR / "saida"
DATA_DIR = BASE_DIR / "data"
AMOSTRA_PATH = ENTRADA_DIR / "AMOSTRA.xlsx"
GABARITO_PATH = ENTRADA_DIR / "gabarito.json"
SAIDA_PATH = SAIDA_DIR / "AMOSTRA_com_nome.xlsx"
PESOS_CACHE_PATH = DATA_DIR / "nome_weights.csv"
OPENAI_MODEL = os.getenv("NOME_OPENAI_MODEL", "gpt-4o-mini")
OPENAI_LOOKUP_ENABLED = os.getenv("NOME_OPENAI_LOOKUP", "0").lower() in {
    "1",
    "true",
    "yes",
    "on",
}

# Regex para tokens que lembram nomes (suporta acentos e qualquer capitalizacao).
NAME_TOKEN = r"[A-Za-zÀ-ÖØ-öø-ÿ][A-Za-zÀ-ÖØ-öø-ÿ'-]{1,}"
CONNECTOR = r"(?:da|de|do|dos|das|e)"
NAME_SEQUENCE_REGEX = re.compile(
    rf"\b{NAME_TOKEN}(?:\s+(?:{CONNECTOR}\s+)?{NAME_TOKEN})+\b",
    flags=re.IGNORECASE,
)
NAME_LABEL_REGEX = re.compile(
    rf"(?i)\bnome\s*[:\-]?\s*{NAME_TOKEN}(?:\s+(?:{CONNECTOR}\s+)?{NAME_TOKEN})*"
)
INTRO_REGEX = re.compile(
    rf"(?i)\b(?:meu\s+nome\s+e|me\s+chamo|sou\s+[oa]?|ass(?:inatura|inado)?|att\.?|at\.?\.?te?\.?|atenciosamente)[,:\s]+{NAME_TOKEN}(?:\s+(?:{CONNECTOR}\s+)?{NAME_TOKEN})*"
)

CONNECTOR_WORDS = {"da", "de", "do", "dos", "das", "e"}
# Fallback leve caso os pesos nao estejam disponiveis.
FALLBACK_NEG_TOKENS = {
    "concurso",
    "edital",
    "protocolo",
    "processo",
    "prefeitura",
    "secretaria",
    "governo",
}
FALLBACK_NEG_WEIGHT = -0.6

NAME_WEIGHTS: dict[str, float] | None = None
_OPENAI_CLIENT = None


def _norm(token: str) -> str:
    """Converte para minusculas e remove acentos para comparacao estavel."""
    decomposed = unicodedata.normalize("NFD", token.lower())
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


CONNECTOR_WORDS_NORM = {_norm(w) for w in CONNECTOR_WORDS}
FALLBACK_NEG_TOKENS_NORM = {_norm(w) for w in FALLBACK_NEG_TOKENS}


def carregar_amostra() -> pd.DataFrame:
    """Carrega a planilha de amostra e normaliza nomes de colunas."""
    df = pd.read_excel(AMOSTRA_PATH)
    df = df.rename(columns={"ID": "id", "Texto Mascarado": "texto_mascarado"})
    return df


def carregar_gabarito() -> pd.DataFrame:
    """Carrega o gabarito JSON."""
    return pd.read_json(GABARITO_PATH)


def carregar_pesos_nomes() -> dict[str, float]:
    """
    Carrega pesos precomputados de tokens. Aceita pesos negativos para
    penalizar termos institucionais ou de assunto.
    """
    try:
        cached = pd.read_csv(PESOS_CACHE_PATH)
    except FileNotFoundError:
        print(
            "Aviso: nome_weights.csv nao encontrado; o detector usara apenas heuristicas."
        )
        return {}
    except Exception as exc:
        print(f"Aviso: nao foi possivel ler nome_weights.csv ({exc}); usando heuristicas.")
        return {}

    weights: dict[str, float] = {}
    for _, row in cached.iterrows():
        token = str(row.get("token", "")).strip()
        weight = row.get("weight")
        if not token:
            continue
        if pd.notna(weight):
            weights[_norm(token)] = float(weight)
    for neg in FALLBACK_NEG_TOKENS_NORM:
        weights.setdefault(neg, FALLBACK_NEG_WEIGHT)
    return weights


def _consultar_openai_tokens(fragmento: str, tokens: list[str]) -> dict[str, float]:
    """
    Consulta a API da OpenAI para atribuir pesos a tokens desconhecidos.
    Retorna dict normalizado token->peso. Requer OPENAI_API_KEY e
    NOME_OPENAI_LOOKUP=1 nas variaveis de ambiente.
    """
    if not OPENAI_LOOKUP_ENABLED:
        return {}
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return {}
    global _OPENAI_CLIENT
    try:
        from openai import OpenAI
    except Exception as exc:
        print(f"Aviso: pacote openai indisponivel ({exc}); sem lookup.")
        return {}
    if _OPENAI_CLIENT is None:
        _OPENAI_CLIENT = OpenAI(api_key=api_key)

    sys_prompt = (
        "Você classifica tokens quanto à probabilidade de serem nomes de pessoa. "
        "Retorne um JSON com os tokens como chaves e pesos numéricos entre -1 e 1. "
        "Use pesos negativos para termos institucionais ou genéricos, positivos para nomes."
    )
    user_prompt = (
        "Texto completo:\n"
        f"{fragmento}\n\n"
        "Tokens desconhecidos:\n"
        f"{tokens}\n\n"
        "Responda apenas JSON. Exemplo: {\"ana\": 0.9, \"edital\": -0.8}"
    )

    try:
        resp = _OPENAI_CLIENT.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0,
        )
    except Exception as exc:
        print(f"Aviso: falha na consulta OpenAI ({exc}); seguindo sem lookup.")
        return {}

    content = None
    try:
        content = resp.choices[0].message.content  # type: ignore[attr-defined]
    except Exception:
        pass
    if not content:
        return {}

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        print("Aviso: resposta OpenAI sem JSON valido; ignorando.")
        return {}

    normalized: dict[str, float] = {}
    for tok, weight in parsed.items():
        if not isinstance(tok, str):
            continue
        if isinstance(weight, (int, float)):
            normalized[_norm(tok)] = float(weight)
    return normalized


def _registrar_pesos_cache(novos: dict[str, float]) -> None:
    """Persiste pesos novos no CSV sem sobrescrever entradas existentes."""
    if not novos:
        return
    try:
        df = pd.read_csv(PESOS_CACHE_PATH)
    except FileNotFoundError:
        df = pd.DataFrame(columns=["token", "weight"])
    tokens_exist = {_norm(str(t)) for t in df.get("token", [])}
    rows = [
        {"token": tok, "weight": weight}
        for tok, weight in novos.items()
        if tok not in tokens_exist
    ]
    if not rows:
        return
    df_out = pd.concat([df, pd.DataFrame(rows)], ignore_index=True)
    df_out.to_csv(PESOS_CACHE_PATH, index=False)


def _parece_nome_pessoal(fragmento: str) -> bool:
    """Retorna True se uma sequencia textual parecer nome de pessoa."""
    global NAME_WEIGHTS
    if NAME_WEIGHTS is None:
        NAME_WEIGHTS = carregar_pesos_nomes()

    tokens = []
    for t in re.findall(NAME_TOKEN, fragmento):
        low = _norm(t)
        if low in CONNECTOR_WORDS_NORM:
            continue
        tokens.append(low)

    if len(tokens) < 2:
        return False
    if tokens and tokens[0] == "lei":
        return False

    if not NAME_WEIGHTS:
        if any(t in FALLBACK_NEG_TOKENS_NORM for t in tokens):
            return False
        return len(tokens) <= 4

    unknown_tokens = [t for t in tokens if t not in NAME_WEIGHTS]
    if unknown_tokens:
        novos_pesos = _consultar_openai_tokens(fragmento, unknown_tokens)
        if novos_pesos:
            NAME_WEIGHTS.update(novos_pesos)
            _registrar_pesos_cache(novos_pesos)

    score = sum(NAME_WEIGHTS.get(t, 0.0) for t in tokens)
    pos_hits = sum(1 for t in tokens if NAME_WEIGHTS.get(t, 0.0) > 0)

    if score <= 0:
        return False
    if pos_hits >= 2 and score >= 0.6:
        return True
    if pos_hits >= 1 and score >= 1.1 and len(tokens) <= 4:
        return True
    return False


def detectar_nome(texto: str) -> int:
    """Retorna 1 se houver indicio de nome pessoal no texto, senao 0."""
    if not isinstance(texto, str):
        return 0

    label_match = NAME_LABEL_REGEX.search(texto)
    if label_match and _parece_nome_pessoal(label_match.group(0)):
        return 1
    if INTRO_REGEX.search(texto):
        return 1

    for match in NAME_SEQUENCE_REGEX.finditer(texto):
        if _parece_nome_pessoal(match.group(0)):
            return 1
    return 0


def adicionar_coluna_nome(df: pd.DataFrame) -> pd.DataFrame:
    """Adiciona a coluna binaria 'nome' ao DataFrame."""
    df = df.copy()
    df["nome"] = df["texto_mascarado"].apply(detectar_nome)
    return df


def calcular_metricas(merged: pd.DataFrame) -> dict[str, float]:
    """Calcula metricas basicas a partir de nome_pred e nome_true."""
    tp = ((merged["nome_pred"] == 1) & (merged["nome_true"] == 1)).sum()
    fp = ((merged["nome_pred"] == 1) & (merged["nome_true"] == 0)).sum()
    fn = ((merged["nome_pred"] == 0) & (merged["nome_true"] == 1)).sum()

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

    amostra_com_nome = adicionar_coluna_nome(amostra)
    SAIDA_PATH.parent.mkdir(parents=True, exist_ok=True)
    amostra_com_nome.to_excel(SAIDA_PATH, index=False)

    merged = amostra_com_nome[["id", "nome"]].merge(
        gabarito[["id", "nome"]],
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
