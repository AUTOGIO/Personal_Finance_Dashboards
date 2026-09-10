#!/usr/bin/env python3
"""
import_spending.py

Local, stdlib-only import-and-classification workflow for the personal spending
ledger. Reads original bank statements from raw/, applies saved rules from
data/spending_rules.csv + data/spending_aliases.csv, recognises previously
imported transactions, handles refunds/installments/exclusions, and writes:

  - reports/<batch>_spending_ledger.csv
  - reports/<batch>_spending_review.csv
  - reports/<date>_spending_by_month.csv

Does not touch CALC, command-center.xlsx, edu_price_analysis, or the dashboards.
Run `make regen` afterwards to refresh tab 12 SPENDING.

Usage:
    python3 scripts/import_spending.py --batch 2026-10-09
    python3 scripts/import_spending.py --batch 2026-10-09 --dry-run
"""

import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = REPO_ROOT / "raw"
RULES_PATH = REPO_ROOT / "data" / "spending_rules.csv"
ALIASES_PATH = REPO_ROOT / "data" / "spending_aliases.csv"
REPORTS_DIR = REPO_ROOT / "reports"
CURRENT_LEDGER_FALLBACK = REPORTS_DIR / "2026-09-09_clean_ledger.csv"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def ddec(s):
    """Parse a Brazilian-formatted decimal to Decimal."""
    if s is None:
        return Decimal("0.00")
    s = str(s).strip()
    if not s:
        return Decimal("0.00")
    # Handle both 1.234,56 and 1234.56
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    return Decimal(s)


def fmt_money(d):
    return f"{d:,.2f}"


def fmt_csv_money(d):
    """Plain numeric string with dot decimal, no thousands separator."""
    return f"{d:.2f}"


def parse_date(s):
    """Return YYYY-MM-DD string from various raw formats."""
    if not s:
        return None
    s = str(s).strip()
    if not s or s in ("00/00/0000",):
        return None
    # YYYY-MM-DD
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    # DD/MM/YYYY or DD/MM/YY
    m = re.match(r"(\d{2})/(\d{2})/(\d{4})", s)
    if m:
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    m = re.match(r"(\d{2})/(\d{2})/(\d{2})", s)
    if m:
        yy = int(m.group(3))
        year = 2000 + yy if yy < 50 else 1900 + yy
        return f"{year}-{m.group(2)}-{m.group(1)}"
    # DD-MM-YYYY
    m = re.match(r"(\d{2})-(\d{2})-(\d{4})", s)
    if m:
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    return None


def normalise_merchant(s):
    if not s:
        return ""
    s = str(s).strip()
    # collapse whitespace, uppercase, strip accents
    s = re.sub(r"\s+", " ", s).upper()
    s = (
        s.replace("Á", "A").replace("À", "A").replace("Ã", "A").replace("Â", "A")
        .replace("É", "E").replace("Ê", "E")
        .replace("Í", "I")
        .replace("Ó", "O").replace("Ô", "O").replace("Õ", "O")
        .replace("Ú", "U")
        .replace("Ç", "C")
    )
    return s


def strip_transaction_prefixes(s):
    """Remove common bank/PIX/card prefixes so 'Pagamento com QR Pix TELEFONICA'
    matches 'TELEFONICA'."""
    s = normalise_merchant(s)
    prefixes = [
        r"^\d{2}/\d{2}(?:\s+\d{2}:\d{2})?\s+",  # BB timestamp "02/07 20:33"
        r"^PIX\s+ENVIADO\s+",
        r"^PAGAMENTO\s+COM\s+QR\s+PIX\s+",
        r"^PAGAMENTO\s+CARTAO\s+DE\s+CREDITO\s+",
        r"^COMPRA\s+INTERNACIONAL\s+EM\s+",
        r"^COMPRA\s+MERCADO\s+LIBRE\s+",
        r"^COMPRA\s+",
        r"^REEMBOLSO\s+COMPRA\s+",
        r"^REEMBOLSO\s+",
        r"^SAQUE\s+DINHEIRO\s+ATM\s+CARTAO\s+",
        r"^DL\s*\*",
        r"^IFD\s*\*",
        r"^MP\s*\*",
        r"^APP\s*\*",
    ]
    for p in prefixes:
        s = re.sub(p, "", s, flags=re.I)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def fingerprint(tx):
    """Stable key for de-duplication using stripped merchant names.
    For MP card, include report_month so purchases with different invoice months
    do not collide."""
    parts = [
        tx["source"],
        tx.get("report_month", "") if tx["source"] == "MP card" else "",
        strip_transaction_prefixes(tx["merchant"]),
        tx.get("date", ""),
        str(tx.get("original_amount_brl", "0.00")),
        tx.get("reference", ""),
    ]
    return "|".join(parts)


def unique_raw_occurrences(txs):
    """Deduplicate repeated exports, preserving multiplicity within each file."""
    counts = Counter()
    seen = set()
    result = []
    for tx in txs:
        fp = fingerprint(tx)
        file_key = (tx.get("source_reference", ""), fp)
        counts[file_key] += 1
        key = (fp, counts[file_key])
        if key not in seen:
            seen.add(key)
            result.append(tx)
    return result


def merchants_match(a, b):
    """True if one stripped merchant contains the other (case-insensitive)."""
    a = strip_transaction_prefixes(a)
    b = strip_transaction_prefixes(b)
    if not a or not b:
        return False
    if a == b:
        return True
    if a in b or b in a:
        return True
    return False


def is_excluded_legacy(r):
    """A legacy clean_ledger row is excluded if its included amount is zero or
    its category is an explicit exclusion category."""
    try:
        inc = ddec(str(r.get("included_amount_brl", r.get("amount_brl", "0"))))
    except Exception:
        inc = Decimal("0.00")
    if inc == 0:
        return True
    cat = (r.get("category", "") or "").upper()
    exclusion_cats = {
        "EXCLUDED - BLANK ANSWER",
        "EXCLUDED - USER INSTRUCTED",
        "LOTTERY - GROUP PAYMENTS",
        "CREDIT-CARD BILL PAYMENTS",
        "CREDIT-CARD BILL PAYMENT",
        "TRANSFERS ABROAD",
        "PHYSICAL US DOLLAR PURCHASE",
        "US DOLLAR TRANSFER - EXCLUDED",
        "FAMILY TRANSFER - BROTHER",
        "FINANCE CHARGE",
        "UNKNOWN - CHECK",
        "CRYPTOCURRENCY",
        "REFUND - EXCLUDED",
        "INCOME/YIELD/REFUND - EXCLUDED",
    }
    return any(ex in cat for ex in exclusion_cats)


def ledger_row_matches_raw(tx, r):
    """Return True if ledger row r corresponds to raw transaction tx,
    ignoring the _raw_matched flag."""
    if r["source"] != tx["source"]:
        return False
    try:
        existing_amt = ddec(str(r.get("original_amount_brl", r.get("included_amount_brl", r.get("amount_brl", "0")))))
    except Exception:
        return False
    amount_ok = existing_amt == tx["original_amount_brl"]
    if tx["source"] == "MP card" and r.get("report_month") != tx.get("report_month"):
        return False
    old_ref = (r.get("_fingerprint") or "").rsplit("|", 1)[-1]
    new_ref = tx.get("reference") or ""
    if old_ref and new_ref and old_ref != new_ref:
        return False
    # A placeholder is not a recipient identity. Require an operation reference.
    redacted = "REDACTED" in normalise_merchant(tx.get("merchant", ""))
    if redacted and not (old_ref and new_ref and old_ref == new_ref):
        return False
    if r.get("date") != tx.get("date"):
        return False
    if not merchants_match(r.get("merchant", ""), tx.get("merchant", "")):
        return False
    # Legacy zero-valued exclusions lost their original amounts; recover once.
    return amount_ok or (existing_amt == 0 and is_excluded_legacy(r))


def find_matching_ledger_row(tx, existing_rows, allow_matched=False):
    """Find an existing ledger row that matches this raw transaction.

    Included records are matched strictly by source + date + stripped merchant + amount.
    Excluded records (credit-card payments, lottery, etc.) are matched by
    source + date + stripped merchant, because the current clean_ledger stored
    0.00 instead of the original amount.
    MP card invoices also fall back to report_month + merchant + amount when the
    legacy purchase date uses invoice-year.
    """
    for r in existing_rows:
        if not allow_matched and r.get("_raw_matched"):
            continue
        if ledger_row_matches_raw(tx, r):
            return r
    return None


def invoice_month_from_date(d):
    """For non-card sources, report_month is just YYYY-MM."""
    if not d:
        return ""
    return d[:7]


def make_record_id(source, seq):
    prefix = {"BB": "BB", "MP account": "MPA", "MP card": "MPC", "Inter": "INT"}.get(
        source, source.replace(" ", "_")
    )
    return f"{prefix}-{seq:05d}"


# ---------------------------------------------------------------------------
# Raw statement parsers
# ---------------------------------------------------------------------------

def parse_bb_csv(path):
    """Banco do Brasil CSV: Data, Lançamento, Detalhes, N° documento, Valor, Tipo Lançamento."""
    txs = []
    with open(path, encoding="utf-8", errors="replace", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            data = parse_date(row.get("Data"))
            if not data:
                continue
            tipo = (row.get("Tipo Lançamento") or "").strip()
            detalhes = (row.get("Detalhes") or "").strip()
            lancamento = (row.get("Lançamento") or "").strip()
            doc = (row.get("N° documento") or "").strip()
            valor = ddec(row.get("Valor"))
            # Skip income / saída reversals that are zero/positive yields
            if lancamento.upper() in ("BB RENDE FÁCIL", "BB RENDE FACIL"):
                continue
            if lancamento.upper() == "S A L D O":
                continue
            # Determine direction: "Saída" = expense (positive absolute)
            if tipo == "Saída":
                amount = -valor if valor < 0 else valor
            elif tipo == "Entrada":
                # Most inflows are excluded later; keep as negative original so refund detection works
                amount = -valor if valor > 0 else valor
            else:
                amount = valor
            merchant = detalhes if detalhes else lancamento
            ref = doc if doc else ""
            txs.append(
                {
                    "source": "BB",
                    "date": data,
                    "merchant": merchant,
                    "original_amount_brl": amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                    "reference": ref,
                    "raw_type": lancamento,
                }
            )
    return txs


def parse_mp_account_csv(path):
    """Mercado Pago account CSV: semicolon-delimited RELEASE_DATE;TRANSACTION_TYPE;REFERENCE_ID;TRANSACTION_NET_AMOUNT;PARTIAL_BALANCE.

    Files contain a short header section (INITIAL_BALANCE...) followed by a blank line
    and then the real RELEASE_DATE header. We skip to the real header before parsing.
    """
    txs = []
    with open(path, encoding="utf-8", errors="replace", newline="") as f:
        lines = f.readlines()

    # Find the line containing the real header
    start = 0
    for i, line in enumerate(lines):
        if "RELEASE_DATE" in line:
            start = i
            break

    delimiter = ";" if ";" in "".join(lines[start:start + 2]) else ","
    reader = csv.DictReader(lines[start:], delimiter=delimiter)
    for row in reader:
        d = parse_date(row.get("RELEASE_DATE"))
        if not d:
            continue
        ttype = (row.get("TRANSACTION_TYPE") or "").strip()
        ref = (row.get("REFERENCE_ID") or "").strip()
        amount = ddec(row.get("TRANSACTION_NET_AMOUNT"))
        # In the CSV positive amounts are credits, negative are debits.
        # We want spending = positive for debits.
        # Net amount already has sign; treat negative as spending, positive as inflow/refund.
        txs.append(
            {
                "source": "MP account",
                "date": d,
                "merchant": ttype,
                "original_amount_brl": (-amount).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                ),
                "reference": ref,
                "raw_type": ttype,
            }
        )
    return txs


def parse_mp_card_json(path):
    """Reads mp_all_data.json or a parsed-fatura JSON. Returns card transactions.
    Preserves the invoice/report month from the source file."""
    j = json.loads(path.read_text(encoding="utf-8"))
    txs = []
    if isinstance(j, dict):
        items = j.get("card_transactions", []) or j.get("transactions", [])
        # Determine report month from file metadata
        period = j.get("period", "")
        if period:
            m = re.match(r"(\d{2})/(\d{4})", period)
            file_report_month = f"{m.group(2)}-{m.group(1)}" if m else None
        else:
            file_report_month = None
    else:
        items = j
        file_report_month = None
    for t in items:
        d = parse_date(t.get("date"))
        if not d:
            continue
        amount = Decimal(str(t.get("amount", 0)))
        merchant = t.get("merchant", "") or ""
        if not merchant and t.get("description"):
            merchant = t.get("description")
        # Use explicit invoice field when present, else file period, else transaction month
        inv = t.get("invoice") or file_report_month
        if inv:
            inv_m = re.match(r"(\d{4})-(\d{2})", str(inv))
            if not inv_m:
                inv_m = re.match(r"(\d{2})/(\d{4})", str(inv))
                report_month = f"{inv_m.group(2)}-{inv_m.group(1)}" if inv_m else invoice_month_from_date(d)
            else:
                report_month = inv
        else:
            report_month = invoice_month_from_date(d)
        txs.append(
            {
                "source": "MP card",
                "date": d,
                "report_month": report_month,
                "merchant": merchant,
                "original_amount_brl": amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                "reference": "",
                "raw_type": "card",
            }
        )
    return txs


def parse_inter_csv(path):
    txs = []
    with open(path, encoding="utf-8", errors="replace", newline="") as f:
        sample = f.read(4096)
        f.seek(0)
        delimiter = ";" if ";" in sample else ","
        reader = csv.DictReader(f, delimiter=delimiter)
        # Strip spaces from fieldnames so "Data Lançamento" -> "Data Lançamento" (no trailing)
        if reader.fieldnames:
            reader.fieldnames = [fn.strip() for fn in reader.fieldnames]
        for row in reader:
            d = parse_date(
                row.get("Data")
                or row.get("Data Lançamento")
                or row.get("data")
                or row.get("DATE")
            )
            if not d:
                continue
            desc = (
                row.get("Histórico")
                or row.get("Descrição")
                or row.get("historico")
                or row.get("descricao")
                or row.get("Description")
                or ""
            ).strip()
            val = ddec(
                row.get("Valor")
                or row.get("Amount")
                or row.get("valor")
            )
            txs.append(
                {
                    "source": "Inter",
                    "date": d,
                    "merchant": desc,
                    "original_amount_brl": (-val).quantize(
                        Decimal("0.01"), rounding=ROUND_HALF_UP
                    ),
                    "reference": "",
                    "raw_type": "",
                }
            )
    return txs


def discover_raw_transactions():
    txs = []
    def add_with_ref(parser, path):
        batch = parser(path)
        ref = str(path.relative_to(REPO_ROOT))
        for tx in batch:
            tx["source_reference"] = ref
        return batch

    # BB
    for p in sorted(RAW_DIR.glob("bb_brasil/extratos/*.csv")):
        txs.extend(add_with_ref(parse_bb_csv, p))
    # MP account CSVs
    for p in sorted(RAW_DIR.glob("mercado_pago/extratos/account_statement-*.csv")):
        txs.extend(add_with_ref(parse_mp_account_csv, p))
    # MP card JSON
    for p in sorted(RAW_DIR.glob("mercado_pago/*.json")):
        if "all_data" in p.name or "parsed" in p.name:
            txs.extend(add_with_ref(parse_mp_card_json, p))
    # Inter
    for p in sorted(RAW_DIR.glob("banco_inter/extratos/*.csv")):
        txs.extend(add_with_ref(parse_inter_csv, p))
    return txs


# ---------------------------------------------------------------------------
# Rules and classification
# ---------------------------------------------------------------------------

def load_rules(path):
    rules = []
    with open(path, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            r["match_value"] = normalise_merchant(r.get("match_value", ""))
            rules.append(r)
    return rules


def load_aliases(path):
    aliases = {}
    with open(path, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            aliases[normalise_merchant(r["source_description"])] = r["canonical_description"]
    return aliases


def apply_aliases(merchant, aliases):
    nm = normalise_merchant(merchant)
    if nm in aliases:
        return aliases[nm]
    # also try stripping common prefixes
    stripped = re.sub(r"^(COMPRA INTERNACIONAL EM|PIX ENVIA DO|PAGAMENTO COM QR PIX)\s+", "", nm, flags=re.I)
    if stripped in aliases:
        return aliases[stripped]
    return merchant


def match_rule(tx, rules):
    """Return first matching rule dict or None."""
    src = tx["source"]
    merchant = tx.get("merchant_norm", "")
    nm = normalise_merchant(merchant)
    for rule in rules:
        if "REDACTED" in nm:
            if (rule["match_type"] != "identifier_contains"
                    or not tx.get("reference")
                    or rule["match_value"] != tx["reference"]):
                continue
        if rule["source"] != src and rule["source"] != "any":
            continue
        mt = rule["match_type"]
        mv = rule["match_value"]
        if mt == "exact_recipient":
            if mv.upper() == nm:
                return rule
        elif mt == "counterparty_contains":
            if mv.upper() in nm:
                return rule
        elif mt == "identifier_contains":
            # identifier can be in merchant or reference
            if mv in (tx.get("reference") or "") or mv in merchant:
                return rule
        elif mt == "prefix_upper":
            if nm.startswith(mv.upper()):
                return rule
        elif mt == "description_contains":
            if mv.upper() in nm:
                return rule
        elif mt == "merchant_contains":
            if mv.upper() in nm:
                return rule
    return None


def is_installment(merchant):
    return bool(re.search(r"PARCELA\s+\d+\s+DE\s+\d+", merchant, re.I))


def installment_root(merchant):
    """Return (base merchant, total parcels) for grouping installments."""
    m = re.search(r"^(.*?)(?:\s+PARCELA\s+\d+\s+DE\s+\d+.*)$", merchant, re.I)
    if m:
        return m.group(1).strip()
    return merchant


# ---------------------------------------------------------------------------
# Refund detection
# ---------------------------------------------------------------------------

def find_refund_pairs(txs, window_days=30):
    """Pair positive spending records with later negative refunds/inflows on the
    same source and stripped merchant, within `window_days`. Partial refunds are
    accepted: the net purchase amount is purchase + refund."""
    positives = [tx for tx in txs if tx["original_amount_brl"] > 0]
    negatives = [tx for tx in txs if tx["original_amount_brl"] < 0]
    pairs = []
    used_pos = set()
    used_neg = set()

    def parse_dt(s):
        try:
            return datetime.strptime(s, "%Y-%m-%d")
        except Exception:
            return None

    def same_merchant_scope(p, n):
        p_merch = strip_transaction_prefixes(p.get("merchant", ""))
        n_merch = strip_transaction_prefixes(n.get("merchant", ""))
        if merchants_match(p_merch, n_merch):
            return True
        # "Reembolso <description>" against "<description>"
        n_raw = n.get("merchant", "").upper()
        if "REEMBOLSO" in n_raw and p_merch and p_merch in n_raw:
            return True
        return False

    for p in positives:
        pid = id(p)
        if pid in used_pos:
            continue
        p_dt = parse_dt(p.get("date", ""))
        if not p_dt:
            continue
        # Greedily attach refunds until the purchase is fully refunded
        remaining = p["original_amount_brl"]
        attached = []
        for n in negatives:
            if remaining <= Decimal("0.005"):
                break
            nid = id(n)
            if nid in used_neg:
                continue
            n_dt = parse_dt(n.get("date", ""))
            if not n_dt:
                continue
            if n_dt < p_dt or (n_dt - p_dt).days > window_days:
                continue
            if p["source"] != n["source"]:
                continue
            if not same_merchant_scope(p, n):
                continue
            refund_amt = abs(n["original_amount_brl"])
            if refund_amt > remaining + Decimal("0.01"):
                # Refund larger than remaining purchase; skip to avoid over-refunding
                continue
            attached.append(n)
            used_neg.add(nid)
            remaining -= refund_amt
        if attached:
            used_pos.add(pid)
            for n in attached:
                pairs.append((p, n))
    return pairs


# ---------------------------------------------------------------------------
# Ledger I/O
# ---------------------------------------------------------------------------

def load_latest_ledger():
    files = sorted(REPORTS_DIR.glob("*_spending_ledger.csv"))
    path = files[-1] if files else CURRENT_LEDGER_FALLBACK
    rows = []
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)
    return rows, path


def load_current_clean_ledger():
    rows = []
    with open(CURRENT_LEDGER_FALLBACK, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)
    return rows


def merge_legacy_ledger(existing_rows):
    """Convert current clean_ledger columns into canonical ledger columns."""
    out = []
    for i, r in enumerate(existing_rows, 1):
        amount = ddec(r.get("amount_brl", "0"))
        out.append(
            {
                "record_id": r.get("record_id") or make_record_id(r.get("source", "?"), i),
                "source": r.get("source", ""),
                "date": r.get("date", ""),
                "report_month": r.get("report_month", ""),
                "merchant": r.get("merchant", ""),
                "original_amount_brl": amount,
                "included_amount_brl": amount,
                "category": r.get("category", ""),
                "action": "include" if amount > 0 else "exclude",
                "basis": r.get("basis", ""),
                "source_reference": "",
                "rule_id": "",
                "review_status": "legacy",
                "import_batch": "2026-09-09",
                "_fingerprint": fingerprint(
                    {
                        "source": r.get("source", ""),
                        "merchant": r.get("merchant", ""),
                        "date": r.get("date", ""),
                        "original_amount_brl": amount,
                        "reference": "",
                    }
                ),
            }
        )
    return out


# ---------------------------------------------------------------------------
# Main workflow
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Import and classify spending statements.")
    parser.add_argument("--batch", default=date.today().isoformat(), help="Batch/date tag for outputs")
    parser.add_argument("--raw-dir", type=Path, default=RAW_DIR)
    parser.add_argument("--rules", type=Path, default=RULES_PATH)
    parser.add_argument("--aliases", type=Path, default=ALIASES_PATH)
    parser.add_argument("--dry-run", action="store_true", help="Do not write files; only report")
    parser.add_argument("--legacy-fallback", action="store_true", default=True,
                        help="Include legacy clean_ledger rows when raw originals are missing")
    args = parser.parse_args()

    print(f"[info] batch: {args.batch}")
    print(f"[info] raw dir: {args.raw_dir}")

    rules = load_rules(args.rules)
    aliases = load_aliases(args.aliases)
    print(f"[info] loaded {len(rules)} rules, {len(aliases)} aliases")

    # Load state
    existing_ledger, existing_path = load_latest_ledger()
    print(f"[info] loaded existing ledger from {existing_path.name}: {len(existing_ledger)} rows")

    # If the latest ledger is the clean_ledger fallback, canonicalise it
    if existing_path.name == CURRENT_LEDGER_FALLBACK.name:
        canonical_existing = merge_legacy_ledger(existing_ledger)
    else:
        canonical_existing = [
            {
                "record_id": r.get("record_id"),
                "source": r.get("source"),
                "date": r.get("date"),
                "report_month": r.get("report_month"),
                "merchant": r.get("merchant"),
                "original_amount_brl": ddec(r.get("original_amount_brl", "0")),
                "included_amount_brl": ddec(r.get("included_amount_brl", "0")),
                "category": r.get("category", ""),
                "action": r.get("action", ""),
                "basis": r.get("basis", ""),
                "source_reference": r.get("source_reference", ""),
                "rule_id": r.get("rule_id", ""),
                "review_status": r.get("review_status", ""),
                "import_batch": r.get("import_batch", ""),
                "_fingerprint": r.get("_fingerprint", ""),
            }
            for r in existing_ledger
        ]

    # Apply saved rules to legacy records that still have a blank category
    blank_classified = 0
    for r in canonical_existing:
        if r.get("category", "").strip():
            continue
        tx = {
            "source": r.get("source", ""),
            "merchant": r.get("merchant", ""),
            "merchant_norm": apply_aliases(r.get("merchant", ""), aliases),
            "original_amount_brl": ddec(str(r.get("original_amount_brl", r.get("included_amount_brl", "0")))),
        }
        rule = match_rule(tx, rules)
        if rule:
            r["category"] = rule["category"]
            r["action"] = rule["action"]
            r["basis"] = rule["basis"]
            r["rule_id"] = rule["rule_id"]
            if rule["action"] == "exclude":
                r["included_amount_brl"] = Decimal("0.00")
            elif rule["action"] == "include":
                r["included_amount_brl"] = ddec(str(r.get("original_amount_brl", r.get("included_amount_brl", "0"))))
            r["review_status"] = "rule"
            blank_classified += 1
    if blank_classified:
        print(f"[info] classified {blank_classified} blank legacy records via saved rules")

    # Note: review answers are applied after new raw records are classified so that
    # answers for genuinely new transactions can be matched and resolved.
    review_path_prev, review_rows_prev = load_latest_review()
    if review_path_prev:
        print(f"[info] loaded previous review table: {review_path_prev.name}")

    initial_record_ids = {r["record_id"] for r in canonical_existing}

    # Discover and parse raw transactions
    discovered_txs = discover_raw_transactions()
    raw_txs = unique_raw_occurrences(discovered_txs)
    print(f"[info] discovered {len(raw_txs)} raw transactions")
    by_source = Counter(t["source"] for t in raw_txs)
    for src, n in sorted(by_source.items()):
        print(f"       {src}: {n}")

    # Apply aliases and match against existing ledger rows to avoid duplicates
    new_txs = []
    matched_count = 0
    duplicate_raw_count = len(discovered_txs) - len(raw_txs)
    for tx in raw_txs:
        tx["merchant_norm"] = apply_aliases(tx["merchant"], aliases)
        tx["_fingerprint"] = fingerprint(tx)
        existing = find_matching_ledger_row(tx, canonical_existing)
        if existing:
            existing["_raw_matched"] = True
            existing["_fingerprint"] = tx["_fingerprint"]
            existing["source_reference"] = tx.get("source_reference", "")
            # Preserve the original statement amount when the legacy ledger only
            # stored the included amount (0.00 for exclusions).
            try:
                existing_orig = ddec(str(existing.get("original_amount_brl", existing.get("included_amount_brl", "0"))))
            except Exception:
                existing_orig = Decimal("0.00")
            if existing_orig == 0 and tx["original_amount_brl"] != 0:
                existing["original_amount_brl"] = tx["original_amount_brl"]
            # Refresh merchant with the normalised raw form when legacy is blank/generic
            if not existing.get("merchant") or existing["merchant"] in ("", "?"):
                existing["merchant"] = tx["merchant_norm"]
            matched_count += 1
            continue
        new_txs.append(tx)

    print(f"[info] raw transactions matching existing ledger: {matched_count}")
    print(f"[info] duplicate raw records skipped: {duplicate_raw_count}")
    print(f"[info] raw candidates requiring refund/classification handling: {len(new_txs)}")

    # Refund detection on ALL raw transactions before matching to ledger,
    # because legacy clean_ledger does not preserve refund counterpart records.
    raw_refund_pairs = find_refund_pairs(raw_txs)
    raw_refund_ids = {id(n) for _, n in raw_refund_pairs}
    raw_payment_ids = {id(p) for p, _ in raw_refund_pairs}
    refunds_for_payment = defaultdict(list)
    pair_by_tx = {}
    for p, n in raw_refund_pairs:
        refunds_for_payment[id(p)].append(n)
        pair_by_tx[id(n)] = p

    # Classify genuinely new transactions
    review_items = []
    seq = len(canonical_existing) + 1
    for tx in new_txs:
        rule = match_rule(tx, rules)
        original = tx["original_amount_brl"]
        report_month = tx.get("report_month") or invoice_month_from_date(tx["date"])
        record = {
            "record_id": make_record_id(tx["source"], seq),
            "source": tx["source"],
            "date": tx["date"],
            "report_month": report_month,
            "merchant": tx["merchant_norm"],
            "original_amount_brl": original,
            "source_reference": tx.get("source_reference", ""),
            "_fingerprint": tx["_fingerprint"],
            "import_batch": args.batch,
        }

        if id(tx) in raw_payment_ids:
            # This is the gross purchase side of one or more refunds. Net it.
            refunds = refunds_for_payment[id(tx)]
            net = original + sum(n["original_amount_brl"] for n in refunds)
            refund_ids_str = ", ".join(str(n.get("source_reference", "")) for n in refunds)

            # Match the net amount to an existing ledger row if possible. If found,
            # reuse that row instead of creating a duplicate purchase record.
            tmp = dict(tx)
            tmp["original_amount_brl"] = net
            existing_net = find_matching_ledger_row(tmp, canonical_existing)

            if existing_net:
                existing_net["_raw_matched"] = True
                existing_net["source_reference"] = tx.get("source_reference", "")
                existing_net["original_amount_brl"] = original
                existing_net["included_amount_brl"] = net.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                existing_net["basis"] = f"Net of refunds {refund_ids_str}"
                if rule:
                    existing_net["category"] = rule["category"]
                    existing_net["rule_id"] = rule["rule_id"]
                    existing_net["review_status"] = "rule"
                purchase_record_id = existing_net["record_id"]
            else:
                record["included_amount_brl"] = net.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                record["category"] = (rule["category"] if rule else suggest_category(tx, canonical_existing)) or ""
                record["action"] = "include"
                record["basis"] = f"Net of refund(s) {refund_ids_str}"
                record["rule_id"] = rule["rule_id"] if rule else ""
                record["review_status"] = "rule" if rule else "pending"
                if not rule:
                    review_items.append(
                        {
                            "item_id": f"REV-{len(review_items)+1:03d}",
                            "source": tx["source"],
                            "date": tx["date"],
                            "report_month": report_month,
                            "merchant": tx["merchant_norm"],
                            "original_amount_brl": net,
                            "suggested_category": record["category"],
                            "reason_for_review": "Refund net amount has no matching rule",
                            "your_answer": "",
                        }
                    )
                canonical_existing.append(record)
                seq += 1
                purchase_record_id = record["record_id"]

            # Add each refund record (refund counterpart records are new raw data).
            for refund in refunds:
                if find_matching_ledger_row(refund, canonical_existing, allow_matched=True):
                    continue
                refund_record = {
                    "record_id": make_record_id(refund["source"], seq),
                    "source": refund["source"],
                    "date": refund["date"],
                    "report_month": refund.get("report_month") or invoice_month_from_date(refund["date"]),
                    "merchant": refund.get("merchant_norm") or apply_aliases(refund["merchant"], aliases),
                    "original_amount_brl": refund["original_amount_brl"],
                    "included_amount_brl": Decimal("0.00"),
                    "category": "Refund - excluded",
                    "action": "exclude",
                    "basis": f"Refund for purchase {purchase_record_id}",
                    "source_reference": refund.get("source_reference", ""),
                    "rule_id": "",
                    "review_status": "auto",
                    "_fingerprint": fingerprint(refund),
                    "import_batch": args.batch,
                }
                canonical_existing.append(refund_record)
                seq += 1
            continue

        if id(tx) in raw_refund_ids:
            # Refunds were handled above with their paired purchase.
            continue

        if rule:
            record["category"] = rule["category"]
            record["action"] = rule["action"]
            record["basis"] = rule["basis"]
            record["rule_id"] = rule["rule_id"]
            record["review_status"] = "rule"
            if rule["action"] == "exclude":
                record["included_amount_brl"] = Decimal("0.00")
            elif rule["action"] == "defer":
                record["included_amount_brl"] = Decimal("0.00")
                record["review_status"] = "pending"
            else:
                record["included_amount_brl"] = original
        elif original <= 0:
            # Credits, yields, and inflows are not spending by default
            record["category"] = "Income/yield/refund - excluded"
            record["action"] = "exclude"
            record["basis"] = "Negative or zero net amount; treated as inflow/refund"
            record["rule_id"] = ""
            record["review_status"] = "auto"
            record["included_amount_brl"] = Decimal("0.00")
        else:
            # Suggest category from similar merchant in existing ledger
            suggestion = suggest_category(tx, canonical_existing)
            record["category"] = suggestion or ""
            record["action"] = "defer"
            record["included_amount_brl"] = Decimal("0.00")
            record["basis"] = "No matching rule"
            record["rule_id"] = ""
            record["review_status"] = "pending"
            review_items.append(
                {
                    "item_id": f"REV-{len(review_items)+1:03d}",
                    "source": tx["source"],
                    "date": tx["date"],
                    "report_month": report_month,
                    "merchant": tx["merchant_norm"],
                    "original_amount_brl": original,
                    "suggested_category": suggestion,
                    "reason_for_review": "No matching rule or ambiguous merchant",
                    "your_answer": "",
                }
            )

        canonical_existing.append(record)
        seq += 1

    # Legacy fallback: add clean_ledger rows whose fingerprint is not in canonical
    if args.legacy_fallback and existing_path.name != CURRENT_LEDGER_FALLBACK.name:
        clean_rows = load_current_clean_ledger()
        legacy = merge_legacy_ledger(clean_rows)
        existing_ids = {r["record_id"] for r in canonical_existing}
        for r in legacy:
            if r["record_id"] not in existing_ids:
                canonical_existing.append(r)

    # Apply answers from the previous review table now that all records exist.
    if review_path_prev:
        apply_review_answers(canonical_existing, review_rows_prev)

    # Sort by source, date
    canonical_existing.sort(key=lambda r: (r["source"] or "", r["date"] or "", r["record_id"]))

    # Aggregate spending by month
    months = sorted({r["report_month"] for r in canonical_existing if r["report_month"]})
    cats = defaultdict(lambda: {m: Decimal("0.00") for m in months})
    for r in canonical_existing:
        if r["action"] != "include":
            continue
        m = r["report_month"]
        if not m:
            continue
        cats[r["category"]][m] += ddec(str(r["included_amount_brl"]))

    monthly_totals = {m: Decimal("0.00") for m in months}
    for cat_values in cats.values():
        for m, v in cat_values.items():
            monthly_totals[m] += v

    # Detect duplicates inside the output ledger (same source+merchant+date+original_amount)
    dup_check = Counter(
        (r["source"], r["date"], normalise_merchant(r["merchant"]), str(r["original_amount_brl"]))
        for r in canonical_existing
    )
    duplicates = {k: v for k, v in dup_check.items() if v > 1}

    # Report
    print("\n[summary]")
    print(f"  canonical ledger rows: {len(canonical_existing)}")
    print(f"  new ledger rows added: {len({r['record_id'] for r in canonical_existing} - initial_record_ids)}")
    print(f"  new pending review items this batch: {len(review_items)}")
    print(f"  refund pairs detected: {len(raw_refund_pairs)}")
    print(f"  duplicate keys:        {len(duplicates)}")
    total_included = sum(
        ddec(str(r["included_amount_brl"])) for r in canonical_existing if r["action"] == "include"
    )
    print(f"  total included:        R$ {fmt_money(total_included)}")

    if duplicates:
        print("\n[warn] duplicate keys detected (source+date+merchant+amount):")
        for k, v in sorted(duplicates.items(), key=lambda x: -x[1]):
            print(f"  {v}x | {k[0]} {k[1]} {k[2][:40]} R$ {k[3]}")

    if args.dry_run:
        print("\n[dry-run] no files written")
        return

    # Write outputs
    ledger_path = REPORTS_DIR / f"{args.batch}_spending_ledger.csv"
    review_path = REPORTS_DIR / f"{args.batch}_spending_review.csv"
    monthly_path = REPORTS_DIR / f"{args.batch}_spending_by_month.csv"

    ledger_fields = [
        "record_id",
        "source",
        "date",
        "report_month",
        "merchant",
        "original_amount_brl",
        "included_amount_brl",
        "category",
        "action",
        "basis",
        "source_reference",
        "rule_id",
        "review_status",
        "import_batch",
        "_fingerprint",
    ]
    with open(ledger_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=ledger_fields)
        w.writeheader()
        for r in canonical_existing:
            w.writerow({k: r.get(k, "") for k in ledger_fields})

    # Collect review items from all pending/deferred records in the ledger,
    # not just brand-new ones, so previously unanswered items stay visible.
    final_review_items = []
    seen_review_keys = set()
    for r in canonical_existing:
        if r.get("review_status") not in ("pending", "defer") and r.get("action") != "defer":
            continue
        key = (r.get("source"), r.get("date"), r.get("merchant"), str(r.get("original_amount_brl", "0")))
        if key in seen_review_keys:
            continue
        seen_review_keys.add(key)
        final_review_items.append(
            {
                "item_id": f"REV-{len(final_review_items)+1:03d}",
                "source": r.get("source", ""),
                "date": r.get("date", ""),
                "report_month": r.get("report_month", ""),
                "merchant": r.get("merchant", ""),
                "original_amount_brl": r.get("original_amount_brl", ""),
                "suggested_category": r.get("category", ""),
                "reason_for_review": r.get("basis", "No matching rule or ambiguous merchant"),
                "your_answer": "",
            }
        )
    print(f"  total pending review items: {len(final_review_items)}")

    review_fields = [
        "item_id",
        "source",
        "date",
        "report_month",
        "merchant",
        "original_amount_brl",
        "suggested_category",
        "reason_for_review",
        "your_answer",
    ]
    with open(review_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=review_fields)
        w.writeheader()
        w.writerows(final_review_items)

    # Monthly CSV in same shape as current
    with open(monthly_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["category"] + months + ["TOTAL"])
        sorted_cats = sorted(cats.items(), key=lambda x: -sum(x[1].values()))
        for cat, vals in sorted_cats:
            row = [cat] + [fmt_csv_money(vals[m]) for m in months] + [fmt_csv_money(sum(vals.values()))]
            w.writerow(row)
        total_row = ["TOTAL"] + [fmt_csv_money(monthly_totals[m]) for m in months] + [
            fmt_csv_money(sum(monthly_totals.values()))
        ]
        w.writerow(total_row)

    print(f"\n[write] {ledger_path.name}")
    print(f"[write] {review_path.name}")
    print(f"[write] {monthly_path.name}")
    print("\nNext: review the review table, then run `make regen` to refresh tab 12 SPENDING.")


def suggest_category(tx, existing_rows):
    """Simple suggestion: find most common category for same normalised merchant."""
    nm = normalise_merchant(tx["merchant"])
    counts = Counter()
    for r in existing_rows:
        if normalise_merchant(r.get("merchant", "")) == nm and r.get("category"):
            counts[r["category"]] += 1
    if counts:
        return counts.most_common(1)[0][0]
    return ""


def load_latest_review():
    files = sorted(REPORTS_DIR.glob("*_spending_review.csv"))
    if not files:
        return None, []
    path = files[-1]
    rows = []
    with open(path, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            rows.append(r)
    return path, rows


def normalize_review_category(answer):
    """Map free-form user answers to canonical category names."""
    mapping = {
        "car": "CAR",
        "CAR": "CAR",
        "home": "HOME SPENDINGS",
        "HOME SPENDINGS": "HOME SPENDINGS",
        "home office": "Home Office",
        "homeoffice": "Home Office",
        "Home Office": "Home Office",
        "personal": "PERSONAL",
        "shopping": "Shopping",
        "groceries": "Groceries",
        "travel": "Travel",
        "other": "Other",
        "restaurants": "Restaurants",
        "bills": "Bills/utilities",
        "utilities": "Bills/utilities",
        "health": "Health/pharmacy",
        "pharmacy": "Health/pharmacy",
        "subscriptions": "Subscriptions/software",
        "software": "Subscriptions/software",
        "transport": "Transport/fuel",
        "fuel": "Transport/fuel",
    }
    key = answer.strip()
    # Try exact match preserving user casing, then lowercased.
    if key in mapping:
        return mapping[key]
    if key.lower() in mapping:
        return mapping[key.lower()]
    return key


def apply_review_answers(existing_rows, review_rows):
    """Apply non-empty answers from the most recent review CSV to matching ledger rows.

    Preserves already-computed included_amount_brl (e.g. net refund amounts) and
    only overwrites it when the row is currently excluded or has no included amount.
    """
    applied = 0
    for ans in review_rows:
        answer = (ans.get("your_answer") or "").strip()
        if not answer:
            continue
        src = ans.get("source", "")
        dt = ans.get("date", "")
        merch = ans.get("merchant", "")
        try:
            amt = ddec(str(ans.get("original_amount_brl", "0")))
        except Exception:
            continue
        for r in existing_rows:
            if r.get("source") != src:
                continue
            if r.get("date") != dt:
                continue
            if not merchants_match(r.get("merchant", ""), merch):
                continue
            try:
                row_amt = ddec(str(r.get("original_amount_brl", r.get("included_amount_brl", "0"))))
            except Exception:
                row_amt = Decimal("0.00")
            if abs(row_amt - amt) > Decimal("0.05"):
                continue
            # Treat common exclusion words as exclude.
            exclusion_words = {"EXCLUDE", "KEEP OUT", "OUT", "REMOVE", "SKIP", "DELETE"}
            if answer.upper() in exclusion_words:
                r["action"] = "exclude"
                r["included_amount_brl"] = Decimal("0.00")
                r["category"] = "User excluded"
                r["review_status"] = "manual"
                r["basis"] = f"User review answer: {answer} (from {ans.get('item_id','')})"
            else:
                category = normalize_review_category(answer)
                r["action"] = "include"
                r["category"] = category
                # Preserve net/refund-adjusted included amounts; only populate from
                # the statement amount when the row had no included amount or was excluded.
                current_included = r.get("included_amount_brl")
                try:
                    current_included_dec = ddec(str(current_included)) if current_included not in (None, "") else Decimal("0.00")
                except Exception:
                    current_included_dec = Decimal("0.00")
                if r.get("action") == "exclude" or current_included_dec == Decimal("0.00"):
                    try:
                        r["included_amount_brl"] = ddec(str(r.get("original_amount_brl", "0")))
                    except Exception:
                        r["included_amount_brl"] = row_amt
                r["review_status"] = "manual"
                r["basis"] = f"User review answer: {answer} -> {category} (from {ans.get('item_id','')})"
            applied += 1
            break
    if applied:
        print(f"[info] applied {applied} review-answer(s) from previous review table")
    return applied


if __name__ == "__main__":
    main()
