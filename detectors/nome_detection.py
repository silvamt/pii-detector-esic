"""
Detecta mencoes a nomes de pessoas em `entrada/AMOSTRA.xlsx` e salva o resultado em
`saida/`.

Estrategia:
- Usa pesos precomputados de tokens (`data/nome_weights.csv`) aprendidos fora do
  conjunto de controle para priorizar sequencias que parecam nomes, mesmo sem
  depender de capitalizacao.
- Pesos negativos penalizam termos institucionais/assunto (ex.: edital,
  protocolo, concurso), reduzindo falsos positivos.
- Mantem pistas simples ("meu nome e", "me chamo", assinaturas) para ampliar a
  cobertura.

Uso:
    python nome_detection.py
"""

from __future__ import annotations

import json
import os
import re
import unicodedata
from pathlib import Path
import sys

import pandas as pd

from utils_io import carregar_amostra

BASE_DIR = Path(__file__).resolve().parent.parent
ENTRADA_DIR = BASE_DIR / "entrada"
SAIDA_DIR = BASE_DIR / "saida"
DATA_DIR = BASE_DIR / "data"
AMOSTRA_PATH = ENTRADA_DIR / "AMOSTRA.xlsx"
SAIDA_PATH = SAIDA_DIR / "AMOSTRA_com_nome.xlsx"
PESOS_CACHE_PATH = DATA_DIR / "nome_weights.csv"
OPENAI_MODEL = os.getenv("NOME_OPENAI_MODEL", "gpt-4o-mini")
OPENAI_LOOKUP_ENABLED = os.getenv("NOME_OPENAI_LOOKUP", "0").lower() in {
    "1",
    "true",
    "yes",
    "on",
}
GENDERIZE_ENABLED = os.getenv("NOME_GENDERIZE", "0").lower() in {"1", "true", "yes", "on"}
GENDERIZE_API_KEY = os.getenv("GENDERIZE_API_KEY")
NAME_SCORE_MIN = float(os.getenv("NOME_SCORE_MIN", "0.6"))
NAME_SCORE_MIN_SINGLE = float(os.getenv("NOME_SCORE_MIN_SINGLE", "1.1"))
NAME_MAX_TOKENS_SINGLE = int(os.getenv("NOME_MAX_TOKENS_SINGLE", "4"))
NAME_MAX_TOKENS_FALLBACK = int(os.getenv("NOME_MAX_TOKENS_FALLBACK", "4"))

# Regex para tokens que lembram nomes (suporta acentos e qualquer capitalizacao).
NAME_TOKEN = r"[A-Za-zÀ-ÖØ-öø-ÿ][A-Za-zÀ-ÖØ-öø-ÿ'-]{1,}"
CONNECTOR = r"(?:da|de|do|dos|das|e)"
NAME_SEQUENCE_REGEX = re.compile(
    rf"\b{NAME_TOKEN}(?:\s+(?:{CONNECTOR}\s+)?{NAME_TOKEN})+\b",
    flags=re.IGNORECASE,
)
NAME_LABEL_REGEX = re.compile(
    rf"(?i)\bnome(?:\s+completo)?\s*[:\-]?\s*{NAME_TOKEN}(?:\s+(?:{CONNECTOR}\s+)?{NAME_TOKEN})*"
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
    "departamento",
    "diretoria",
    "coordenacao",
    "ministerio",
    "instituto",
    "universidade",
    "hospital",
    "escola",
    "bairro",
    "rua",
    "avenida",
    "setor",
}
FALLBACK_NEG_WEIGHT = -0.6

NAME_WEIGHTS: dict[str, float] | None = None
_OPENAI_CLIENT = None
_GENDER_DETECTORS = None
EXTERNAL_LOOKUP_USED = False
EXTERNAL_LOOKUP_SOURCES: set[str] = set()

GENDER_NAME_WEIGHT = 1.2


def _mark_external_lookup(source: str) -> None:
    """Registra e anuncia uso de consulta externa (rede)."""
    global EXTERNAL_LOOKUP_USED
    if source in EXTERNAL_LOOKUP_SOURCES:
        return
    EXTERNAL_LOOKUP_SOURCES.add(source)
    EXTERNAL_LOOKUP_USED = True
    print(
        f"Aviso: consulta externa habilitada ({source}); garanta uso apenas com dados sintéticos."
    )


def _norm(token: str) -> str:
    """Converte para minusculas e remove acentos para comparacao estavel."""
    decomposed = unicodedata.normalize("NFD", token.lower())
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


CONNECTOR_WORDS_NORM = {_norm(w) for w in CONNECTOR_WORDS}
FALLBACK_NEG_TOKENS_NORM = {_norm(w) for w in FALLBACK_NEG_TOKENS}


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


def _carregar_detectores_genero():
    """Carrega detectores de genero de bibliotecas opcionais."""
    global _GENDER_DETECTORS
    if _GENDER_DETECTORS is not None:
        return _GENDER_DETECTORS

    detectores = []

    try:
        from gender_guesser.detector import Detector

        detector = Detector(case_sensitive=False)

        def _gg(nome: str) -> bool:
            genero = detector.get_gender(nome)
            return genero not in {"unknown", "andy"}

        detectores.append(_gg)
    except Exception:
        pass

    try:
        import gender_guesser_br

        def _gg_br(nome: str) -> bool:
            try:
                genero = gender_guesser_br.get_gender(nome)
            except Exception:
                return False
            return genero not in {"unknown", "andy"}

        detectores.append(_gg_br)
    except Exception:
        pass

    try:
        from gender_detector import GenderDetector

        detector = GenderDetector()

        def _gd(nome: str) -> bool:
            try:
                genero = detector.guess(nome)
            except Exception:
                return False
            return genero not in {"unknown", "andy", None}

        detectores.append(_gd)
    except Exception:
        pass

    _GENDER_DETECTORS = detectores
    return _GENDER_DETECTORS


def _consultar_bibliotecas_genero(tokens: list[str]) -> dict[str, float]:
    """Retorna pesos positivos para tokens reconhecidos como nomes."""
    detectores = _carregar_detectores_genero()
    if not detectores:
        return {}

    encontrados: dict[str, float] = {}
    for token in tokens:
        for detector in detectores:
            try:
                if detector(token):
                    encontrados[_norm(token)] = GENDER_NAME_WEIGHT
                    break
            except Exception:
                continue
    return encontrados


def _consultar_genderize(tokens: list[str]) -> dict[str, float]:
    """Consulta Genderize.io para identificar nomes (exige chave e habilitacao)."""
    if not GENDERIZE_ENABLED or not GENDERIZE_API_KEY:
        return {}
    try:
        import requests
    except Exception as exc:
        print(f"Aviso: pacote requests indisponivel ({exc}); sem Genderize.")
        return {}

    nomes_unicos = []
    vistos = set()
    for token in tokens:
        low = _norm(token)
        if low in vistos:
            continue
        vistos.add(low)
        nomes_unicos.append(token)

    if not nomes_unicos:
        return {}

    _mark_external_lookup("Genderize.io")
    encontrados: dict[str, float] = {}
    for nome in nomes_unicos:
        try:
            resp = requests.get(
                "https://api.genderize.io",
                params={"name": nome, "apikey": GENDERIZE_API_KEY},
                timeout=5,
            )
            if resp.status_code != 200:
                continue
            data = resp.json()
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        if data.get("gender") in {"male", "female"} and data.get("probability", 0) >= 0.6:
            encontrados[_norm(nome)] = GENDER_NAME_WEIGHT
    return encontrados


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

    _mark_external_lookup("OpenAI")

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
            response_format={"type": "json_object"},
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
        preview = content
        if len(preview) > 120:
            preview = preview[:117] + "..."
        print(f"Aviso: resposta OpenAI sem JSON valido; ignorando. Trecho: {preview}")
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
    # Mantem cache append-only para evitar reavaliar tokens ja conhecidos.
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
    tokens_originais = []
    for t in re.findall(NAME_TOKEN, fragmento):
        low = _norm(t)
        if low in CONNECTOR_WORDS_NORM:
            continue
        tokens_originais.append(t)
        tokens.append(low)

    if len(tokens) < 2:
        return False
    if tokens and tokens[0] == "lei":
        return False

    unknown_tokens = [t for t in tokens if t not in NAME_WEIGHTS]
    if unknown_tokens:
        # Prioriza fontes locais/low-cost para reduzir falsos negativos.
        unknown_tokens_raw = [
            raw
            for raw, norm in zip(tokens_originais, tokens)
            if norm in unknown_tokens
        ]
        novos_pesos = _consultar_bibliotecas_genero(unknown_tokens_raw)
        if novos_pesos:
            NAME_WEIGHTS.update(novos_pesos)
            _registrar_pesos_cache(novos_pesos)
            return True

        novos_pesos = _consultar_genderize(unknown_tokens_raw)
        if novos_pesos:
            NAME_WEIGHTS.update(novos_pesos)
            _registrar_pesos_cache(novos_pesos)
            return True

    if not NAME_WEIGHTS:
        if any(t in FALLBACK_NEG_TOKENS_NORM for t in tokens):
            return False
        # Sem pesos, mantem heuristica permissiva apenas para poucos tokens.
        return len(tokens) <= NAME_MAX_TOKENS_FALLBACK

    if unknown_tokens:
        novos_pesos = _consultar_openai_tokens(fragmento, unknown_tokens)
        if novos_pesos:
            NAME_WEIGHTS.update(novos_pesos)
            _registrar_pesos_cache(novos_pesos)

    score = sum(NAME_WEIGHTS.get(t, 0.0) for t in tokens)
    pos_hits = sum(1 for t in tokens if NAME_WEIGHTS.get(t, 0.0) > 0)

    if score <= 0:
        return False
    # Exige consenso em pelo menos dois tokens ou um token muito forte.
    if pos_hits >= 2 and score >= NAME_SCORE_MIN:
        return True
    if pos_hits >= 1 and score >= NAME_SCORE_MIN_SINGLE and len(tokens) <= NAME_MAX_TOKENS_SINGLE:
        return True
    return False


def _parece_nome_pessoal_single(fragmento: str) -> bool:
    """Heuristica para nomes unitarios quando ha rotulo explicito."""
    global NAME_WEIGHTS
    if NAME_WEIGHTS is None:
        NAME_WEIGHTS = carregar_pesos_nomes()

    tokens = [_norm(t) for t in re.findall(NAME_TOKEN, fragmento)]
    tokens = [t for t in tokens if t not in CONNECTOR_WORDS_NORM]
    if len(tokens) != 1:
        return False
    token = tokens[0]
    if token in FALLBACK_NEG_TOKENS_NORM:
        return False
    weight = NAME_WEIGHTS.get(token)
    if weight is None:
        return len(token) >= 3
    return weight > 0


def detectar_nome(texto: str) -> int:
    """Retorna 1 se houver indicio de nome pessoal no texto, senao 0."""
    if not isinstance(texto, str):
        return 0

    label_match = NAME_LABEL_REGEX.search(texto)
    if label_match and (
        _parece_nome_pessoal(label_match.group(0))
        or _parece_nome_pessoal_single(label_match.group(0))
    ):
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
        raise SystemExit("Uso: python nome_detection.py [amostra.xlsx] [saida.xlsx]")
    if len(argv) >= 1:
        amostra_path = _resolve_input_path(argv[0])
    else:
        amostra_path = AMOSTRA_PATH

    if len(argv) == 2:
        saida_path = _resolve_output_path(argv[1])
    else:
        saida_path = SAIDA_DIR / f"{Path(amostra_path).stem}_com_nome.xlsx"
    return amostra_path, saida_path


def main() -> None:
    try:
        amostra_path, saida_path = _parse_cli_paths(sys.argv[1:])
        amostra = carregar_amostra(amostra_path)
        amostra_com_nome = adicionar_coluna_nome(amostra)
        saida_path.parent.mkdir(parents=True, exist_ok=True)
        amostra_com_nome.to_excel(saida_path, index=False)
        if EXTERNAL_LOOKUP_USED:
            print(
                f"Consultas externas usadas: {', '.join(sorted(EXTERNAL_LOOKUP_SOURCES))}"
            )
        print(f"Arquivo salvo em: {saida_path}")
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        print(f"Erro: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
