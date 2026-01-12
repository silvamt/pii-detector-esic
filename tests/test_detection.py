import unittest

from pii_detector.detection import analyze_text


class DetectionTests(unittest.TestCase):
    def test_detects_cpf(self):
        text = "Meu CPF é 529.982.247-25 para cadastro."
        result = analyze_text(text)
        self.assertEqual(result.flags["cpf"], 1)
        self.assertEqual(result.flags["nao_publico"], 1)

    def test_detects_email(self):
        text = "Contato: exemplo@dominio.com"
        result = analyze_text(text)
        self.assertEqual(result.flags["email"], 1)

    def test_no_pii(self):
        text = "Solicito informações sobre contratos públicos."
        result = analyze_text(text)
        self.assertEqual(result.flags["nao_publico"], 0)


if __name__ == "__main__":
    unittest.main()
