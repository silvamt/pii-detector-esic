import sys
import unittest
from pathlib import Path

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT_DIR / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from cpf_detection import adicionar_coluna_cpf, detectar_cpf
from email_detection import adicionar_coluna_email, detectar_email
from nome_detection import adicionar_coluna_nome, detectar_nome
from rg_detection import adicionar_coluna_rg, detectar_rg
from telefone_detection import adicionar_coluna_telefone, detectar_telefone


class TestDetectoresSinteticos(unittest.TestCase):
    def test_email_detecta_endereco_basico(self):
        self.assertEqual(detectar_email("Contato: maria@example.com"), 1)

    def test_email_detecta_com_ponto_final(self):
        self.assertEqual(
            detectar_email("Favor responder para joao.silva@empresa.com.br."), 1
        )

    def test_email_detecta_subdominio_e_maiusculas(self):
        self.assertEqual(detectar_email("Envie para SUPORTE@mail.gov.br"), 1)

    def test_email_rejeita_endereco_incompleto(self):
        self.assertEqual(detectar_email("Fale comigo em maria@example"), 0)
        self.assertEqual(detectar_email("E-mail: joao @ exemplo . com"), 0)

    def test_cpf_com_rotulo_ou_formato(self):
        self.assertEqual(detectar_cpf("CPF: 123.456.789-09"), 1)
        self.assertEqual(detectar_cpf("Doc 123.456.789-09"), 1)

    def test_cpf_com_rotulo_e_hifen(self):
        self.assertEqual(detectar_cpf("CPF-123.456.789-09"), 1)

    def test_cpf_com_rotulo_e_digitos_crus(self):
        self.assertEqual(detectar_cpf("CPF 12345678909"), 1)

    def test_cpf_rejeita_digitos_sem_formato_e_sem_rotulo(self):
        self.assertEqual(detectar_cpf("Protocolo 12345678901"), 0)
        self.assertEqual(detectar_cpf("Documento 00000000000"), 0)

    def test_telefone_com_ddd_e_nove_digitos(self):
        self.assertEqual(detectar_telefone("Me ligue no (11) 98765-4321"), 1)

    def test_telefone_com_ddd_e_oito_digitos(self):
        self.assertEqual(detectar_telefone("Contato (61) 3456-7890"), 1)

    def test_telefone_compacto_com_ddd(self):
        self.assertEqual(detectar_telefone("(21)912345678"), 1)

    def test_telefone_rejeita_sem_ddd_ou_0800(self):
        self.assertEqual(detectar_telefone("Telefone: 98765-4321"), 0)
        self.assertEqual(detectar_telefone("0800 123 456"), 0)
        self.assertEqual(detectar_telefone("Tel: 12345-6789"), 0)
        self.assertEqual(detectar_telefone("(00) 91234-5678"), 0)

    def test_rg_padroes_mais_comuns(self):
        self.assertEqual(detectar_rg("Documento RG 12.345.678-9"), 1)
        self.assertEqual(detectar_rg("OAB/DF 12345"), 1)
        self.assertEqual(detectar_rg("Matricula 1234-5/2020"), 1)
        self.assertEqual(detectar_rg("NIS 12345678901"), 1)
        self.assertEqual(detectar_rg("Registro 21-1205-1999"), 1)

    def test_rg_rejeita_numero_aleatorio(self):
        self.assertEqual(detectar_rg("Protocolo interno 98765-432"), 0)
        self.assertEqual(detectar_rg("Codigo 2112051999"), 0)

    def test_nome_intro_e_assinatura(self):
        self.assertEqual(detectar_nome("Meu nome e Joao da Silva"), 1)
        self.assertEqual(detectar_nome("Atenciosamente, Maria Oliveira"), 1)
        self.assertEqual(detectar_nome("Sou Carlos Henrique de Souza"), 1)
        self.assertEqual(detectar_nome("Assinado: Pedro de Almeida e Costa"), 1)

    def test_nome_rejeita_orgao_ou_assunto(self):
        self.assertEqual(
            detectar_nome("Solicito informacoes sobre o processo 12345/2023"), 0
        )
        self.assertEqual(detectar_nome("Numero do protocolo 2023-000123"), 0)
        self.assertEqual(detectar_nome("Lei Maria da Penha atualizada"), 0)

    def test_nao_confunde_cns_com_outros_detectores(self):
        texto = "Cartao SUS (CNS) 898001160220176"
        self.assertEqual(detectar_cpf(texto), 0)
        self.assertEqual(detectar_telefone(texto), 0)
        self.assertEqual(detectar_rg(texto), 0)

    def test_nao_confunde_placa_de_veiculo(self):
        texto = "Veiculo placa ABC1D23 estacionado"
        self.assertEqual(detectar_cpf(texto), 0)
        self.assertEqual(detectar_telefone(texto), 0)
        self.assertEqual(detectar_rg(texto), 0)
        self.assertEqual(detectar_nome(texto), 0)

    def test_nao_confunde_cep(self):
        texto = "CEP 01310-000 Sao Paulo SP"
        self.assertEqual(detectar_cpf(texto), 0)
        self.assertEqual(detectar_telefone(texto), 0)
        self.assertEqual(detectar_rg(texto), 0)

    def test_adiciona_colunas_em_dataframe_sintetico(self):
        df = pd.DataFrame(
            [
                {"id": 1, "texto_mascarado": "Email: a@b.com"},
                {"id": 2, "texto_mascarado": "CPF: 123.456.789-09"},
                {"id": 3, "texto_mascarado": "Telefone (11) 98765-4321"},
                {"id": 4, "texto_mascarado": "OAB/DF 12345"},
                {"id": 5, "texto_mascarado": "Meu nome e Ana Carla Dias"},
                {
                    "id": 6,
                    "texto_mascarado": "Dados para contato: CPF 98765432100, email x@y.com",
                },
            ]
        )

        df = adicionar_coluna_email(df)
        df = adicionar_coluna_cpf(df)
        df = adicionar_coluna_telefone(df)
        df = adicionar_coluna_rg(df)
        df = adicionar_coluna_nome(df)

        self.assertListEqual(df["email"].tolist(), [1, 0, 0, 0, 0, 1])
        self.assertListEqual(df["cpf"].tolist(), [0, 1, 0, 0, 0, 1])
        self.assertListEqual(df["telefone"].tolist(), [0, 0, 1, 0, 0, 0])
        self.assertListEqual(df["rg"].tolist(), [0, 0, 0, 1, 0, 0])
        self.assertListEqual(df["nome"].tolist(), [0, 0, 0, 0, 1, 0])


if __name__ == "__main__":
    unittest.main()
