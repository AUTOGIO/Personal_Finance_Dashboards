import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from litoral_store_prices import (  # noqa: E402
    LITORAL_CNPJ,
    build_payload,
    equal_weight_staple_index,
    filter_litoral_receipts,
    parse_sefaz_txt_exports,
    yoy_pairs,
)
from personal_inflation import normalize_description  # noqa: E402


NFE_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe">
 <NFe><infNFe Id="NFe{key}" versao="4.00">
  <ide><dhEmi>{dh}</dhEmi></ide>
  <emit><CNPJ>{cnpj}</CNPJ><xNome>SUPERMERCADO LITORAL LTDA.</xNome></emit>
  <det nItem="1"><prod>
   <xProd>{desc}</xProd><cEAN>{ean}</cEAN><NCM>10063021</NCM>
   <qCom>1.0000</qCom><uCom>UN</uCom><vUnCom>{price}</vUnCom><vProd>{price}</vProd>
  </prod></det>
  <total><ICMSTot><vNF>{price}</vNF></ICMSTot></total>
 </infNFe></NFe>
</nfeProc>"""

TXT_HEADER = (
    "Data_de_emissao|Descricao_do_Produto_ou_servicos|NCM_prod|CST_prod|"
    "Unid_com|Quant_com|Valor_unit_com|Valor_total_prod\n"
)


def _write_note(folder, key, dh, price, desc="ARROZ TIO JOAO 1KG POLIDO", ean="7896006710150", cnpj=LITORAL_CNPJ):
    path = os.path.join(folder, f"NFCE_{key}_20260101000000.xml")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(
            NFE_TEMPLATE.format(
                key=key,
                dh=dh,
                price=f"{price:.2f}",
                desc=desc,
                ean=ean,
                cnpj=cnpj,
            )
        )


def _write_txt(path, rows):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(TXT_HEADER)
        for emitted, desc, ncm, uom, qty, unit, total in rows:
            fh.write(f"{emitted}|{desc}|{ncm}|00|{uom}|{qty}|{unit}|{total}\n")


class LitoralStorePricesTests(unittest.TestCase):
    def test_filter_keeps_only_litoral_cnpj(self):
        receipts = [
            {"cnpj": LITORAL_CNPJ, "merchant": "LITORAL"},
            {"cnpj": "00000000000191", "merchant": "OUTRO"},
        ]
        kept, info = filter_litoral_receipts(receipts)
        self.assertEqual(len(kept), 1)
        self.assertEqual(info["receipts_skipped_other_cnpj"], 1)

    def test_yoy_pairs_skip_ineligible_years(self):
        pairs = yoy_pairs({2020: 10.0, 2021: 11.0, 2026: 50.0}, {2020, 2021})
        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs[0]["pct"], 10.0)

    def test_parse_sefaz_txt_groups_by_timestamp(self):
        with tempfile.TemporaryDirectory() as root:
            _write_txt(
                os.path.join(root, "NFCE_20260101000000.txt"),
                [
                    ("2023-12-30 10:00:00", "ARROZ TIO JOAO 1KG POLIDO", "10062010", "UN", "1,00", "8,39", "8,39"),
                    ("2023-12-30 10:00:00", "FEIJAO COMETA 1KG PRETO", "07133319", "UN", "2,00", "10,89", "21,78"),
                    ("2023-12-30 11:00:00", "BANANA PRATA KG", "08039000", "KG", "0,50", "7,49", "3,75"),
                ],
            )
            receipts, validation = parse_sefaz_txt_exports(root)
            self.assertEqual(validation["txt_rows"], 3)
            self.assertEqual(validation["txt_synthetic_receipts"], 2)
            self.assertEqual(len(receipts), 2)
            self.assertEqual(receipts[0]["cnpj"], LITORAL_CNPJ)
            self.assertEqual(len(receipts[0]["items"]), 2)

    def test_parse_compact_product_txt(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "NFCE_20260101000002.txt")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("Data_de_emissao|Descricao_do_Produto_ou_servicos|NCM_prod|Valor_unit_com\n")
                handle.write("2023-12-30 12:33:28|FARINHA DE MANDIOCA|11062000|5,5\n")
            receipts, validation = parse_sefaz_txt_exports(root)
            self.assertEqual(validation["txt_rows"], 1)
            self.assertEqual(validation["txt_synthetic_receipts"], 1)
            self.assertEqual(receipts[0]["items"][0]["qty"], 1.0)
            self.assertEqual(receipts[0]["items"][0]["unit_price"], 5.5)

    def test_staple_match_and_payload(self):
        with tempfile.TemporaryDirectory() as root:
            folder = os.path.join(root, "NFCE_XML_TEST")
            os.makedirs(folder)
            _write_note(folder, "20201226" + "0" * 36, "2020-12-26T10:00:00-03:00", 5.0)
            _write_note(folder, "20211226" + "1" * 36, "2021-12-26T10:00:00-03:00", 6.0)
            _write_note(folder, "20221226" + "2" * 36, "2022-12-26T10:00:00-03:00", 6.6)
            _write_note(
                folder,
                "20260701" + "3" * 36,
                "2026-07-01T10:00:00-03:00",
                9.0,
                desc="ARROZ TIO JOAO POLIDO 1KG",
            )
            _write_txt(
                os.path.join(root, "NFCE_20260101000001.txt"),
                [
                    ("2023-12-30 10:00:00", "ARROZ TIO JOAO 1KG POLIDO", "10062010", "UN", "1,00", "7,00", "7,00"),
                ],
            )

            from litoral_store_prices import load_store_receipts

            receipts, validation = load_store_receipts(root)
            data = build_payload(receipts, validation, personal_json="/nonexistent.json")

            self.assertGreaterEqual(data["kpis"]["receipts"], 4)
            self.assertGreaterEqual(data["kpis"]["txt_receipts"], 1)
            arroz = next(s for s in data["staples"] if s["id"] == "arroz")
            self.assertTrue(arroz["found"])
            # TXT 2023 + XML years should appear; 2026 excluded from YoY joins
            self.assertTrue(all(row["to_year"] != 2026 for row in arroz["yoy"]))
            years = {point["year"] for point in arroz["series"]}
            self.assertIn(2023, years)
            drift = next(s for s in data["snapshots"] if s["year"] == 2026)
            self.assertTrue(drift["naming_drift"])
            self.assertFalse(drift["yoy_eligible"])

    def test_discover_year_folders(self):
        from litoral_store_prices import discover_store_xml_dirs

        with tempfile.TemporaryDirectory() as root:
            year_dir = os.path.join(root, "2023")
            os.makedirs(year_dir)
            _write_note(year_dir, "20231226" + "4" * 36, "2023-12-26T10:00:00-03:00", 7.0)
            found = discover_store_xml_dirs(root)
            self.assertEqual(found, [year_dir])

    def test_equal_weight_basket_rebased(self):
        staples = [
            {
                "found": True,
                "series": [
                    {"year": 2020, "price": 10.0, "yoy_eligible": True},
                    {"year": 2021, "price": 12.0, "yoy_eligible": True},
                ],
            },
            {
                "found": True,
                "series": [
                    {"year": 2020, "price": 20.0, "yoy_eligible": True},
                    {"year": 2021, "price": 22.0, "yoy_eligible": True},
                ],
            },
        ]
        basket = equal_weight_staple_index(staples, [2020, 2021])
        self.assertEqual(basket[0]["v"], 100.0)
        self.assertGreater(basket[1]["v"], 100.0)

    def test_normalize_staple_label(self):
        self.assertEqual(
            normalize_description("ARROZ TIO JOAO 1KG POLIDO"),
            "ARROZ TIO JOAO 1KG POLIDO",
        )


if __name__ == "__main__":
    unittest.main()
