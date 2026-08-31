import math
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from personal_inflation import (
    MAX_JUMP,
    build_product_id,
    chain_index_series,
    compute_monthly_product_stats,
    parse_number,
    parse_receipts,
    spread_monthly_log_change,
)

NFE_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe">
 <NFe><infNFe Id="NFe{key}" versao="4.00">
  <ide><dhEmi>{dh}</dhEmi></ide>
  <emit><CNPJ>12345678000199</CNPJ><xNome>LOJA TESTE</xNome></emit>
  <det nItem="1"><prod>
   <xProd>ARROZ 5KG</xProd><cEAN>7890000000001</cEAN><NCM>10063021</NCM>
   <qCom>1.0000</qCom><uCom>UN</uCom><vUnCom>{price}</vUnCom><vProd>{price}</vProd>
  </prod></det>
  <total><ICMSTot><vNF>{price}</vNF></ICMSTot></total>
 </infNFe></NFe>
</nfeProc>"""


def _write_note(folder, key, dh, price):
    path = os.path.join(folder, f"NFCE_{key}_20260101000000.xml")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(NFE_TEMPLATE.format(key=key, dh=dh, price=f"{price:.2f}"))


def _write_cancel(folder, key):
    path = os.path.join(folder, f"CANC_110111_NFCE_{key}_20260101000000.xml")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("<x/>")


class PersonalInflationMethodologyTests(unittest.TestCase):
    def test_product_identity_prefers_valid_ean(self):
        product_id = build_product_id("08189400000107", "LARANJA PERA KG", "00000000003261")
        self.assertEqual(product_id, "EAN:3261")

    def test_product_identity_falls_back_for_invalid_ean(self):
        product_id = build_product_id("35128392000153", "PIZZA GRANDE (8 FATIAS)", "ABC123")
        self.assertEqual(product_id, "DSC:35128392:PIZZA GRANDE 8 FATIAS")

    def test_parse_brazilian_number(self):
        validation = {"missing_numeric_fields": 0, "malformed_numeric_fields": 0}
        self.assertAlmostEqual(parse_number("1.104,98", validation, "total", "t"), 1104.98)
        self.assertAlmostEqual(parse_number("89,99", validation, "unit", "t"), 89.99)

    def test_unit_mismatch_is_prevented_by_grouping_key(self):
        same_product = build_product_id("08414996000274", "CENOURA kg", "SEM GTIN")
        self.assertNotEqual((same_product, "KG"), (same_product, "UN"))

    def test_monthly_median_price_logic(self):
        monthly = compute_monthly_product_stats(
            [
                (0, 10.0, 10.0),
                (0, 14.0, 14.0),
                (0, 12.0, 12.0),
                (1, 20.0, 20.0),
            ]
        )
        self.assertEqual(monthly[0], (12.0, 36.0))
        self.assertEqual(monthly[1], (20.0, 20.0))

    def test_gap_spread_log_return_logic(self):
        spread = spread_monthly_log_change(0, 10.0, 3, 20.0)
        self.assertEqual([month for month, _ in spread], [1, 2, 3])
        expected = math.log(2.0) / 3
        for _, monthly_return in spread:
            self.assertAlmostEqual(monthly_return, expected)

    def test_large_jumps_are_filtered(self):
        self.assertEqual(spread_monthly_log_change(0, 10.0, 1, math.exp(MAX_JUMP) * 10.01), [])

    def test_chained_weighted_aggregation_logic(self):
        contributions = {
            1: [(math.log(1.10), 2.0, "A"), (math.log(1.05), 1.0, "B")],
            2: [(math.log(1.02), 3.0, "A")],
        }
        series = chain_index_series([1, 2], contributions)
        first_month_rate = (math.log(1.10) * 2.0 + math.log(1.05) * 1.0) / 3.0
        expected_month_1 = 100.0 * math.exp(first_month_rate)
        expected_month_2 = expected_month_1 * 1.02
        self.assertEqual(series[0], {"m": "0000-01", "v": 100.0, "n": 0})
        self.assertAlmostEqual(series[1]["v"], round(expected_month_1, 3))
        self.assertAlmostEqual(series[2]["v"], round(expected_month_2, 3))

class IncrementalRefreshDedupTests(unittest.TestCase):
    """A re-downloaded note (same 44-digit access key in a new NFCE_XML_* folder)
    must be counted once; cancelled keys must be excluded. This protects the
    incremental-refresh workflow: dropping a fresh export folder never double-counts."""

    K1 = "1" * 44
    K2 = "2" * 44
    K3 = "3" * 44

    def test_redownload_is_deduped_and_cancelled_excluded(self):
        with tempfile.TemporaryDirectory() as root:
            folder_a = os.path.join(root, "NFCE_XML_A")
            folder_b = os.path.join(root, "NFCE_XML_B")  # a later re-export
            os.makedirs(folder_a)
            os.makedirs(folder_b)

            _write_note(folder_a, self.K1, "2025-01-10T12:00:00-03:00", 10.00)
            _write_note(folder_a, self.K2, "2025-02-10T12:00:00-03:00", 20.00)
            _write_note(folder_b, self.K1, "2025-01-10T12:00:00-03:00", 10.00)  # re-download
            _write_note(folder_b, self.K3, "2025-03-10T12:00:00-03:00", 30.00)
            _write_cancel(folder_b, self.K2)  # K2 later cancelled

            receipts, validation = parse_receipts(root)
            keys = sorted(r["key"] for r in receipts)

            self.assertEqual(keys, sorted([self.K1, self.K3]))   # K1 once, K2 gone
            self.assertEqual(validation["cancelled_unique_keys"], 1)
            self.assertEqual(validation["duplicate_xml_key_instances"], 1)  # the re-download
            self.assertEqual(validation["cancelled_receipts_skipped"], 1)

    def test_receipt_txt_export_parsed(self):
        from personal_inflation import parse_sefaz_receipt_txt_exports

        header = (
            "Chave_de_acesso|Numero|Serie|Data_de_emissao|Situacao|Valor_total_da_nota|"
            "Nome_razao_social_emit|CPF_CNPJ_emit|Cod_prod|Descricao_do_Produto_ou_servicos|"
            "NCM_prod|Unid_com|Quant_com|Valor_unit_com|Valor_total_prod|Cod_EAN\n"
        )
        key = "2" * 44
        row = (
            f"{key}|1|1|2026-07-16 20:40:05|A|10,00|Supermercado Litoral|08.189.400/0001-07|"
            "1|ARROZ TIO JOAO|10063021|UN|1,00|10,00|10,00|7896006710150\n"
        )
        with tempfile.TemporaryDirectory() as root:
            with open(os.path.join(root, "NFCE_20260101000000.txt"), "w", encoding="utf-8") as handle:
                handle.write(header + row)
            receipts, validation = parse_sefaz_receipt_txt_exports(root)
            self.assertEqual(validation["receipt_txt_receipts"], 1)
            self.assertEqual(receipts[0]["cnpj"], "08189400000107")
            self.assertEqual(receipts[0]["items"][0]["ean"], "7896006710150")


if __name__ == "__main__":
    unittest.main()
