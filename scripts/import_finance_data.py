#!/usr/bin/env python3
"""
Import Personal_Finance data from xlsx/csv into SQLite.

Sources:
  - data/command-center_V2.xlsx (primary for most sheets)
  - data/command-center.xlsx (FX_OPS only, not present in V2)
  - data/spending_aliases.csv
  - data/spending_rules.csv

Target:
  - data/finances.db

Logs:
  - logs/import_finance_data.log
"""

import argparse
import csv
import logging
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import openpyxl

# Absolute paths
PROJECT_DIR = Path("/Users/giovannini.eduardogmail.com/Documents/GitHub/Personal_Finance")
DATA_DIR = PROJECT_DIR / "data"
LOGS_DIR = PROJECT_DIR / "logs"
DB_PATH = DATA_DIR / "finances.db"

SOURCES = {
    "command_center_v2": DATA_DIR / "command-center_V2.xlsx",
    "command_center": DATA_DIR / "command-center.xlsx",
    "spending_aliases": DATA_DIR / "spending_aliases.csv",
    "spending_rules": DATA_DIR / "spending_rules.csv",
}


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------
SCHEMA = """
DROP TABLE IF EXISTS accounts;
DROP TABLE IF EXISTS transactions;
DROP TABLE IF EXISTS fx_operations;
DROP TABLE IF EXISTS subscriptions;
DROP TABLE IF EXISTS pix_transactions;
DROP TABLE IF EXISTS repos;
DROP TABLE IF EXISTS projects;
DROP TABLE IF EXISTS config;
DROP TABLE IF EXISTS monthly_summary;
DROP TABLE IF EXISTS categories;
DROP TABLE IF EXISTS alerts;
DROP TABLE IF EXISTS spending_aliases;
DROP TABLE IF EXISTS spending_rules;

CREATE TABLE accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_file TEXT,
    sheet_name TEXT,
    institution TEXT,
    type TEXT,
    balance_brl REAL,
    balance_usd REAL,
    last_updated TEXT,
    status TEXT,
    notes TEXT
);

CREATE TABLE transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_file TEXT,
    sheet_name TEXT,
    row_num INTEGER,
    tx_date TEXT,
    fatura TEXT,
    merchant TEXT,
    value_brl REAL,
    category TEXT,
    international TEXT
);

CREATE TABLE fx_operations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_file TEXT,
    sheet_name TEXT,
    row_num INTEGER,
    op_date TEXT,
    institution TEXT,
    destination TEXT,
    ccy TEXT,
    fcy_amount REAL,
    brl_amount REAL,
    fx_rate REAL,
    direction TEXT,
    nature TEXT
);

CREATE TABLE subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_file TEXT,
    sheet_name TEXT,
    service TEXT,
    plan TEXT,
    email TEXT,
    ccy TEXT,
    monthly_brl REAL,
    category TEXT,
    dup_risk TEXT,
    decision TEXT,
    renewal_date TEXT,
    status TEXT
);

CREATE TABLE pix_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_file TEXT,
    sheet_name TEXT,
    row_num INTEGER,
    pix_date TEXT,
    type TEXT,
    counterpart TEXT,
    pix_amount REAL,
    fx_amount REAL,
    iof_amount REAL
);

CREATE TABLE repos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_file TEXT,
    sheet_name TEXT,
    name TEXT,
    status TEXT,
    branch TEXT,
    dirty_files TEXT,
    last_commit TEXT,
    days_since INTEGER,
    remote TEXT,
    language TEXT,
    risk_score REAL,
    notes TEXT
);

CREATE TABLE projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_file TEXT,
    sheet_name TEXT,
    project TEXT,
    status TEXT,
    current_focus TEXT,
    blocker TEXT,
    next_action TEXT,
    last_touched TEXT,
    priority TEXT
);

CREATE TABLE config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_file TEXT,
    sheet_name TEXT,
    parameter TEXT,
    value TEXT,
    unit TEXT,
    notes TEXT
);

CREATE TABLE monthly_summary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_file TEXT,
    sheet_name TEXT,
    month TEXT,
    card_spend REAL,
    txs INTEGER,
    pix_out REAL,
    fx_out REAL,
    fx_in REAL,
    iof REAL,
    net_flow REAL
);

CREATE TABLE categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_file TEXT,
    sheet_name TEXT,
    category TEXT,
    total_brl REAL,
    pct_card REAL,
    avg_month REAL,
    txs INTEGER,
    classification TEXT
);

CREATE TABLE alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_file TEXT,
    sheet_name TEXT,
    row_num INTEGER,
    severity TEXT,
    domain TEXT,
    finding TEXT,
    brl_exposure REAL,
    recommended_action TEXT,
    status TEXT
);

CREATE TABLE spending_aliases (
    alias_id TEXT PRIMARY KEY,
    source_description TEXT,
    canonical_description TEXT,
    basis TEXT
);

CREATE TABLE spending_rules (
    rule_id TEXT PRIMARY KEY,
    source TEXT,
    match_type TEXT,
    match_value TEXT,
    category TEXT,
    action TEXT,
    basis TEXT,
    note TEXT
);
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def setup_logging():
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOGS_DIR / "import_finance_data.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.FileHandler(log_path, mode="a"), logging.StreamHandler(sys.stdout)],
    )
    logging.info(f"Logging to {log_path}")


def validate_sources():
    missing = [name for name, path in SOURCES.items() if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing sources: {missing}")
    logging.info("All sources found.")


def to_float(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip().replace("R$", "").replace(",", "_comma_").replace(".", "").replace("_comma_", ".")
    # Keep only last dot for decimals; above is a naive BRL fix. Try direct first.
    try:
        return float(value)
    except (ValueError, TypeError):
        pass
    s = str(value).strip()
    try:
        # European/Brazilian: 1.234,56 -> 1234.56
        if "," in s and "." in s:
            if s.rfind(",") > s.rfind("."):
                s = s.replace(".", "").replace(",", ".")
            else:
                s = s.replace(",", "")
        elif "," in s:
            s = s.replace(",", ".")
        return float(s)
    except (ValueError, TypeError):
        return None


def to_int(value):
    f = to_float(value)
    return int(f) if f is not None else None


def to_text(value):
    if value is None:
        return None
    s = str(value).strip()
    return s if s else None


def to_date(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    s = str(value).strip()
    return s if s else None


def read_sheet_rows(path, sheet_name, header_row=4, stop_at_repeated_header=True):
    """Return list of dicts from an openpyxl sheet.

    If stop_at_repeated_header is True, reading stops when a subsequent row's
    first non-empty value equals the first header name (a new table starts).
    """
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    if sheet_name not in wb.sheetnames:
        raise ValueError(f"Sheet '{sheet_name}' not found in {path.name}")
    ws = wb[sheet_name]
    rows = list(ws.iter_rows(values_only=True))
    if len(rows) < header_row:
        return []
    headers = [to_text(c) for c in rows[header_row - 1]]
    first_header = headers[0] if headers else None
    data = []
    for idx, row in enumerate(rows[header_row:], start=header_row + 1):
        if all(v is None or str(v).strip() == "" for v in row):
            continue
        first_val = next((to_text(v) for v in row if v is not None and str(v).strip() != ""), None)
        if stop_at_repeated_header and first_val and first_val.lower() == (first_header or "").lower() and data:
            break
        record = {}
        for h, v in zip(headers, row):
            if h is not None:
                record[h] = v
        if record:
            record["__row_num"] = idx
            data.append(record)
    return data


def is_empty_row(record):
    return all(v is None or str(v).strip() == "" for k, v in record.items() if not k.startswith("__"))


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------
def load_accounts(conn, dry_run):
    rows = read_sheet_rows(SOURCES["command_center_v2"], "BALANCES")
    inserted = 0
    for r in rows:
        if not r.get("Institution"):
            continue
        data = {
            "source_file": SOURCES["command_center_v2"].name,
            "sheet_name": "BALANCES",
            "institution": to_text(r.get("Institution")),
            "type": to_text(r.get("Type")),
            "balance_brl": to_float(r.get("Balance (BRL)")),
            "balance_usd": to_float(r.get("Balance (USD)")),
            "last_updated": to_date(r.get("Last Updated")),
            "status": to_text(r.get("Status")),
            "notes": to_text(r.get("Notes")),
        }
        if dry_run:
            inserted += 1
            continue
        conn.execute(
            """
            INSERT INTO accounts (source_file, sheet_name, institution, type, balance_brl, balance_usd, last_updated, status, notes)
            VALUES (:source_file, :sheet_name, :institution, :type, :balance_brl, :balance_usd, :last_updated, :status, :notes)
            """,
            data,
        )
        inserted += 1
    logging.info(f"accounts: {inserted} rows")


def load_transactions(conn, dry_run):
    rows = read_sheet_rows(SOURCES["command_center_v2"], "TRANSACTIONS")
    inserted = 0
    for r in rows:
        if not r.get("Merchant"):
            continue
        data = {
            "source_file": SOURCES["command_center_v2"].name,
            "sheet_name": "TRANSACTIONS",
            "row_num": r.get("__row_num"),
            "tx_date": to_date(r.get("Date")),
            "fatura": to_text(r.get("Fatura")),
            "merchant": to_text(r.get("Merchant")),
            "value_brl": to_float(r.get("Value (BRL)")),
            "category": to_text(r.get("Category")),
            "international": to_text(r.get("International")),
        }
        if dry_run:
            inserted += 1
            continue
        conn.execute(
            """
            INSERT INTO transactions (source_file, sheet_name, row_num, tx_date, fatura, merchant, value_brl, category, international)
            VALUES (:source_file, :sheet_name, :row_num, :tx_date, :fatura, :merchant, :value_brl, :category, :international)
            """,
            data,
        )
        inserted += 1
    logging.info(f"transactions: {inserted} rows")


def load_fx_operations(conn, dry_run):
    rows = read_sheet_rows(SOURCES["command_center"], "FX_OPS")
    inserted = 0
    for r in rows:
        if not r.get("Date"):
            continue
        data = {
            "source_file": SOURCES["command_center"].name,
            "sheet_name": "FX_OPS",
            "row_num": r.get("__row_num"),
            "op_date": to_date(r.get("Date")),
            "institution": to_text(r.get("Institution")),
            "destination": to_text(r.get("Destination")),
            "ccy": to_text(r.get("CCY")),
            "fcy_amount": to_float(r.get("FCY Amount")),
            "brl_amount": to_float(r.get("BRL Amount")),
            "fx_rate": to_float(r.get("FX Rate")),
            "direction": to_text(r.get("Direction")),
            "nature": to_text(r.get("Nature")),
        }
        if dry_run:
            inserted += 1
            continue
        conn.execute(
            """
            INSERT INTO fx_operations (source_file, sheet_name, row_num, op_date, institution, destination, ccy, fcy_amount, brl_amount, fx_rate, direction, nature)
            VALUES (:source_file, :sheet_name, :row_num, :op_date, :institution, :destination, :ccy, :fcy_amount, :brl_amount, :fx_rate, :direction, :nature)
            """,
            data,
        )
        inserted += 1
    logging.info(f"fx_operations: {inserted} rows")


def load_subscriptions(conn, dry_run):
    rows = read_sheet_rows(SOURCES["command_center_v2"], "SUBSCRIPTIONS")
    inserted = 0
    for r in rows:
        if not r.get("Service"):
            continue
        data = {
            "source_file": SOURCES["command_center_v2"].name,
            "sheet_name": "SUBSCRIPTIONS",
            "service": to_text(r.get("Service")),
            "plan": to_text(r.get("Plan")),
            "email": to_text(r.get("Email")),
            "ccy": to_text(r.get("CCY")),
            "monthly_brl": to_float(r.get("Monthly BRL")),
            "category": to_text(r.get("Category")),
            "dup_risk": to_text(r.get("Dup Risk")),
            "decision": to_text(r.get("Decision")),
            "renewal_date": to_date(r.get("Renewal Date")),
            "status": to_text(r.get("Status")),
        }
        if dry_run:
            inserted += 1
            continue
        conn.execute(
            """
            INSERT INTO subscriptions (source_file, sheet_name, service, plan, email, ccy, monthly_brl, category, dup_risk, decision, renewal_date, status)
            VALUES (:source_file, :sheet_name, :service, :plan, :email, :ccy, :monthly_brl, :category, :dup_risk, :decision, :renewal_date, :status)
            """,
            data,
        )
        inserted += 1
    logging.info(f"subscriptions: {inserted} rows")


def load_pix_transactions(conn, dry_run):
    rows = read_sheet_rows(SOURCES["command_center_v2"], "PIX")
    inserted = 0
    for r in rows:
        if not r.get("Date"):
            continue
        data = {
            "source_file": SOURCES["command_center_v2"].name,
            "sheet_name": "PIX",
            "row_num": r.get("__row_num"),
            "pix_date": to_date(r.get("Date")),
            "type": to_text(r.get("Type")),
            "counterpart": to_text(r.get("Counterpart")),
            "pix_amount": to_float(r.get("PIX Amount")),
            "fx_amount": to_float(r.get("FX Amount")),
            "iof_amount": to_float(r.get("IOF Amount")),
        }
        if dry_run:
            inserted += 1
            continue
        conn.execute(
            """
            INSERT INTO pix_transactions (source_file, sheet_name, row_num, pix_date, type, counterpart, pix_amount, fx_amount, iof_amount)
            VALUES (:source_file, :sheet_name, :row_num, :pix_date, :type, :counterpart, :pix_amount, :fx_amount, :iof_amount)
            """,
            data,
        )
        inserted += 1
    logging.info(f"pix_transactions: {inserted} rows")


def load_repos(conn, dry_run):
    rows = read_sheet_rows(SOURCES["command_center_v2"], "REPOS")
    inserted = 0
    for r in rows:
        if not r.get("Name"):
            continue
        data = {
            "source_file": SOURCES["command_center_v2"].name,
            "sheet_name": "REPOS",
            "name": to_text(r.get("Name")),
            "status": to_text(r.get("Status")),
            "branch": to_text(r.get("Branch")),
            "dirty_files": to_text(r.get("Dirty Files")),
            "last_commit": to_text(r.get("Last Commit")),
            "days_since": to_int(r.get("Days Since")),
            "remote": to_text(r.get("Remote")),
            "language": to_text(r.get("Language")),
            "risk_score": to_float(r.get("Risk Score")),
            "notes": to_text(r.get("Notes")),
        }
        if dry_run:
            inserted += 1
            continue
        conn.execute(
            """
            INSERT INTO repos (source_file, sheet_name, name, status, branch, dirty_files, last_commit, days_since, remote, language, risk_score, notes)
            VALUES (:source_file, :sheet_name, :name, :status, :branch, :dirty_files, :last_commit, :days_since, :remote, :language, :risk_score, :notes)
            """,
            data,
        )
        inserted += 1
    logging.info(f"repos: {inserted} rows")


def load_projects(conn, dry_run):
    rows = read_sheet_rows(SOURCES["command_center_v2"], "PROJECTS")
    inserted = 0
    for r in rows:
        if not r.get("Project"):
            continue
        data = {
            "source_file": SOURCES["command_center_v2"].name,
            "sheet_name": "PROJECTS",
            "project": to_text(r.get("Project")),
            "status": to_text(r.get("Status")),
            "current_focus": to_text(r.get("Current Focus")),
            "blocker": to_text(r.get("Blocker")),
            "next_action": to_text(r.get("Next Action")),
            "last_touched": to_date(r.get("Last Touched")),
            "priority": to_text(r.get("Priority")),
        }
        if dry_run:
            inserted += 1
            continue
        conn.execute(
            """
            INSERT INTO projects (source_file, sheet_name, project, status, current_focus, blocker, next_action, last_touched, priority)
            VALUES (:source_file, :sheet_name, :project, :status, :current_focus, :blocker, :next_action, :last_touched, :priority)
            """,
            data,
        )
        inserted += 1
    logging.info(f"projects: {inserted} rows")


def load_config(conn, dry_run):
    rows = read_sheet_rows(SOURCES["command_center_v2"], "CONFIG")
    inserted = 0
    for r in rows:
        if not r.get("Parameter"):
            continue
        data = {
            "source_file": SOURCES["command_center_v2"].name,
            "sheet_name": "CONFIG",
            "parameter": to_text(r.get("Parameter")),
            "value": to_text(r.get("Value")),
            "unit": to_text(r.get("Unit")),
            "notes": to_text(r.get("Notes")),
        }
        if dry_run:
            inserted += 1
            continue
        conn.execute(
            """
            INSERT INTO config (source_file, sheet_name, parameter, value, unit, notes)
            VALUES (:source_file, :sheet_name, :parameter, :value, :unit, :notes)
            """,
            data,
        )
        inserted += 1
    logging.info(f"config: {inserted} rows")


def load_monthly_summary(conn, dry_run):
    # V2 only has: Month, Card Spend, Txs, PIX Out, Total Out
    # command-center has: Month, Card Spend, Txs, PIX In, PIX Out, FX Out, FX In, IOF, Net Flow
    # We'll load V2 as primary; if you need the richer version, swap the source.
    import re

    rows_v2 = read_sheet_rows(SOURCES["command_center_v2"], "MONTHLY")
    rows_cc = read_sheet_rows(SOURCES["command_center"], "MONTHLY")
    cc_lookup = {r.get("Month"): r for r in rows_cc if r.get("Month")}
    inserted = 0
    month_re = re.compile(r"^\d{4}-\d{2}$")
    for r in rows_v2:
        month = to_text(r.get("Month"))
        if not month or not month_re.match(month):
            continue
        cc = cc_lookup.get(month, {})
        data = {
            "source_file": SOURCES["command_center_v2"].name,
            "sheet_name": "MONTHLY",
            "month": month,
            "card_spend": to_float(r.get("Card Spend")),
            "txs": to_int(r.get("Txs")),
            "pix_out": to_float(r.get("PIX Out")),
            "fx_out": to_float(cc.get("FX Out")),
            "fx_in": to_float(cc.get("FX In")),
            "iof": to_float(cc.get("IOF")),
            "net_flow": to_float(cc.get("Net Flow")),
        }
        if dry_run:
            inserted += 1
            continue
        conn.execute(
            """
            INSERT INTO monthly_summary (source_file, sheet_name, month, card_spend, txs, pix_out, fx_out, fx_in, iof, net_flow)
            VALUES (:source_file, :sheet_name, :month, :card_spend, :txs, :pix_out, :fx_out, :fx_in, :iof, :net_flow)
            """,
            data,
        )
        inserted += 1
    logging.info(f"monthly_summary: {inserted} rows")


def load_categories(conn, dry_run):
    rows = read_sheet_rows(SOURCES["command_center_v2"], "CATEGORIES")
    inserted = 0
    for r in rows:
        if not r.get("Category"):
            continue
        data = {
            "source_file": SOURCES["command_center_v2"].name,
            "sheet_name": "CATEGORIES",
            "category": to_text(r.get("Category")),
            "total_brl": to_float(r.get("Total (R$)")),
            "pct_card": to_float(r.get("% of Card")),
            "avg_month": to_float(r.get("Avg/Month")),
            "txs": to_int(r.get("Txs")),
            "classification": to_text(r.get("Classification")),
        }
        if dry_run:
            inserted += 1
            continue
        conn.execute(
            """
            INSERT INTO categories (source_file, sheet_name, category, total_brl, pct_card, avg_month, txs, classification)
            VALUES (:source_file, :sheet_name, :category, :total_brl, :pct_card, :avg_month, :txs, :classification)
            """,
            data,
        )
        inserted += 1
    logging.info(f"categories: {inserted} rows")


def load_alerts(conn, dry_run):
    rows = read_sheet_rows(SOURCES["command_center_v2"], "ALERTS")
    inserted = 0
    for r in rows:
        if not r.get("Finding"):
            continue
        data = {
            "source_file": SOURCES["command_center_v2"].name,
            "sheet_name": "ALERTS",
            "row_num": r.get("__row_num"),
            "severity": to_text(r.get("Severity")),
            "domain": to_text(r.get("Domain")),
            "finding": to_text(r.get("Finding")),
            "brl_exposure": to_float(r.get("BRL Exposure")),
            "recommended_action": to_text(r.get("Recommended Action")),
            "status": to_text(r.get("Status")),
        }
        if dry_run:
            inserted += 1
            continue
        conn.execute(
            """
            INSERT INTO alerts (source_file, sheet_name, row_num, severity, domain, finding, brl_exposure, recommended_action, status)
            VALUES (:source_file, :sheet_name, :row_num, :severity, :domain, :finding, :brl_exposure, :recommended_action, :status)
            """,
            data,
        )
        inserted += 1
    logging.info(f"alerts: {inserted} rows")


def load_spending_aliases(conn, dry_run):
    path = SOURCES["spending_aliases"]
    inserted = 0
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if dry_run:
                inserted += 1
                continue
            conn.execute(
                """
                INSERT OR REPLACE INTO spending_aliases (alias_id, source_description, canonical_description, basis)
                VALUES (:alias_id, :source_description, :canonical_description, :basis)
                """,
                row,
            )
            inserted += 1
    logging.info(f"spending_aliases: {inserted} rows")


def load_spending_rules(conn, dry_run):
    path = SOURCES["spending_rules"]
    inserted = 0
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if dry_run:
                inserted += 1
                continue
            conn.execute(
                """
                INSERT OR REPLACE INTO spending_rules (rule_id, source, match_type, match_value, category, action, basis, note)
                VALUES (:rule_id, :source, :match_type, :match_value, :category, :action, :basis, :note)
                """,
                row,
            )
            inserted += 1
    logging.info(f"spending_rules: {inserted} rows")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def run(dry_run=False):
    setup_logging()
    logging.info("=" * 60)
    logging.info(f"Starting import (dry_run={dry_run})")
    validate_sources()

    if not dry_run:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(DB_PATH)
        conn.executescript(SCHEMA)
        conn.commit()
        logging.info(f"Created/reset database: {DB_PATH}")
    else:
        conn = None
        logging.info("DRY RUN: no writes to database")

    loaders = [
        load_accounts,
        load_transactions,
        load_fx_operations,
        load_subscriptions,
        load_pix_transactions,
        load_repos,
        load_projects,
        load_config,
        load_monthly_summary,
        load_categories,
        load_alerts,
        load_spending_aliases,
        load_spending_rules,
    ]

    for loader in loaders:
        try:
            loader(conn, dry_run)
        except Exception as e:
            logging.error(f"Loader {loader.__name__} failed: {e}", exc_info=True)
            if not dry_run:
                conn.close()
            raise

    if not dry_run:
        conn.commit()
        logging.info(f"Committed changes to {DB_PATH}")
        conn.close()

    logging.info("Import complete.")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Import Personal_Finance data into SQLite")
    parser.add_argument("--dry-run", action="store_true", help="Preview import without writing to database")
    args = parser.parse_args()
    try:
        sys.exit(run(dry_run=args.dry_run))
    except Exception as e:
        logging.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
