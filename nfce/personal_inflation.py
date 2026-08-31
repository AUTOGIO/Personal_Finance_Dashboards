#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Personal Inflation Index from NFC-e XMLs.

Source of truth:
- XMLs under notas/NFCE_XML_*.
- CSVs and JSONs in this repo are derived artifacts only.

Methodology:
1. Product identity is valid EAN when available, otherwise CNPJ-root +
   normalized description.
2. Commercial unit is part of the grouping key so UN and KG are never mixed.
3. Monthly product price is the median unit price inside each month.
4. Consecutive observed prices are converted to log changes and spread uniformly
   across intervening months.
5. Monthly inflation is the spend-weighted mean of active log changes.
6. The index is chained from a base value of 100 at the first active month.
"""

from __future__ import annotations

import argparse
import glob
import json
import math
import os
import re
import statistics
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from typing import Dict, Iterable, List, Tuple

BASE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(BASE))
DEFAULT_NOTES_DIR = os.path.join(BASE, "notas")
DEFAULT_JSON = os.path.join(BASE, "personal_inflation_data.json")
DEFAULT_HTML = os.path.join(BASE, "personal_inflation_index.html")
DEFAULT_VALIDATION_JSON = os.path.join(BASE, "personal_inflation_validation.json")
DEFAULT_BASELINE_JSON = os.path.join(BASE, "personal_inflation_baseline.json")
NS = {"n": "http://www.portalfiscal.inf.br/nfe"}
MAX_JUMP = math.log(4)


def _repo_relative(path: str) -> str:
    """Return path relative to the repo root when possible.

    Keeps validation payloads (and the fallback JSON embedded in
    personal_inflation_index.html) free of the operator's username so the
    output is portable between machines. See AUDIT-007.
    """
    try:
        return os.path.relpath(os.path.abspath(path), REPO_ROOT)
    except ValueError:
        return path

# IPCA annual (%) for a rough comparison line.
IPCA_ANNUAL = {
    2018: 3.75,
    2019: 4.31,
    2020: 4.52,
    2021: 10.06,
    2022: 5.79,
    2023: 4.62,
    2024: 4.83,
    2025: 4.50,
    2026: 4.30,
}

# Ground-truth baseline. Kept in-file as a fallback for the test suite (which
# imports this module and uses EXPECTED_METRICS directly) and as documentation
# of the expected metric shape. The runtime pipeline prefers whatever is on
# disk at DEFAULT_BASELINE_JSON so operators can bump the numbers after adding
# receipts without editing this file. See AUDIT-016.
EXPECTED_METRICS = {
    "receipts": 498,
    "cancelled_unique_keys": 4,
    "total_spend": 150170.52,
    "tracked_products": 622,
    "coverage_pct": 40.6,
    "final_index": 158.57,
    "last_month": "2026-07",
    "yoy12_pct": 5.88,
}


def load_baseline(baseline_path: str) -> dict:
    """Load the baseline metric dict from JSON, falling back to EXPECTED_METRICS."""
    if not os.path.exists(baseline_path):
        return dict(EXPECTED_METRICS)
    try:
        with open(baseline_path, encoding="utf-8") as handle:
            raw = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return dict(EXPECTED_METRICS)
    return {k: v for k, v in raw.items() if not k.startswith("_")}


def save_baseline(baseline_path: str, metrics: dict) -> None:
    payload = {
        "_note": (
            "Ground-truth baseline for src/nfce/personal_inflation.py. "
            "Update via `python3 personal_inflation.py --accept-new-baseline` "
            "after intentional data additions (see AUDIT-016 in REPOSITORY_AUDIT.md)."
        ),
    }
    payload.update(metrics)
    with open(baseline_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def _txt(el: ET.Element | None, path: str) -> str:
    if el is None:
        return ""
    node = el.find(path, NS)
    return node.text.strip() if node is not None and node.text else ""


def _json_dump(path: str, payload: dict) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=False)


def _record_example(validation: dict, field: str, example, limit: int = 8) -> None:
    bucket = validation.setdefault(field, [])
    if len(bucket) < limit:
        bucket.append(example)

def parse_number(raw: str, validation: dict, field_name: str, context: str) -> float:
    text = (raw or "").strip()
    if not text:
        validation["missing_numeric_fields"] += 1
        _record_example(validation, "missing_numeric_examples", {"field": field_name, "context": context})
        return 0.0
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    else:
        text = text.replace(",", ".")
    try:
        return float(text)
    except ValueError:
        validation["malformed_numeric_fields"] += 1
        _record_example(
            validation,
            "malformed_numeric_examples",
            {"field": field_name, "raw": raw, "context": context},
        )
        return 0.0


def normalize_description(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^A-Z0-9 ]", "", (text or "").upper())).strip()


def normalize_ean(raw_ean: str) -> str:
    return (raw_ean or "").strip().upper()


def is_valid_ean(raw_ean: str) -> bool:
    ean = normalize_ean(raw_ean)
    if not ean or ean == "SEM GTIN":
        return False
    if not ean.isdigit():
        return False
    if len(ean) not in {8, 12, 13, 14}:
        return False
    if set(ean) <= {"0"}:
        return False
    return True


def build_product_id(cnpj: str, desc: str, ean: str) -> str:
    if is_valid_ean(ean):
        return "EAN:" + normalize_ean(ean).lstrip("0")
    return "DSC:" + (cnpj or "")[:8] + ":" + normalize_description(desc)


def category(ncm: str, desc: str) -> str:
    upper_desc = (desc or "").upper()
    chapter = int(ncm[:2]) if ncm and ncm[:2].isdigit() else None
    if chapter == 30:
        return "Farmácia"
    if chapter in (33, 34, 48, 96):
        return "Higiene/Limpeza"
    if chapter == 22:
        alcoholic = any(token in upper_desc for token in ("CERV", "VINHO", "WHISK", "VODKA", "GIN ", "CACHAC", "APERITIVO", "LICOR"))
        if alcoholic or (ncm and ncm[:4] in ("2203", "2204", "2205", "2206", "2208")):
            return "Bebidas alcoólicas"
        return "Bebidas"
    if chapter is not None and 1 <= chapter <= 21:
        return "Alimentos"
    if chapter in (25, 27, 28, 29, 31, 32, 35, 36, 38, 39, 40, 44, 63, 69, 70, 72, 73, 74, 76, 82, 83, 84, 85, 90, 94):
        return "Casa/Materiais"
    if chapter in (61, 62, 64, 65):
        return "Vestuário"
    return "Outros"


def month_to_index(label: str) -> int:
    return int(label[:4]) * 12 + int(label[5:7]) - 1


def index_to_month(index: int) -> str:
    return f"{index // 12:04d}-{index % 12 + 1:02d}"


def _digits_only(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def parse_sefaz_receipt_txt_exports(notes_dir: str) -> Tuple[List[dict], dict]:
    """Parse SEFAZ pipe-delimited receipt exports (one row per line item).

    Header includes ``Chave_de_acesso`` plus product columns such as
    ``Descricao_do_Produto_ou_servicos``, ``Quant_com``, ``Valor_unit_com``.
    """
    paths = sorted(glob.glob(os.path.join(notes_dir, "NFCE_*.txt")))
    validation = {
        "receipt_txt_files": [_repo_relative(p) for p in paths],
        "receipt_txt_file_count": len(paths),
        "receipt_txt_rows": 0,
        "receipt_txt_malformed_rows": 0,
        "receipt_txt_receipts": 0,
    }
    if not paths:
        return [], validation

    buckets: Dict[str, dict] = {}
    blank_validation = {
        "missing_numeric_fields": 0,
        "malformed_numeric_fields": 0,
    }

    for path in paths:
        with open(path, encoding="utf-8-sig", errors="replace") as handle:
            header = handle.readline()
            if "Chave_de_acesso" not in header:
                continue
            columns = [name.strip() for name in header.strip().split("|")]
            index = {name: position for position, name in enumerate(columns)}

            def col(parts: List[str], name: str, default: str = "") -> str:
                position = index.get(name)
                if position is None or position >= len(parts):
                    return default
                return parts[position].strip()

            for line_no, line in enumerate(handle, start=2):
                line = line.strip()
                if not line:
                    continue
                parts = line.split("|")
                key = col(parts, "Chave_de_acesso")
                if len(key) != 44:
                    validation["receipt_txt_malformed_rows"] += 1
                    continue
                validation["receipt_txt_rows"] += 1
                context = f"{os.path.basename(path)}:{line_no}"

                if key not in buckets:
                    emitted = col(parts, "Data_de_emissao")
                    cnpj_raw = col(parts, "CPF_CNPJ_emit")
                    buckets[key] = {
                        "key": key,
                        "date": emitted[:10] if emitted else "",
                        "month": emitted[:7] if emitted else "",
                        "merchant": col(parts, "Nome_razao_social_emit"),
                        "cnpj": _digits_only(cnpj_raw),
                        "total": parse_number(col(parts, "Valor_total_da_nota"), blank_validation, "receipt_total", key),
                        "items": [],
                        "source": "receipt_txt",
                    }

                qty = parse_number(col(parts, "Quant_com"), blank_validation, "qty", context)
                unit_price = parse_number(col(parts, "Valor_unit_com"), blank_validation, "unit_price", context)
                total = parse_number(col(parts, "Valor_total_prod"), blank_validation, "item_total", context)
                ean = col(parts, "Cod_EAN")
                buckets[key]["items"].append(
                    {
                        "desc": col(parts, "Descricao_do_Produto_ou_servicos"),
                        "ean": ean,
                        "ncm": col(parts, "NCM_prod"),
                        "qty": qty,
                        "uom": col(parts, "Unid_com", "UN").upper().strip() or "UN",
                        "unit_price": unit_price,
                        "total": total if total > 0 else round(qty * unit_price, 2),
                    }
                )

    receipts = [buckets[key] for key in sorted(buckets)]
    validation["receipt_txt_receipts"] = len(receipts)
    validation["receipt_txt_missing_numeric_fields"] = blank_validation["missing_numeric_fields"]
    validation["receipt_txt_malformed_numeric_fields"] = blank_validation["malformed_numeric_fields"]
    return receipts, validation


def scan_xml_inventory(notes_dir: str, xml_dirs: List[str] | None = None) -> dict:
    if xml_dirs is None:
        xml_dirs = sorted(glob.glob(os.path.join(notes_dir, "NFCE_XML_*")))
    else:
        xml_dirs = sorted(xml_dirs)
    if not xml_dirs:
        raise SystemExit(f"nenhuma pasta XML encontrada em {notes_dir}")

    cancel_files = []
    cancel_keys = set()
    for directory in xml_dirs:
        for path in sorted(glob.glob(os.path.join(directory, "CANC_*.xml"))):
            cancel_files.append(path)
            match = re.search(r"NFCE_(\d{44})", os.path.basename(path))
            if match:
                cancel_keys.add(match.group(1))

    receipt_files = []
    key_to_paths = defaultdict(list)
    for directory in xml_dirs:
        for path in sorted(glob.glob(os.path.join(directory, "NFCE_*.xml"))):
            receipt_files.append(path)
            match = re.search(r"NFCE_(\d{44})", os.path.basename(path))
            if match:
                key_to_paths[match.group(1)].append(path)

    duplicate_keys = sorted(key for key, paths in key_to_paths.items() if len(paths) > 1)
    duplicate_instances = sum(len(paths) - 1 for paths in key_to_paths.values() if len(paths) > 1)

    return {
        "xml_dirs": xml_dirs,
        "receipt_files": receipt_files,
        "cancel_files": cancel_files,
        "cancel_keys": cancel_keys,
        "key_to_paths": key_to_paths,
        "duplicate_keys": duplicate_keys,
        "duplicate_instances": duplicate_instances,
    }


def parse_receipts(notes_dir: str, xml_dirs: List[str] | None = None) -> Tuple[List[dict], dict]:
    inventory = scan_xml_inventory(notes_dir, xml_dirs=xml_dirs)
    validation = {
        "notes_dir": _repo_relative(notes_dir),
        "xml_directories": [_repo_relative(d) for d in inventory["xml_dirs"]],
        "xml_note_files": len(inventory["receipt_files"]),
        "unique_xml_keys": len(inventory["key_to_paths"]),
        "duplicate_xml_key_instances": inventory["duplicate_instances"],
        "duplicate_xml_keys": inventory["duplicate_keys"][:8],
        "cancelled_files": len(inventory["cancel_files"]),
        "cancelled_unique_keys": len(inventory["cancel_keys"]),
        "cancelled_keys": sorted(inventory["cancel_keys"]),
        "cancelled_keys_without_note": sorted(inventory["cancel_keys"] - set(inventory["key_to_paths"]))[:8],
        "malformed_numeric_fields": 0,
        "missing_numeric_fields": 0,
        "notes_skipped_parse_errors": 0,
        "missing_product_nodes": 0,
        "duplicate_receipts_skipped": 0,
        "cancelled_receipts_skipped": 0,
        "items_with_nonpositive_qty_or_price": 0,
    }

    receipts = []
    seen = set()
    for path in sorted(inventory["receipt_files"]):
        key_match = re.search(r"NFCE_(\d{44})", os.path.basename(path))
        if not key_match:
            continue
        key = key_match.group(1)
        if key in inventory["cancel_keys"]:
            validation["cancelled_receipts_skipped"] += 1
            continue
        if key in seen:
            validation["duplicate_receipts_skipped"] += 1
            continue

        try:
            root = ET.parse(path).getroot()
        except ET.ParseError as exc:
            validation["notes_skipped_parse_errors"] += 1
            _record_example(validation, "parse_error_examples", {"path": path, "error": str(exc)})
            continue

        inf = root.find(".//n:infNFe", NS)
        date_value = _txt(inf, "n:ide/n:dhEmi") or _txt(inf, "n:ide/n:dEmi")
        emit = inf.find("n:emit", NS) if inf is not None else None
        seen.add(key)

        receipt = {
            "key": key,
            "date": date_value[:10],
            "month": date_value[:7],
            "merchant": _txt(emit, "n:xNome"),
            "cnpj": _txt(emit, "n:CNPJ"),
            "total": parse_number(_txt(inf, "n:total/n:ICMSTot/n:vNF"), validation, "receipt_total", key),
            "items": [],
        }

        for index, det in enumerate(inf.findall("n:det", NS) if inf is not None else [], start=1):
            prod = det.find("n:prod", NS)
            if prod is None:
                validation["missing_product_nodes"] += 1
                _record_example(validation, "missing_product_examples", {"receipt_key": key, "item_index": index})
                continue

            item = {
                "desc": _txt(prod, "n:xProd"),
                "ean": _txt(prod, "n:cEAN"),
                "ncm": _txt(prod, "n:NCM"),
                "qty": parse_number(_txt(prod, "n:qCom"), validation, "qty", f"{key}:{index}"),
                "uom": _txt(prod, "n:uCom").upper().strip(),
                "unit_price": parse_number(_txt(prod, "n:vUnCom"), validation, "unit_price", f"{key}:{index}"),
                "total": parse_number(_txt(prod, "n:vProd"), validation, "item_total", f"{key}:{index}"),
            }
            if item["qty"] <= 0 or item["unit_price"] <= 0:
                validation["items_with_nonpositive_qty_or_price"] += 1
            receipt["items"].append(item)

        receipts.append(receipt)

    receipts.sort(key=lambda row: (row["date"], row["key"]))
    validation["parsed_receipts"] = len(receipts)
    validation["parsed_items"] = sum(len(receipt["items"]) for receipt in receipts)
    return receipts, validation


def compute_monthly_product_stats(observations: Iterable[Tuple[int, float, float]]) -> Dict[int, Tuple[float, float]]:
    by_month = defaultdict(lambda: [[], 0.0])
    for month_index, unit_price, spend in observations:
        by_month[month_index][0].append(unit_price)
        by_month[month_index][1] += spend
    return {
        month_index: (statistics.median(values), total_spend)
        for month_index, (values, total_spend) in by_month.items()
    }


def spread_monthly_log_change(start_month: int, start_price: float, end_month: int, end_price: float, max_jump_log: float = MAX_JUMP) -> List[Tuple[int, float]]:
    if start_price <= 0 or end_price <= 0:
        return []
    log_change = math.log(end_price / start_price)
    if abs(log_change) > max_jump_log:
        return []
    month_gap = end_month - start_month
    if month_gap <= 0:
        return []
    monthly_return = log_change / month_gap
    return [(month, monthly_return) for month in range(start_month + 1, end_month + 1)]


def chain_index_series(months: List[int], contributions: Dict[int, List[Tuple[float, float, str]]], category_filter: str | None = None) -> List[dict]:
    series = []
    current_value = 100.0
    started = False
    for month_index in months:
        active = [(log_return, weight) for log_return, weight, cat in contributions[month_index] if category_filter is None or cat == category_filter]
        if category_filter is not None and not active and not started:
            continue
        if not started:
            started = True
            series.append({"m": index_to_month(month_index - 1), "v": 100.0, "n": 0})
        total_weight = sum(weight for _, weight in active)
        weighted_rate = sum(log_return * weight for log_return, weight in active) / total_weight if total_weight else 0.0
        current_value *= math.exp(weighted_rate)
        series.append({"m": index_to_month(month_index), "v": round(current_value, 3), "n": len(active)})
    return series


def build_index(receipts: List[dict], validation: dict) -> dict:
    observations = defaultdict(list)
    meta = {}
    total_spend = 0.0
    product_units = defaultdict(set)
    invalid_ean_fallbacks = 0

    for receipt in receipts:
        month_index = month_to_index(receipt["month"])
        for item in receipt["items"]:
            total_spend += item["total"]
            if item["qty"] <= 0 or item["unit_price"] <= 0:
                continue
            raw_ean = normalize_ean(item["ean"])
            product_code = build_product_id(receipt["cnpj"], item["desc"], raw_ean)
            if raw_ean and raw_ean != "SEM GTIN" and not is_valid_ean(raw_ean):
                invalid_ean_fallbacks += 1
                _record_example(validation, "invalid_ean_examples", {"ean": raw_ean, "item": item["desc"], "receipt_key": receipt["key"]})
            grouping_key = (product_code, item["uom"])
            observations[grouping_key].append((month_index, item["unit_price"], item["total"]))
            meta[grouping_key] = {
                "desc": item["desc"],
                "cat": category(item["ncm"], item["desc"]),
                "merchant": receipt["merchant"],
            }
            product_units[product_code].add(item["uom"])

    product_months = {key: compute_monthly_product_stats(values) for key, values in observations.items()}
    tracked = {key: months for key, months in product_months.items() if len(months) >= 2}
    tracked_spend = sum(spend for key in tracked for _, _, spend in observations[key])

    contributions = defaultdict(list)
    filtered_large_jumps = 0
    for key, monthly_stats in tracked.items():
        months = sorted(monthly_stats)
        for start_month, end_month in zip(months, months[1:]):
            start_price, start_spend = monthly_stats[start_month]
            end_price, end_spend = monthly_stats[end_month]
            spread = spread_monthly_log_change(start_month, start_price, end_month, end_price)
            if not spread and start_price > 0 and end_price > 0 and abs(math.log(end_price / start_price)) > MAX_JUMP:
                filtered_large_jumps += 1
                continue
            weight = (start_spend + end_spend) / 2
            for month_index, monthly_return in spread:
                contributions[month_index].append((monthly_return, weight, meta[key]["cat"]))

    active_months = sorted(contributions)
    overall = chain_index_series(active_months, contributions)

    ipca_ref = []
    current_ipca = 100.0
    for point in overall:
        year = int(point["m"][:4])
        if point is overall[0]:
            ipca_ref.append({"m": point["m"], "v": 100.0})
            continue
        monthly_factor = (1 + IPCA_ANNUAL.get(year, 4.0) / 100.0) ** (1 / 12)
        current_ipca *= monthly_factor
        ipca_ref.append({"m": point["m"], "v": round(current_ipca, 3)})

    year_end = {}
    for point in overall:
        year_end[int(point["m"][:4])] = point["v"]
    yoy = []
    for previous_year, current_year in zip(sorted(year_end), sorted(year_end)[1:]):
        yoy.append(
            {
                "year": current_year,
                "personal": round(100 * (year_end[current_year] / year_end[previous_year] - 1), 2),
                "ipca": IPCA_ANNUAL.get(current_year),
                "partial": current_year == int(overall[-1]["m"][:4]) and overall[-1]["m"][5:7] != "12",
            }
        )

    categories = []
    for category_name in sorted({value["cat"] for value in meta.values()}):
        category_series = chain_index_series(active_months, contributions, category_name)
        if len(category_series) < 3:
            continue
        span_months = month_to_index(category_series[-1]["m"]) - month_to_index(category_series[0]["m"])
        if span_months < 12:
            continue
        cumulative_factor = category_series[-1]["v"] / 100
        category_spend = sum(record[2] for key in tracked if meta[key]["cat"] == category_name for record in observations[key])
        category_products = len([key for key in tracked if meta[key]["cat"] == category_name])
        categories.append(
            {
                "cat": category_name,
                "products": category_products,
                "spend": round(category_spend, 2),
                "from": category_series[0]["m"],
                "to": category_series[-1]["m"],
                "cum_pct": round(100 * (cumulative_factor - 1), 1),
                "ann_pct": round(100 * (cumulative_factor ** (12 / span_months) - 1), 2),
            }
        )
    categories.sort(key=lambda row: -row["ann_pct"])

    products = []
    for key, monthly_stats in tracked.items():
        months = sorted(monthly_stats)
        month_span = months[-1] - months[0]
        first_price = monthly_stats[months[0]][0]
        last_price = monthly_stats[months[-1]][0]
        spend = sum(item_total for _, _, item_total in observations[key])
        annualized = (last_price / first_price) ** (12 / month_span) - 1 if month_span >= 1 and first_price > 0 else None
        products.append(
            {
                "desc": meta[key]["desc"],
                "cat": meta[key]["cat"],
                "uom": key[1],
                "merchant": meta[key]["merchant"],
                "months": len(monthly_stats),
                "from": index_to_month(months[0]),
                "to": index_to_month(months[-1]),
                "p_first": round(first_price, 2),
                "p_last": round(last_price, 2),
                "cum_pct": round(100 * (last_price / first_price - 1), 1) if first_price > 0 else None,
                "ann_pct": round(100 * annualized, 1) if annualized is not None else None,
                "spend": round(spend, 2),
            }
        )
    products.sort(key=lambda row: -row["spend"])

    movers_pool = [
        row
        for row in products
        if row["months"] >= 3 and month_to_index(row["to"]) - month_to_index(row["from"]) >= 10 and row["ann_pct"] is not None and abs(row["ann_pct"]) < 200
    ]
    movers_pool.sort(key=lambda row: -row["ann_pct"])
    risers = movers_pool[:8]
    fallers = sorted(movers_pool[-8:], key=lambda row: row["ann_pct"])

    span_months = month_to_index(overall[-1]["m"]) - month_to_index(overall[0]["m"])
    cumulative_factor = overall[-1]["v"] / 100
    by_label = {point["m"]: point["v"] for point in overall}
    final_month_index = month_to_index(overall[-1]["m"])
    twelve_month_value = by_label.get(index_to_month(final_month_index - 12))
    yoy12 = round(100 * (overall[-1]["v"] / twelve_month_value - 1), 2) if twelve_month_value else None

    multi_uom_products = sorted(product_code for product_code, uoms in product_units.items() if len(uoms) > 1)
    validation["invalid_ean_fallbacks"] = invalid_ean_fallbacks
    validation["products_with_multiple_units"] = len(multi_uom_products)
    validation["products_with_multiple_units_examples"] = multi_uom_products[:8]
    validation["filtered_large_jumps"] = filtered_large_jumps

    return {
        "generated_from": f"{len(receipts)} notas fiscais (NFC-e), {overall[0]['m']} a {overall[-1]['m']}",
        "kpis": {
            "cum_pct": round(100 * (cumulative_factor - 1), 1),
            "ann_pct": round(100 * (cumulative_factor ** (12 / span_months) - 1), 2),
            "yoy12_pct": yoy12,
            "last_month": overall[-1]["m"],
            "tracked_products": len(tracked),
            "coverage_pct": round(100 * tracked_spend / total_spend, 1),
            "total_spend": round(total_spend, 2),
            "receipts": len(receipts),
        },
        "index": overall,
        "ipca_ref": ipca_ref,
        "yoy": yoy,
        "categories": categories,
        "risers": risers,
        "fallers": fallers,
        "products": products,
        "ipca_note": "IPCA anual (IBGE) composto uniformemente no ano; 2025 aproximado, 2026 estimativa.",
    }


def verify_expected_metrics(data: dict, validation: dict, expected: dict | None = None) -> dict:
    if expected is None:
        expected = EXPECTED_METRICS
    actual = {
        "receipts": data["kpis"]["receipts"],
        "cancelled_unique_keys": validation["cancelled_unique_keys"],
        "total_spend": round(data["kpis"]["total_spend"], 2),
        "tracked_products": data["kpis"]["tracked_products"],
        "coverage_pct": round(data["kpis"]["coverage_pct"], 1),
        "final_index": round(data["index"][-1]["v"], 2),
        "last_month": data["kpis"]["last_month"],
        "yoy12_pct": round(data["kpis"]["yoy12_pct"], 2),
    }
    mismatches = []
    for key, expected_value in expected.items():
        if actual[key] != expected_value:
            mismatches.append({"metric": key, "expected": expected_value, "actual": actual[key]})
    return {"expected": dict(expected), "actual": actual, "matches": not mismatches, "mismatches": mismatches}


def write_html_payload(html_path: str, data: dict, validation_report: dict) -> None:
    if not os.path.exists(html_path):
        return
    html = open(html_path, encoding="utf-8").read()
    data_payload = json.dumps(data, ensure_ascii=False)
    updated, data_replaced = re.subn(
        r"/\*__DATA__\*/.*?/\*__END_DATA__\*/",
        lambda _: "/*__DATA__*/" + data_payload + "/*__END_DATA__*/",
        html,
        count=1,
        flags=re.S,
    )
    validation_payload = json.dumps(validation_report, ensure_ascii=False)
    updated, validation_replaced = re.subn(
        r"/\*__VALIDATION__\*/.*?/\*__END_VALIDATION__\*/",
        lambda _: "/*__VALIDATION__*/" + validation_payload + "/*__END_VALIDATION__*/",
        updated,
        count=1,
        flags=re.S,
    )
    if data_replaced or validation_replaced:
        with open(html_path, "w", encoding="utf-8") as handle:
            handle.write(updated)


def build_cli() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build the personal inflation index from NFC-e XMLs.")
    parser.add_argument("--notes-dir", default=DEFAULT_NOTES_DIR, help="Directory containing NFCE_XML_* folders.")
    parser.add_argument("--output-json", default=DEFAULT_JSON, help="Main analysis JSON output.")
    parser.add_argument("--output-html", default=DEFAULT_HTML, help="HTML file to inject data into.")
    parser.add_argument("--validation-json", default=DEFAULT_VALIDATION_JSON, help="Validation JSON output.")
    parser.add_argument("--baseline-json", default=DEFAULT_BASELINE_JSON, help="JSON file with expected metric baseline (see AUDIT-016).")
    parser.add_argument("--skip-html", action="store_true", help="Do not inject data into the HTML file.")
    parser.add_argument("--verify-ground-truth", action="store_true", help="Exit non-zero if the current results do not match the baseline metrics.")
    parser.add_argument("--accept-new-baseline", action="store_true", help="Overwrite --baseline-json with the current run's metrics.")
    return parser


def main(argv: List[str] | None = None) -> int:
    args = build_cli().parse_args(argv)

    receipts, validation = parse_receipts(args.notes_dir)
    xml_keys = {row["key"] for row in receipts}
    cancel_keys = set(validation.get("cancelled_keys") or [])
    txt_receipts, txt_validation = parse_sefaz_receipt_txt_exports(args.notes_dir)
    validation.update(txt_validation)
    txt_added = 0
    for receipt in txt_receipts:
        if receipt["key"] in xml_keys:
            validation["receipt_txt_skipped_existing_xml"] = validation.get("receipt_txt_skipped_existing_xml", 0) + 1
            continue
        if receipt["key"] in cancel_keys:
            validation["receipt_txt_skipped_cancelled"] = validation.get("receipt_txt_skipped_cancelled", 0) + 1
            continue
        receipts.append(receipt)
        xml_keys.add(receipt["key"])
        txt_added += 1
    validation["receipt_txt_receipts_added"] = txt_added
    receipts.sort(key=lambda row: (row["date"], row["key"]))
    validation["parsed_receipts"] = len(receipts)
    validation["parsed_items"] = sum(len(row["items"]) for row in receipts)
    data = build_index(receipts, validation)
    expected = load_baseline(args.baseline_json)
    verification = verify_expected_metrics(data, validation, expected=expected)

    validation_report = {
        "source_of_truth": "XML under notas/NFCE_XML_* plus SEFAZ receipt NFCE_*.txt (keys not already in XML)",
        "validation": validation,
        "ground_truth_check": verification,
    }

    _json_dump(args.output_json, data)
    _json_dump(args.validation_json, validation_report)
    if not args.skip_html:
        write_html_payload(args.output_html, data, validation_report)

    print(f"notas lidas: {data['kpis']['receipts']} (canceladas únicas: {validation['cancelled_unique_keys']})")
    print(
        "índice: "
        f"{data['index'][0]['m']} → {data['index'][-1]['m']}  "
        f"acumulado {data['kpis']['cum_pct']:+.1f}%  "
        f"anualizado {data['kpis']['ann_pct']:+.2f}%/ano"
    )
    print(
        f"produtos rastreados: {data['kpis']['tracked_products']}  "
        f"cobertura do gasto: {data['kpis']['coverage_pct']}%  "
        f"12m: {data['kpis']['yoy12_pct']}%"
    )
    print(
        f"duplicatas XML: {validation['duplicate_xml_key_instances']}  "
        f"saltos >4x filtrados: {validation['filtered_large_jumps']}  "
        f"EANs inválidos tratados: {validation['invalid_ean_fallbacks']}"
    )
    print(f"gravado {os.path.basename(args.output_json)} e {os.path.basename(args.validation_json)}")
    if not args.skip_html and os.path.exists(args.output_html):
        print(f"dados injetados em {os.path.basename(args.output_html)}")
    if verification["matches"]:
        print("ground truth check: OK")
    else:
        print("ground truth check: FAIL")
        for mismatch in verification["mismatches"]:
            print(f"  - {mismatch['metric']}: esperado={mismatch['expected']} atual={mismatch['actual']}")
        if args.accept_new_baseline:
            save_baseline(args.baseline_json, verification["actual"])
            print(f"baseline atualizado: {os.path.basename(args.baseline_json)}")
            return 0
        if args.verify_ground_truth:
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
