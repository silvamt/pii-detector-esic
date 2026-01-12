# Classificador de Acesso à Informação - Desafio Participa DF

## 1. Objetivo
Este repositório implementa um classificador automático para identificar se um pedido de acesso à informação contém dados pessoais e, portanto, deve ser classificado como **não público**.

## 2. Definição de “dados pessoais” (conforme edital)
Para fins deste projeto, consideram-se **apenas**:

- Nome
- CPF
- RG
- Telefone
- Endereço de e-mail

## 3. Pré-requisitos
- Python 3.11+
- `pip` e `venv`

## 4. Instalação via pip + venv
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

## 5. Execução (CSV e Excel)
CSV:
```bash
python -m pii_detector.cli --input data/AMOSTRA.csv --output data/AMOSTRA_classificado.csv
```

Excel:
```bash
python -m pii_detector.cli --input data/AMOSTRA.xlsx --output data/AMOSTRA_classificado.xlsx
```

## 6. Regra de equivalência de formato
O arquivo de saída **sempre** mantém o mesmo formato do arquivo de entrada:

- Entrada `.xlsx` → Saída `.xlsx`
- Entrada `.csv` → Saída `.csv`

Se `--output` não for informado, será gerado no mesmo diretório com sufixo `_classificado`.

## 7. Pipeline e curto-circuito
1. **Fragmentação** em janelas de 30–40 palavras, com overlap de 10–15 palavras.
2. **Detectores fortes** (curto-circuito por fragmento, nesta ordem):
   - CPF (regex + validação)
   - E-mail (regex padrão)
   - Telefone (regex estrita com DDD/+55 ou marcador)
   - CEP / endereço forte
   - RG (apenas com marcador explícito)
3. **Casos difíceis** (somente se nenhum forte disparar):
   - Nome (heurísticas leves)
   - Endereço fraco (heurísticas leves)

Se qualquer detector forte disparar em qualquer fragmento, o processamento da observação é encerrado imediatamente.

## 8. LLM opcional e cache
Para casos ambíguos, é possível habilitar o LLM (OpenAI) com cache persistente:

```bash
export OPENAI_API_KEY="sua-chave"
python -m pii_detector.cli --input data/AMOSTRA.csv --llm openai --cache cache.json --evidence evidence.jsonl
```

- `--llm none|openai` (default: none)
- Cache em JSON com chave `sha256` do texto normalizado
- O LLM só é chamado quando não há detecção forte nem heurística suficiente

## 9. Licença
Este projeto é distribuído sob licença MIT. Também inclui a **cessão de direitos** conforme exigido pelo edital do Desafio Participa DF.

Veja `LICENSE` para detalhes.
