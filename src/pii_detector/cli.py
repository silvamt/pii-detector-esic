"""Command line interface for PII detector."""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

from .cache import JsonCache
from .detection import DetectionResult, analyze_text
from .io_utils import InputError, read_csv, read_xlsx, write_csv, write_xlsx
from .llm import MODEL_VERSION, PROMPT_VERSION, call_openai

OUTPUT_COLUMNS = ["ID", "nao_publico", "cpf", "email", "telefone", "endereco", "rg", "nome"]


def _build_output_row(row: Dict[str, str], flags: Dict[str, int]) -> Dict[str, str]:
    output = dict(row)
    for key in OUTPUT_COLUMNS:
        if key == "ID":
            output[key] = str(row.get("ID", ""))
        elif key in flags:
            output[key] = int(flags[key])
    return output


def _merge_llm(flags: Dict[str, int], llm_payload: Dict[str, object]) -> DetectionResult:
    evidence = list(llm_payload.get("evidence", []))
    contains_pii = bool(llm_payload.get("contains_pii"))
    if not contains_pii or not evidence:
        flags["nao_publico"] = 0
        return DetectionResult(flags=flags, evidence=[])

    type_map = {
        "cpf": "cpf",
        "email": "email",
        "rg": "rg",
        "phone": "telefone",
        "name": "nome",
    }
    for pii_type in llm_payload.get("pii_types", []):
        mapped = type_map.get(str(pii_type))
        if mapped:
            flags[mapped] = 1
    for item in evidence:
        mapped = type_map.get(str(item.get("type", "")).lower())
        if mapped:
            flags[mapped] = 1
    flags["nao_publico"] = 1 if any(flags[key] for key in type_map.values()) else 0
    return DetectionResult(flags=flags, evidence=evidence, used_llm=True)


def classify_rows(
    rows: List[Dict[str, str]],
    llm_mode: str,
    cache: Optional[JsonCache],
    max_rows: Optional[int],
    evidence_path: Optional[Path],
) -> List[Dict[str, str]]:
    output_rows: List[Dict[str, str]] = []
    evidence_handle = None
    if evidence_path:
        evidence_handle = evidence_path.open("w", encoding="utf-8")

    try:
        for idx, row in enumerate(rows):
            if max_rows is not None and idx >= max_rows:
                flags = {\"cpf\": 0, \"email\": 0, \"telefone\": 0, \"endereco\": 0, \"rg\": 0, \"nome\": 0, \"nao_publico\": 0}
                output_rows.append(_build_output_row(row, flags))
                continue
            text = row.get("Texto Mascarado", "")
            flags = {"cpf": 0, "email": 0, "telefone": 0, "endereco": 0, "rg": 0, "nome": 0, "nao_publico": 0}
            result = analyze_text(text)
            flags.update(result.flags)
            evidence = list(result.evidence)

            if flags["nao_publico"] == 0 and llm_mode == "openai":
                cached = cache.get(text) if cache else None
                if cached:
                    result = _merge_llm(flags, cached.payload)
                    flags.update(result.flags)
                    evidence = list(result.evidence)
                else:
                    llm_result = call_openai(text)
                    payload = {
                        "contains_pii": llm_result.contains_pii,
                        "pii_types": llm_result.pii_types,
                        "evidence": llm_result.evidence,
                        "confidence": llm_result.confidence,
                        "model_version": MODEL_VERSION,
                        "prompt_version": PROMPT_VERSION,
                    }
                    if cache:
                        cache.set(text, payload)
                    result = _merge_llm(flags, payload)
                    flags.update(result.flags)
                    evidence = list(result.evidence)

            output_rows.append(_build_output_row(row, flags))

            if evidence_handle:
                record = {
                    "id": row.get("ID", ""),
                    "nao_publico": flags["nao_publico"],
                    "flags": {key: flags[key] for key in ["cpf", "email", "telefone", "endereco", "rg", "nome"]},
                    "evidence": evidence,
                }
                evidence_handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    finally:
        if evidence_handle:
            evidence_handle.close()

    return output_rows


def build_output_path(input_path: Path, output_path: Optional[Path]) -> Path:
    if output_path:
        return output_path
    return input_path.with_name(f"{input_path.stem}_classificado{input_path.suffix}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Classificador de dados pessoais para pedidos de acesso à informação.")
    parser.add_argument("--input", required=True, help="Arquivo de entrada (.csv ou .xlsx)")
    parser.add_argument("--output", help="Arquivo de saída (mesma extensão do input)")
    parser.add_argument("--llm", choices=["none", "openai"], default="none", help="Habilitar LLM opcional")
    parser.add_argument("--cache", default="cache.json", help="Arquivo de cache JSON")
    parser.add_argument("--evidence", help="Arquivo JSONL para evidências")
    parser.add_argument("--max-rows", type=int, help="Número máximo de linhas")
    parser.add_argument("--verbose", action="store_true", help="Logs verbosos")

    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING, format="%(message)s")

    input_path = Path(args.input)
    output_path = build_output_path(input_path, Path(args.output) if args.output else None)

    try:
        if input_path.suffix.lower() not in {".csv", ".xlsx"}:
            raise InputError("Formato inválido: use .csv ou .xlsx")
        if output_path.suffix.lower() != input_path.suffix.lower():
            raise InputError("A saída deve ter a mesma extensão do arquivo de entrada")

        cache = JsonCache(Path(args.cache)) if args.llm == "openai" else None
        evidence_path = Path(args.evidence) if args.evidence else None

        if input_path.suffix.lower() == ".csv":
            data = read_csv(input_path)
            output_rows = classify_rows(data.rows, args.llm, cache, args.max_rows, evidence_path)
            write_csv(output_path, data, output_rows, OUTPUT_COLUMNS)
        else:
            data = read_xlsx(input_path)
            output_rows = classify_rows(data.rows, args.llm, cache, args.max_rows, evidence_path)
            write_xlsx(output_path, data, output_rows, OUTPUT_COLUMNS)

        if cache:
            cache.save()

        logging.info("Arquivo de saída gerado em %s", output_path)
        return 0
    except InputError as exc:
        logging.error(str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
