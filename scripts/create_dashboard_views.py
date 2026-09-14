#!/usr/bin/env python3
"""
Create reusable SQLite dashboard views inside finances.db.

These views aggregate raw data into ready-to-query summaries,
so the agent can answer common finance questions quickly.
"""

import logging
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path("/Users/giovannini.eduardogmail.com/Documents/GitHub/Personal_Finance/data/finances.db")
LOG_PATH = Path("/Users/giovannini.eduardogmail.com/Documents/GitHub/Personal_Finance/logs/create_dashboard_views.log")

VIEWS = [
    ("v_total_liquidity", """
        CREATE VIEW v_total_liquidity AS
        SELECT 
            ROUND(SUM(balance_brl), 2) AS total_brl,
            ROUND(SUM(balance_usd), 2) AS total_usd,
            COUNT(*) AS confirmed_accounts
        FROM accounts
        WHERE status = 'CONFIRMED' AND balance_brl IS NOT NULL;
    """),
    ("v_spending_by_category", """
        CREATE VIEW v_spending_by_category AS
        SELECT 
            category,
            COUNT(*) AS tx_count,
            ROUND(SUM(value_brl), 2) AS total_brl,
            ROUND(AVG(value_brl), 2) AS avg_brl
        FROM transactions
        WHERE value_brl < 0
        GROUP BY category
        ORDER BY total_brl ASC;
    """),
    ("v_top_merchants", """
        CREATE VIEW v_top_merchants AS
        SELECT 
            merchant,
            COUNT(*) AS tx_count,
            ROUND(SUM(value_brl), 2) AS total_brl,
            ROUND(AVG(value_brl), 2) AS avg_brl,
            MIN(tx_date) AS first_seen,
            MAX(tx_date) AS last_seen
        FROM transactions
        WHERE value_brl < 0
        GROUP BY merchant
        ORDER BY total_brl ASC
        LIMIT 50;
    """),
    ("v_monthly_outflows", """
        CREATE VIEW v_monthly_outflows AS
        SELECT 
            m.month,
            COALESCE(m.card_spend, 0) AS card_spend,
            COALESCE(m.pix_out, 0) AS pix_out,
            COALESCE(m.fx_out, 0) AS fx_out,
            COALESCE(m.iof, 0) AS iof,
            COALESCE(m.card_spend, 0) + COALESCE(m.pix_out, 0) + COALESCE(m.fx_out, 0) + COALESCE(m.iof, 0) AS total_outflow,
            COALESCE(m.net_flow, 0) AS net_flow
        FROM monthly_summary m
        ORDER BY m.month;
    """),
    ("v_subscription_review", """
        CREATE VIEW v_subscription_review AS
        SELECT 
            service,
            plan,
            monthly_brl,
            decision,
            status,
            category,
            CASE decision
                WHEN 'CANCEL' THEN monthly_brl
                WHEN 'REVIEW' THEN ROUND(monthly_brl * 0.5, 2)
                ELSE 0
            END AS potential_monthly_savings,
            CASE decision
                WHEN 'CANCEL' THEN ROUND(monthly_brl * 12, 2)
                WHEN 'REVIEW' THEN ROUND(monthly_brl * 6, 2)
                ELSE 0
            END AS potential_annual_savings
        FROM subscriptions
        WHERE decision IN ('CANCEL', 'REVIEW')
        ORDER BY potential_monthly_savings DESC;
    """),
    ("v_open_alerts", """
        CREATE VIEW v_open_alerts AS
        SELECT 
            row_num,
            severity,
            domain,
            finding,
            brl_exposure,
            recommended_action,
            status
        FROM alerts
        WHERE status IS NULL OR lower(status) != 'resolved'
        ORDER BY 
            CASE severity
                WHEN 'CRITICAL' THEN 1
                WHEN 'HIGH' THEN 2
                WHEN 'MEDIUM' THEN 3
                WHEN 'LOW' THEN 4
                ELSE 5
            END,
            brl_exposure DESC;
    """),
    ("v_unmatched_card_transactions", """
        CREATE VIEW v_unmatched_card_transactions AS
        SELECT 
            t.tx_date,
            t.merchant,
            t.value_brl,
            t.category
        FROM transactions t
        WHERE t.value_brl < 0
          AND NOT EXISTS (
              SELECT 1 FROM spending_rules r
              WHERE t.merchant LIKE '%' || r.match_value || '%'
          )
        ORDER BY t.tx_date DESC
        LIMIT 100;
    """),
    ("v_fx_operations_summary", """
        CREATE VIEW v_fx_operations_summary AS
        SELECT 
            direction,
            ccy,
            COUNT(*) AS op_count,
            ROUND(SUM(fcy_amount), 2) AS total_fcy,
            ROUND(SUM(brl_amount), 2) AS total_brl,
            ROUND(AVG(fx_rate), 4) AS avg_rate,
            MIN(op_date) AS first_op,
            MAX(op_date) AS last_op
        FROM fx_operations
        GROUP BY direction, ccy
        ORDER BY total_brl DESC;
    """),
]


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.FileHandler(LOG_PATH, mode="a"), logging.StreamHandler(sys.stdout)],
    )
    logging.info("Creating dashboard views...")

    if not DB_PATH.exists():
        logging.error(f"Database not found: {DB_PATH}")
        return 1

    conn = sqlite3.connect(DB_PATH)
    created = 0
    for name, ddl in VIEWS:
        conn.execute(f"DROP VIEW IF EXISTS {name}")
        conn.execute(ddl)
        created += 1
        logging.info(f"Created view: {name}")

    conn.commit()
    conn.close()
    logging.info(f"Done. {created} views created.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
