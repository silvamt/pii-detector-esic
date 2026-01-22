# Detector de informacoes pessoais - e-SIC

## Objetivo da solucao

Identificar e marcar informacoes pessoais em planilhas do e-SIC, gerando uma coluna final de sinalizacao (`nao_publico`) e o detector prioritario que motivou a marcacao.

## Visao geral do funcionamento

1. Le o arquivo Excel de entrada.
2. Aplica detectores em ordem definida (email, CPF, telefone, RG, nome).
3. Adiciona uma coluna binaria para cada detector.
4. Define `nao_publico` e `detector_prioritario` com base na primeira correspondencia.
5. Grava uma planilha de saida com as colunas adicionadas.

## Estrutura do repositorio

- `nao_publico.py`: pipeline principal que executa todos os detectores e gera a saida final.
- `detectors/`: scripts de deteccao individual (email, CPF, telefone, RG, nome).
- `data/`: dados auxiliares para o detector de nomes (`nome_weights.csv`).
- `entrada/`: pasta sugerida para arquivos de entrada.
- `saida/`: pasta padrao para arquivos de saida.
- `requirements.txt`: dependencias Python.
- `docs/`: material de apoio (quando aplicavel).

## Pre-requisitos

- Python 3.10 ou superior.
- pip e ambiente virtual (recomendado).
- Acesso a internet apenas se habilitar consultas externas (OpenAI ou Genderize).
- Dependencias listadas em `requirements.txt`.

## Instalacao

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Windows (PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Windows (CMD):

```bat
python -m venv .venv
.\.venv\Scripts\activate.bat
pip install -r requirements.txt
```

## Execucao

Processamento completo (gera `nao_publico` e `detector_prioritario`):

```bash
python nao_publico.py entrada/AMOSTRA.xlsx
```

Saida padrao:
`saida/AMOSTRA_com_nao_publico.xlsx`

Definir arquivo de saida:

```bash
python nao_publico.py entrada/AMOSTRA.xlsx saida/minha_saida.xlsx
```

Recalcular detectores mesmo se as colunas ja existirem:

```bash
python nao_publico.py entrada/AMOSTRA.xlsx --recalcular
```

Executar detectores individuais:

```bash
python detectors/email_detection.py
python detectors/cpf_detection.py
python detectors/telefone_detection.py
python detectors/rg_detection.py
python detectors/nome_detection.py
```

Cada script individual aceita um caminho de entrada opcional e um caminho de saida
opcional:

```bash
python detectors/email_detection.py entrada/AMOSTRA.xlsx saida/minha_saida.xlsx
```

Quando omitidos, os scripts usam `entrada/AMOSTRA.xlsx` e geram um arquivo em
`saida/` com o sufixo `_com_<detector>.xlsx`.

## Entrada e saida

Entrada:

- Arquivo Excel `.xlsx`.
- Colunas obrigatorias: `id` e `texto_mascarado`.
- Se as colunas vierem como `ID` e `Texto Mascarado`, os scripts normalizam os nomes.

Saida:

- Arquivo Excel `.xlsx` com colunas adicionadas por detector.
- Colunas finais: `nao_publico` (0/1) e `detector_prioritario`.
- Padrao de nome: `saida/<arquivo>_com_nao_publico.xlsx` (pipeline completo) ou `saida/<arquivo>_com_<detector>.xlsx` (detector individual).

## Limitacoes conhecidas

- Entrada restrita a arquivos `.xlsx` com as colunas especificadas.
- Heuristicas de nomes foram desenhadas para lingua portuguesa e podem gerar falsos positivos/negativos.
- Consultas externas (OpenAI/Genderize) sao opcionais e exigem credenciais; sem elas, o detector de nomes opera apenas com pesos locais.
- O pipeline prioriza o primeiro detector positivo na ordem configurada e nao agrega confidencia entre detectores.

## Variaveis de ambiente (opcionais)

Deteccao de nomes (consultas externas desligadas por padrao):

- `NOME_OPENAI_LOOKUP=1` habilita consulta a API OpenAI para tokens desconhecidos.
- `OPENAI_API_KEY` chave de API da OpenAI.
- `NOME_OPENAI_MODEL` (padrao `gpt-4o-mini`) define o modelo OpenAI.
- `NOME_GENDERIZE=1` habilita consultas ao Genderize.io.
- `GENDERIZE_API_KEY` chave do Genderize.io (necessaria quando habilitado).

Ajustes de thresholds do detector de nomes:

- `NOME_SCORE_MIN` (padrao `0.6`)
- `NOME_SCORE_MIN_SINGLE` (padrao `1.1`)
- `NOME_MAX_TOKENS_SINGLE` (padrao `4`)
- `NOME_MAX_TOKENS_FALLBACK` (padrao `4`)
