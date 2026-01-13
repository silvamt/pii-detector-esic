from urllib.request import urlopen
import ssl
import certifi
from openpyxl import Workbook

url = "https://raw.githubusercontent.com/peluz/lener-br/refs/heads/master/leNER-Br/train/train.conll"
output_path = "sentencas.xlsx"

wb = Workbook()
ws = wb.active
ws.title = "dados"
ws.append(["id", "texto"])

sentenca_tokens = []
sentenca_id = 1

# Usa cadeia de certificados atualizada do certifi para evitar erros de SSL.
ssl_ctx = ssl.create_default_context(cafile=certifi.where())

with urlopen(url, context=ssl_ctx) as response:
    for raw_line in response:
        line = raw_line.decode("utf-8").strip()

        # Linha em branco = fim da sentença
        if not line:
            if sentenca_tokens:
                texto = " ".join(sentenca_tokens)
                ws.append([sentenca_id, texto])
                sentenca_id += 1
                sentenca_tokens = []
            continue

        token = line.split()[0]
        sentenca_tokens.append(token)

# Caso o arquivo não termine com linha em branco
if sentenca_tokens:
    texto = " ".join(sentenca_tokens)
    ws.append([sentenca_id, texto])

wb.save(output_path)

print(f"Arquivo gerado: {output_path}")
