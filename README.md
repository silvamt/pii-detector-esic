# Detector de Informações Pessoais - e-SIC

Este programa identifica informações pessoais em planilhas Excel, como e-mail, CPF, telefone, RG e nome.

## O que você precisa

- Python 3.10 ou mais novo
- Uma planilha Excel com os dados (exemplo: `entrada/AMOSTRA.xlsx`)

## Como instalar

1. Abra o terminal na pasta do projeto
2. Digite os comandos abaixo:

```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

## Como usar

### Detectar informações pessoais na planilha

```bash
python nao_publico.py entrada/AMOSTRA.xlsx
```

O programa cria uma nova planilha na pasta `saida` com uma coluna mostrando quais linhas têm informações pessoais.

### Ver se o resultado está correto

```bash
python avaliar_nao_publico.py saida/AMOSTRA_com_nao_publico.xlsx
```

Isso compara o resultado com o gabarito e mostra se está acertando.

### Testar apenas um tipo de informação

Você pode testar cada detector separadamente:

```bash
python scripts/email_detection.py
python scripts/cpf_detection.py
python scripts/telefone_detection.py
python scripts/rg_detection.py
python scripts/nome_detection.py
```

### Rodar testes automáticos

```bash
python -m unittest tests/test_detectores.py
```

## Como funciona

- O programa lê uma planilha Excel
- Procura por e-mails, CPFs, telefones, RGs e nomes
- Marca as linhas que têm essas informações
- Cria uma nova planilha com os resultados

## Organização dos arquivos

- `entrada/` - coloque suas planilhas aqui
- `saida/` - os resultados aparecem aqui
- `scripts/` - programas que fazem cada tipo de detecção
- `data/` - dados auxiliares do programa
- `tests/` - testes automáticos

## Recurso extra: OpenAI para nomes

O detector de nomes pode usar inteligência artificial para melhorar. Para isso:

1. Configure a variável `OPENAI_API_KEY` com sua chave
2. Configure `NOME_OPENAI_LOOKUP=1`

Sem essas configurações, o programa funciona normalmente mas só com as regras básicas.
