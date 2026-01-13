# 🔒 Detector de Informações Pessoais - e-SIC

> **Identifique automaticamente dados sensíveis em documentos públicos**

Ferramenta que detecta e protege informações pessoais em planilhas Excel, garantindo conformidade com **LGPD** e **Lei de Acesso à Informação**.

## ✨ O que faz

Detecta automaticamente:
- 📧 **E-mails**
- 🆔 **CPF** e **RG**
- 📱 **Telefones**
- 👤 **Nomes próprios** (com IA)

Marca linhas com dados sensíveis e gera relatório estruturado.

## 🎯 Por que usar

- ⚖️ Conformidade com LGPD artigo 18 (direito ao esquecimento)
- 🚀 Processamento em batch de documentos
- 🎯 Detecção com priorização inteligente
- 📊 Resultados verificáveis com gabarito

## 📋 Requisitos

- Python 3.10+
- Planilha Excel (ou CSV)

**Opcional:** Chave OpenAI para detecção de nomes com IA

## ⚡ Quick Start (macOS/Linux)

```bash
# Clone e configure
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Execute
python nao_publico.py entrada/AMOSTRA.xlsx
```
🚀 Como usar

### 1️⃣ Processamento completo
```bash
python nao_publico.py entrada/AMOSTRA.xlsx
```
Gera: `saida/AMOSTRA_com_nao_publico.xlsx` com coluna `nao_publico` (0 ou 1)

### 2️⃣ Validar contra gabarito
```bash
python avaliar_nao_publico.py saida/AMOSTRA_com_nao_publico.xlsx
```
Compara resultados com `entrada/gabarito.json` e mostra acurácia

### 3️⃣ Testar detectores individuais
```bash
python scripts/email_detection.py
python scripts/cpf_detection.py
python scripts/telefone_detection.py
python scripts/rg_detection.py
python scripts/nome_detection.py
```

### 4️⃣ Rodar suite de testespython scripts/telefone_detection.py
python scripts/rg_detection.py
python scripts/nome_detection.py
```

### Rodar testes automáticos

```bash
python -m unittest tests/test_detectores.py
```

## Como funciona

- O🔍 Como funciona

```
Entrada (Excel)
    ↓
[Email] → [CPF] → [Telefone] → [RG] → [Nome]
    ↓ (prioridade cascata)
Encontrou? Marca 1 e passa
    ↓
Saída (Excel + coluna nao_publico)
```

**Lógica de priorização:** Para cada célula, testa detectores em ordem até encontrar correspondência.

## 📁 Estrutura do projeto

```
pii-detector-esic/
├── nao_publico.py           # Motor principal
├── avaliar_nao_publico.py   # Validação
├── entrada/                 # Suas planilhas
├── saida/                   # Resultados
├── scripts/                 # Detectores (email, cpf, telefone, rg, nome)
├── data/                    # Weights e dados auxiliares
└── tests/                   # Suite de testes
```

## 🤖 Detecção de Nomes com OpenAI

Melhora precisão de nomes não conhecidos usando IA:

```bash
# Método 1: Variáveis de ambiente
export NOME_OPENAI_LOOKUP=1
export OPENAI_API_KEY="sk-proj-..."
python scripts/nome_detection.py

# Método 2: Um só comando
NOME_OPENAI_LOOKUP=1 OPENAI_API_KEY="sk-proj-..." python scripts/nome_detection.py

# Método 3: Permanente (~/.zshrc ou ~/.bashrc)
export NOME_OPENAI_LOOKUP=1
export OPENAI_API_KEY="sk-proj-..."
```

**Cache automático:** Pesos são salvos em `data/nome_weights.csv` e reutilizados (sem chamadas API duplicadas)