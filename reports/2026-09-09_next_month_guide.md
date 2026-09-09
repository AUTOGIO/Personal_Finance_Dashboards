# Next-month spending-import guide

Use this each month to keep the spending ledger and tab `12 SPENDING` up to date.

## 1. Collect originals

Download the new monthly statements and save them **unchanged** under `raw/`:

| Source | Where to save |
|---|---|
| Banco do Brasil statement(s) | `raw/bb_brasil/extratos/` |
| Mercado Pago account statement | `raw/mercado_pago/extratos/` |
| Mercado Pago card invoice(s) | `raw/mercado_pago/faturas/` |
| Banco Inter statement (if any) | `raw/banco_inter/extratos/` |

Do not edit, rename, or delete previous months. The workflow reads everything in these folders and recognises previously imported rows.

## 2. Run the import workflow

```bash
python3 scripts/import_spending.py --batch 2026-10-09
```

This reads `raw/`, applies `data/spending_rules.csv`, matches against the latest `reports/<date>_spending_ledger.csv`, and writes three dated files in `reports/`.

## 3. Answer the review table

Open `reports/2026-10-09_spending_review.csv`. It contains only genuinely new or ambiguous items with one blank column: `your_answer`.

- Fill a category name (e.g. `Shopping`, `HOME SPENDINGS`, `PERSONAL`) to include the amount in spending.
- Write `exclude` to exclude it from spending.
- Leave blank if you want to defer the decision.

Re-run the workflow to apply your answers:

```bash
python3 scripts/import_spending.py --batch 2026-10-09
```

The workflow loads the previous review table, applies non-empty answers to the ledger, then imports any newer raw statements.

## 4. Refresh the dashboard

```bash
make regen
```

Confirm the last line is `[ok] all N spot-checks passed`. Tab `12 SPENDING` now renders from the newest `reports/*_spending_by_month.csv`.

## 5. If you want to add a reusable rule

Edit `data/spending_rules.csv` and add a row with:

```csv
rule_id,source,match_type,match_value,category,action,basis,note
MPA-999,MP account,exact_recipient,NEW MERCHANT,CATEGORY,include,User confirmed 2026-10-09,Reusable rule
```

Run the workflow again. New rules apply to future imports automatically.

## What not to do

- Do not hand-edit `bloomberg-terminal.html` or `command-center.html`.
- Do not touch `data/wealthcommand.xlsx` (CALC) or the frozen `data/command-center.xlsx` for spending updates.
- Do not reconcile the spending total against net worth, liquidity, or the NFC-e inflation index — they answer different questions.
- Do not delete or overwrite raw statements.

