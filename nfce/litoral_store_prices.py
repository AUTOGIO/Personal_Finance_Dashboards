#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Supermercado Litoral store-price snapshots from NFC-e XMLs + SEFAZ TXT exports.

Parallel track to personal_inflation.py — never merges into notas/.

Source of truth:
- Year folders `2020/`…`2026/` (or legacy `NFCE_XML_*`) under notas_litoral/
- Optional NFCE_*.txt SEFAZ pipe-delimited product exports in the same root

Methodology:
1. Parse XMLs with the shared personal_inflation helpers; parse NFCE_*.txt
   into synthetic receipts (grouped by emission timestamp).
2. Keep only emitente CNPJ 08189400000107 (TXT rows are assumed Litoral).
3. Treat each calendar year as a store snapshot window (XML ≈26/Dec;
   TXT often late-Dec / early-Jul multi-day lots).
4. Product identity for store prices = normalized description + UOM
   (TXT has no EAN; this also merges XML+TXT for the same shelf name).
5. Snapshot price = median unit price within that year.
6. YoY % uses consecutive Dec-style years; 2026 is reported but excluded
   from YoY joins because naming drifts break product identity.
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
from collections import Counter, defaultdict
from typing import Dict, Iterable, List, Optional, Tuple

from personal_inflation import (
    IPCA_ANNUAL,
    build_product_id,
    category,
    normalize_description,
    normalize_ean,
    parse_number,
    parse_receipts,
    parse_sefaz_receipt_txt_exports,
    write_html_payload,
)

BASE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(BASE))
DEFAULT_NOTES_DIR = os.path.join(BASE, "notas_litoral")
DEFAULT_JSON = os.path.join(BASE, "litoral_price_data.json")
DEFAULT_VALIDATION_JSON = os.path.join(BASE, "litoral_price_validation.json")
DEFAULT_HTML = os.path.join(BASE, "litoral_store_prices.html")
DEFAULT_PERSONAL_JSON = os.path.join(BASE, "personal_inflation_data.json")


def _repo_relative(path: str) -> str:
    """Return path relative to the repo root (portable JSON payloads).

    See AUDIT-007 in REPOSITORY_AUDIT.md.
    """
    try:
        return os.path.relpath(os.path.abspath(path), REPO_ROOT)
    except ValueError:
        return path

LITORAL_CNPJ = "08189400000107"
NAMING_DRIFT_YEAR = 2026

# Exact product labels tracked in LitoralPriceTracker (Dec snapshots).
STAPLES = [
    {"id": "arroz", "label": "Arroz", "match": "ARROZ TIO JOAO 1KG POLIDO"},
    {"id": "feijao", "label": "Feijão", "match": "FEIJAO COMETA 1KG PRETO"},
    {"id": "cafe", "label": "Café", "match": "CAFE PILAO 250G TRADICIONAL VACUO"},
    {"id": "acucar", "label": "Açúcar", "match": "ACUCAR ESTRELA 1KG REF.ESPECIAL"},
    {"id": "oleo", "label": "Óleo", "match": "OLEO SOYA 900ML DE SOJA PET"},
    {"id": "banana", "label": "Banana", "match": "BANANA PRATA KG"},
    {"id": "pao", "label": "Pão", "match": "PAO LITORAL FRANCES KG"},
    {"id": "leite", "label": "Leite", "match": "LEITE BETANIA 1L INTEGRAL TAMPA ROSCA"},
]

# Broader personal-basket keyword families for the compare panel.
PERSONAL_STAPLE_KEYWORDS = {
    "arroz": ("ARROZ",),
    "feijao": ("FEIJAO", "FEIJÃO"),
    "cafe": ("CAFE", "CAFÉ", "PILAO", "PILÃO"),
    "acucar": ("ACUCAR", "AÇÚCAR", "ACUCAR"),
    "oleo": ("OLEO", "ÓLEO", "SOYA", "SOJA"),
    "banana": ("BANANA",),
    "pao": ("PAO ", "PÃO ", "FRANCES", "FRANCÊS"),
    "leite": ("LEITE", "BETANIA", "BETÂNIA"),
}


def _json_dump(path: str, payload: dict) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=False)


def parse_sefaz_txt_exports(notes_dir: str) -> Tuple[List[dict], dict]:
    """Parse SEFAZ pipe-delimited NFCE_*.txt product dumps into synthetic receipts.

    Expected header:
    Data_de_emissao|Descricao_do_Produto_ou_servicos|NCM_prod|CST_prod|
    Unid_com|Quant_com|Valor_unit_com|Valor_total_prod
    """
    paths = sorted(glob.glob(os.path.join(notes_dir, "NFCE_*.txt")))
    validation = {
        "txt_files": [_repo_relative(p) for p in paths],
        "txt_file_count": len(paths),
        "txt_rows": 0,
        "txt_malformed_rows": 0,
        "txt_skipped_nonpositive": 0,
        "txt_synthetic_receipts": 0,
    }
    if not paths:
        return [], validation

    # timestamp -> list of items
    buckets: Dict[str, List[dict]] = defaultdict(list)
    blank_validation = {
        "missing_numeric_fields": 0,
        "malformed_numeric_fields": 0,
    }

    for path in paths:
        with open(path, encoding="utf-8", errors="replace") as handle:
            header = handle.readline()
            if "Data_de_emissao" not in header or "Descricao_do_Produto" not in header:
                validation["txt_malformed_rows"] += 1
                continue
            if "Chave_de_acesso" in header:
                validation["txt_malformed_rows"] += 1
                continue
            columns = [name.strip() for name in header.strip().split("|")]
            compact = len(columns) <= 5
            for line_no, line in enumerate(handle, start=2):
                line = line.strip()
                if not line:
                    continue
                parts = line.split("|")
                if compact:
                    if len(parts) < 4:
                        validation["txt_malformed_rows"] += 1
                        continue
                    emitted, desc, ncm, unit_raw = parts[:4]
                    _cst, uom, qty_raw, total_raw = "", "UN", "1", unit_raw
                elif len(parts) < 8:
                    validation["txt_malformed_rows"] += 1
                    continue
                else:
                    emitted, desc, ncm, _cst, uom, qty_raw, unit_raw, total_raw = parts[:8]
                emitted = emitted.strip()
                if len(emitted) < 10:
                    validation["txt_malformed_rows"] += 1
                    continue
                context = f"{os.path.basename(path)}:{line_no}"
                qty = parse_number(qty_raw, blank_validation, "qty", context)
                unit_price = parse_number(unit_raw, blank_validation, "unit_price", context)
                total = parse_number(total_raw, blank_validation, "item_total", context)
                validation["txt_rows"] += 1
                if qty <= 0 or unit_price <= 0:
                    validation["txt_skipped_nonpositive"] += 1
                    continue
                buckets[emitted].append(
                    {
                        "desc": desc.strip(),
                        "ean": "",
                        "ncm": ncm.strip(),
                        "qty": qty if qty > 0 else 1.0,
                        "uom": (uom or "UN").upper().strip(),
                        "unit_price": unit_price,
                        "total": total if total > 0 else round((qty if qty > 0 else 1.0) * unit_price, 2),
                    }
                )

    receipts = []
    for index, emitted in enumerate(sorted(buckets)):
        items = buckets[emitted]
        date_value = emitted[:10]
        key = f"TXT:{date_value}:{index:06d}"
        receipts.append(
            {
                "key": key,
                "date": date_value,
                "month": date_value[:7],
                "merchant": "SUPERMERCADO LITORAL LTDA.",
                "cnpj": LITORAL_CNPJ,
                "total": round(sum(item["total"] for item in items), 2),
                "items": items,
                "source": "txt",
            }
        )
    validation["txt_synthetic_receipts"] = len(receipts)
    validation["txt_missing_numeric_fields"] = blank_validation["missing_numeric_fields"]
    validation["txt_malformed_numeric_fields"] = blank_validation["malformed_numeric_fields"]
    return receipts, validation


def discover_store_xml_dirs(notes_dir: str) -> List[str]:
    """Prefer legacy NFCE_XML_* folders; else year folders like 2020/…/2026/."""
    legacy = sorted(glob.glob(os.path.join(notes_dir, "NFCE_XML_*")))
    if legacy:
        return legacy
    year_dirs = []
    for path in sorted(glob.glob(os.path.join(notes_dir, "20[0-9][0-9]"))):
        if not os.path.isdir(path):
            continue
        if glob.glob(os.path.join(path, "NFCE_*.xml")):
            year_dirs.append(path)
    return year_dirs


def load_store_receipts(notes_dir: str) -> Tuple[List[dict], dict]:
    """Load XML receipts (if any) plus SEFAZ TXT exports under notes_dir."""
    validation: dict = {
        "notes_dir": _repo_relative(notes_dir),
        "xml_directories": [],
        "xml_note_files": 0,
        "unique_xml_keys": 0,
        "duplicate_xml_key_instances": 0,
        "cancelled_unique_keys": 0,
        "parsed_receipts": 0,
        "parsed_items": 0,
    }
    receipts: List[dict] = []

    xml_dirs = discover_store_xml_dirs(notes_dir)
    if xml_dirs:
        xml_receipts, xml_validation = parse_receipts(notes_dir, xml_dirs=xml_dirs)
        for row in xml_receipts:
            row.setdefault("source", "xml")
        receipts.extend(xml_receipts)
        validation.update(xml_validation)
        validation["xml_layout"] = (
            "NFCE_XML_*" if any(os.path.basename(d).startswith("NFCE_XML_") for d in xml_dirs) else "year_folders"
        )
    else:
        validation["xml_skipped"] = "nenhuma pasta NFCE_XML_* ou 20XX/ com XML"

    txt_receipts, txt_validation = parse_sefaz_txt_exports(notes_dir)
    receipts.extend(txt_receipts)
    validation.update(txt_validation)

    receipt_txt, receipt_txt_validation = parse_sefaz_receipt_txt_exports(notes_dir)
    xml_keys = {row["key"] for row in receipts if len(row.get("key", "")) == 44}
    receipt_txt_added = 0
    for receipt in receipt_txt:
        if receipt["key"] in xml_keys:
            receipt_txt_validation["receipt_txt_skipped_existing_xml"] = (
                receipt_txt_validation.get("receipt_txt_skipped_existing_xml", 0) + 1
            )
            continue
        if (receipt.get("cnpj") or "") != LITORAL_CNPJ:
            receipt_txt_validation["receipt_txt_skipped_other_cnpj"] = (
                receipt_txt_validation.get("receipt_txt_skipped_other_cnpj", 0) + 1
            )
            continue
        receipt.setdefault("source", "receipt_txt")
        receipts.append(receipt)
        xml_keys.add(receipt["key"])
        receipt_txt_added += 1
    receipt_txt_validation["receipt_txt_receipts_added"] = receipt_txt_added
    validation.update(receipt_txt_validation)

    if not receipts:
        raise SystemExit(f"nenhuma NFC-e XML ou NFCE_*.txt encontrada em {notes_dir}")

    receipts.sort(key=lambda row: (row["date"], row["key"]))
    validation["parsed_receipts"] = len(receipts)
    validation["parsed_items"] = sum(len(row["items"]) for row in receipts)
    validation["xml_receipts"] = sum(1 for row in receipts if row.get("source") == "xml")
    validation["txt_receipts"] = sum(1 for row in receipts if row.get("source") == "txt")
    validation["receipt_txt_receipts_kept"] = sum(1 for row in receipts if row.get("source") == "receipt_txt")
    return receipts, validation


def filter_litoral_receipts(receipts: List[dict]) -> Tuple[List[dict], dict]:
    kept = [row for row in receipts if (row.get("cnpj") or "") == LITORAL_CNPJ]
    skipped = len(receipts) - len(kept)
    merchants = Counter(row.get("merchant") or "?" for row in receipts)
    return kept, {
        "expected_cnpj": LITORAL_CNPJ,
        "receipts_kept": len(kept),
        "receipts_skipped_other_cnpj": skipped,
        "merchants_seen": dict(merchants.most_common(8)),
    }


def snapshot_meta(receipts: List[dict]) -> List[dict]:
    by_year: Dict[int, Counter] = defaultdict(Counter)
    for receipt in receipts:
        if not receipt.get("date"):
            continue
        year = int(receipt["date"][:4])
        by_year[year][receipt["date"]] += 1
    snapshots = []
    for year in sorted(by_year):
        mode_date, count = by_year[year].most_common(1)[0]
        snapshots.append(
            {
                "year": year,
                "mode_date": mode_date,
                "receipts_on_mode_date": count,
                "distinct_dates": len(by_year[year]),
                "total_receipts": sum(by_year[year].values()),
                "naming_drift": year == NAMING_DRIFT_YEAR,
                "yoy_eligible": year != NAMING_DRIFT_YEAR,
            }
        )
    return snapshots


def collect_year_prices(receipts: List[dict]) -> Tuple[dict, dict, dict]:
    """Return (prices[key][year] = [unit_prices], spend[key][year], meta[key]).

    Store track keys by normalized description + UOM so XML (with EAN) and
    TXT (no EAN) observations of the same shelf label merge.
    """
    prices: Dict[Tuple[str, str], Dict[int, List[float]]] = defaultdict(lambda: defaultdict(list))
    spend: Dict[Tuple[str, str], Dict[int, float]] = defaultdict(lambda: defaultdict(float))
    meta: Dict[Tuple[str, str], dict] = {}
    desc_votes: Dict[Tuple[str, str], Counter] = defaultdict(Counter)

    for receipt in receipts:
        year = int(receipt["date"][:4])
        for item in receipt["items"]:
            if item["qty"] <= 0 or item["unit_price"] <= 0:
                continue
            desc_norm = normalize_description(item["desc"])
            if not desc_norm:
                continue
            key = (desc_norm, item["uom"])
            prices[key][year].append(item["unit_price"])
            spend[key][year] += item["total"]
            weight = 0 if year == NAMING_DRIFT_YEAR else 1
            desc_votes[key][item["desc"]] += weight
            product_code = build_product_id(receipt["cnpj"], item["desc"], item.get("ean") or "")
            if key not in meta:
                meta[key] = {
                    "desc": item["desc"],
                    "desc_norm": desc_norm,
                    "cat": category(item["ncm"], item["desc"]),
                    "ncm": item["ncm"],
                    "ean": normalize_ean(item.get("ean") or ""),
                    "product_id": product_code,
                    "desc_variants": set(),
                }
            meta[key]["desc_variants"].add(desc_norm)
            if year != NAMING_DRIFT_YEAR:
                meta[key]["ncm"] = item["ncm"]
                if item.get("ean"):
                    meta[key]["ean"] = normalize_ean(item["ean"])
                    meta[key]["product_id"] = build_product_id(receipt["cnpj"], item["desc"], item["ean"])

    for key, votes in desc_votes.items():
        ranked = votes.most_common()
        best = next((desc for desc, count in ranked if count > 0), ranked[0][0] if ranked else meta[key]["desc"])
        meta[key]["desc"] = best
        meta[key]["desc_norm"] = normalize_description(best)
        meta[key]["cat"] = category(meta[key].get("ncm", ""), best)
        meta[key]["desc_variants"] = sorted(meta[key]["desc_variants"])
    return prices, spend, meta


def median_year_prices(prices: dict) -> Dict[Tuple[str, str], Dict[int, float]]:
    return {
        key: {year: statistics.median(values) for year, values in year_map.items()}
        for key, year_map in prices.items()
    }


def yoy_pairs(year_prices: Dict[int, float], eligible_years: Iterable[int]) -> List[dict]:
    years = [year for year in sorted(year_prices) if year in eligible_years]
    rows = []
    for previous, current in zip(years, years[1:]):
        p0 = year_prices[previous]
        p1 = year_prices[current]
        if p0 <= 0 or p1 <= 0:
            continue
        rows.append(
            {
                "from_year": previous,
                "to_year": current,
                "p_from": round(p0, 2),
                "p_to": round(p1, 2),
                "pct": round(100 * (p1 / p0 - 1), 2),
            }
        )
    return rows


def build_product_rows(
    medians: dict,
    spend: dict,
    meta: dict,
    eligible_years: set,
) -> List[dict]:
    rows = []
    for key, year_prices in medians.items():
        years = sorted(year_prices)
        if len(years) < 2:
            continue
        first_year, last_year = years[0], years[-1]
        p0, p1 = year_prices[first_year], year_prices[last_year]
        span = last_year - first_year
        cagr = (p1 / p0) ** (1 / span) - 1 if span > 0 and p0 > 0 else None
        total_spend = sum(spend[key].values())
        series = [{"year": year, "price": round(year_prices[year], 2), "spend": round(spend[key][year], 2)} for year in years]
        rows.append(
            {
                "desc": meta[key]["desc"],
                "desc_norm": meta[key]["desc_norm"],
                "cat": meta[key]["cat"],
                "uom": key[1],
                "product_id": meta[key]["product_id"],
                "years": len(years),
                "from_year": first_year,
                "to_year": last_year,
                "p_first": round(p0, 2),
                "p_last": round(p1, 2),
                "cum_pct": round(100 * (p1 / p0 - 1), 1) if p0 > 0 else None,
                "cagr_pct": round(100 * cagr, 1) if cagr is not None else None,
                "spend": round(total_spend, 2),
                "yoy": yoy_pairs(year_prices, eligible_years),
                "series": series,
                "has_naming_drift_year": NAMING_DRIFT_YEAR in year_prices,
            }
        )
    rows.sort(key=lambda row: -row["spend"])
    return rows


def match_staple(medians: dict, meta: dict, match_text: str) -> Optional[Tuple[Tuple[str, str], Dict[int, float]]]:
    target = normalize_description(match_text)
    exact = []
    partial = []
    for key, year_prices in medians.items():
        variants = set(meta[key].get("desc_variants") or [])
        variants.add(meta[key]["desc_norm"])
        if target in variants:
            exact.append((key, year_prices))
        elif any(target in variant or variant in target for variant in variants if variant):
            partial.append((key, year_prices))
    pool = exact or partial
    if not pool:
        return None
    # Prefer the series with the most Dec-eligible years, then spend proxy = len samples.
    pool.sort(key=lambda item: (-len([y for y in item[1] if y != NAMING_DRIFT_YEAR]), -len(item[1])))
    return pool[0]


def build_staples(medians: dict, meta: dict, eligible_years: set) -> List[dict]:
    staples = []
    for staple in STAPLES:
        matched = match_staple(medians, meta, staple["match"])
        if matched is None:
            staples.append(
                {
                    "id": staple["id"],
                    "label": staple["label"],
                    "match": staple["match"],
                    "found": False,
                    "desc": None,
                    "uom": None,
                    "series": [],
                    "yoy": [],
                    "cum_pct": None,
                    "cagr_pct": None,
                }
            )
            continue
        key, year_prices = matched
        years = sorted(year_prices)
        first_year, last_year = years[0], years[-1]
        p0, p1 = year_prices[first_year], year_prices[last_year]
        span = last_year - first_year
        cagr = (p1 / p0) ** (1 / span) - 1 if span > 0 and p0 > 0 else None
        staples.append(
            {
                "id": staple["id"],
                "label": staple["label"],
                "match": staple["match"],
                "found": True,
                "desc": meta[key]["desc"],
                "uom": key[1],
                "product_id": meta[key]["product_id"],
                "series": [
                    {
                        "year": year,
                        "price": round(year_prices[year], 2),
                        "yoy_eligible": year in eligible_years,
                    }
                    for year in years
                ],
                "yoy": yoy_pairs(year_prices, eligible_years),
                "from_year": first_year,
                "to_year": last_year,
                "p_first": round(p0, 2),
                "p_last": round(p1, 2),
                "cum_pct": round(100 * (p1 / p0 - 1), 1) if p0 > 0 else None,
                "cagr_pct": round(100 * cagr, 1) if cagr is not None else None,
            }
        )
    return staples


def equal_weight_staple_index(staples: List[dict], eligible_years: List[int]) -> List[dict]:
    """Geometric mean of staple prices, rebased to 100 at first year with full coverage."""
    by_year: Dict[int, List[float]] = defaultdict(list)
    for staple in staples:
        if not staple.get("found"):
            continue
        for point in staple["series"]:
            if point["year"] in eligible_years and point["price"] > 0:
                by_year[point["year"]].append(point["price"])

    years = [year for year in eligible_years if year in by_year]
    if not years:
        return []

    # Require at least half the found staples in a year.
    found_count = sum(1 for staple in staples if staple.get("found"))
    min_n = max(2, found_count // 2)
    geo = {}
    for year in years:
        prices = by_year[year]
        if len(prices) < min_n:
            continue
        log_mean = sum(math.log(price) for price in prices) / len(prices)
        geo[year] = math.exp(log_mean)

    ordered = sorted(geo)
    if not ordered:
        return []
    base = geo[ordered[0]]
    series = []
    previous = None
    for year in ordered:
        value = 100 * geo[year] / base
        pct = None if previous is None else round(100 * (geo[year] / previous - 1), 2)
        series.append(
            {
                "year": year,
                "v": round(value, 2),
                "n": len(by_year[year]),
                "yoy_pct": pct,
                "ipca": IPCA_ANNUAL.get(year),
            }
        )
        previous = geo[year]
    return series


def compare_with_personal(staples: List[dict], personal_path: str) -> List[dict]:
    if not os.path.exists(personal_path):
        return []
    try:
        personal = json.load(open(personal_path, encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

    products = personal.get("products") or []
    compare = []
    for staple in staples:
        keywords = PERSONAL_STAPLE_KEYWORDS.get(staple["id"], ())
        candidates = []
        for product in products:
            desc_upper = (product.get("desc") or "").upper()
            if any(token in desc_upper for token in keywords):
                candidates.append(product)
        candidates.sort(key=lambda row: -float(row.get("spend") or 0))
        best = candidates[0] if candidates else None
        compare.append(
            {
                "id": staple["id"],
                "label": staple["label"],
                "litoral_desc": staple.get("desc"),
                "litoral_cum_pct": staple.get("cum_pct"),
                "litoral_cagr_pct": staple.get("cagr_pct"),
                "litoral_from": staple.get("from_year"),
                "litoral_to": staple.get("to_year"),
                "personal_desc": best.get("desc") if best else None,
                "personal_cum_pct": best.get("cum_pct") if best else None,
                "personal_ann_pct": best.get("ann_pct") if best else None,
                "personal_from": best.get("from") if best else None,
                "personal_to": best.get("to") if best else None,
                "personal_spend": best.get("spend") if best else None,
                "matched": best is not None and staple.get("found"),
            }
        )
    return compare


def build_payload(receipts: List[dict], validation: dict, personal_json: str) -> dict:
    kept, cnpj_info = filter_litoral_receipts(receipts)
    validation.update(cnpj_info)
    snapshots = snapshot_meta(kept)
    eligible_years = {row["year"] for row in snapshots if row["yoy_eligible"]}
    prices, spend, meta = collect_year_prices(kept)
    medians = median_year_prices(prices)
    products = build_product_rows(medians, spend, meta, eligible_years)
    staples = build_staples(medians, meta, eligible_years)
    basket = equal_weight_staple_index(staples, sorted(eligible_years))
    compare = compare_with_personal(staples, personal_json)

    tracked = [row for row in products if row["years"] >= 2]
    total_spend = sum(item["total"] for receipt in kept for item in receipt["items"])
    first_snap = snapshots[0]["mode_date"] if snapshots else "?"
    last_snap = snapshots[-1]["mode_date"] if snapshots else "?"

    risers = [row for row in tracked if row["cagr_pct"] is not None and row["years"] >= 3]
    risers.sort(key=lambda row: -row["cagr_pct"])
    fallers = sorted(risers, key=lambda row: row["cagr_pct"])[:8]
    risers = risers[:8]

    return {
        "generated_from": (
            f"{len(kept)} NFC-e Litoral (CNPJ {LITORAL_CNPJ}), "
            f"snapshots {first_snap} → {last_snap}"
        ),
        "track": "litoral_store",
        "sampling_note": (
            "Snapshots misturam pastas XML (20XX/ ou NFCE_XML_*, ≈26/dez) e exports SEFAZ NFCE_*.txt "
            "(janelas multi-dia no fim de dezembro / julho). "
            f"O lote {NAMING_DRIFT_YEAR} tem nomenclatura diferente e não entra nas junções YoY."
        ),
        "kpis": {
            "receipts": len(kept),
            "xml_receipts": sum(1 for row in kept if row.get("source") == "xml"),
            "txt_receipts": sum(1 for row in kept if row.get("source") == "txt"),
            "snapshots": len(snapshots),
            "tracked_products": len(tracked),
            "total_spend": round(total_spend, 2),
            "staples_found": sum(1 for staple in staples if staple["found"]),
            "basket_cum_pct": round(basket[-1]["v"] - 100, 1) if basket else None,
            "first_snapshot": first_snap,
            "last_snapshot": last_snap,
        },
        "snapshots": snapshots,
        "basket_index": basket,
        "staples": staples,
        "compare_personal": compare,
        "risers": risers,
        "fallers": fallers,
        "products": products[:500],
        "ipca_note": "IPCA anual (IBGE) como referência; 2025 aproximado, 2026 estimativa.",
    }


def build_cli() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build Litoral store snapshot prices from NFC-e XMLs and SEFAZ TXT exports."
    )
    parser.add_argument(
        "--notes-dir",
        default=DEFAULT_NOTES_DIR,
        help="Directory containing NFCE_XML_* folders and/or NFCE_*.txt exports.",
    )
    parser.add_argument("--output-json", default=DEFAULT_JSON, help="Main analysis JSON output.")
    parser.add_argument("--validation-json", default=DEFAULT_VALIDATION_JSON, help="Validation JSON output.")
    parser.add_argument("--output-html", default=DEFAULT_HTML, help="HTML file to inject data into.")
    parser.add_argument("--personal-json", default=DEFAULT_PERSONAL_JSON, help="Personal inflation JSON for compare panel.")
    parser.add_argument("--skip-html", action="store_true", help="Do not inject data into the HTML file.")
    return parser


def main(argv: List[str] | None = None) -> int:
    args = build_cli().parse_args(argv)
    if not os.path.isdir(args.notes_dir):
        home = os.path.expanduser("~")
        example_source = os.path.join(
            home, "Documents", "GitHub", "LitoralPriceTracker", "data", "raw", "NOTAS_LITORAL"
        )
        print(
            f"notes-dir não encontrado: {args.notes_dir}\n"
            "Crie um symlink, por exemplo:\n"
            f"  ln -sfn {example_source} {DEFAULT_NOTES_DIR}",
            file=sys.stderr,
        )
        return 1

    receipts, validation = load_store_receipts(args.notes_dir)
    data = build_payload(receipts, validation, args.personal_json)
    validation_report = {
        "source_of_truth": "XML under notas_litoral/ (20XX/ or NFCE_XML_*) plus optional NFCE_*.txt SEFAZ exports",
        "track": "litoral_store",
        "validation": validation,
    }

    _json_dump(args.output_json, data)
    _json_dump(args.validation_json, validation_report)
    if not args.skip_html:
        write_html_payload(args.output_html, data, validation_report)

    print(
        f"notas Litoral: {data['kpis']['receipts']} "
        f"(xml={data['kpis']['xml_receipts']} txt={data['kpis']['txt_receipts']})  "
        f"snapshots: {data['kpis']['snapshots']}"
    )
    print(
        f"produtos (≥2 anos): {data['kpis']['tracked_products']}  "
        f"staples: {data['kpis']['staples_found']}/{len(STAPLES)}  "
        f"cesta: {data['kpis']['basket_cum_pct']}% vs base"
    )
    print(f"período: {data['kpis']['first_snapshot']} → {data['kpis']['last_snapshot']}")
    print(f"gravado {os.path.basename(args.output_json)} e {os.path.basename(args.validation_json)}")
    if not args.skip_html and os.path.exists(args.output_html):
        print(f"dados injetados em {os.path.basename(args.output_html)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
