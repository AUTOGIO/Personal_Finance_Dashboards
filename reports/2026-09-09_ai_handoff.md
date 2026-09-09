# AI-readable handoff — 2026-09-09

## Context for the next Codex / ChatGPT / Claude / Cursor task

This repository now has a local, stdlib-only spending import-and-classification
workflow. The user approved and implemented it on 2026-09-09. The task was to:

1. Audit the current spending ledger for duplicates, coverage gaps, inconsistent
categories, and conflicts with explicit user answers.
2. Build a small local workflow that preserves raw statements, recognises
previously imported transactions, applies saved rules, handles
installments/refunds/exclusions, records the reason for every classification,
and puts genuinely new/ambiguous items into a review table with one blank answer
column.
3. Validate the workflow against existing statements and explain differences from
the previous ledger without silently changing historical totals.
4. Produce a next-month guide and an AI-readable handoff.

## Authoritative sources

| File | Purpose |
|---|---|
| `reports/2026-09-09_spending_method.md` | Method, validation, and known limitations |
| `reports/2026-09-09_clean_ledger.csv` | Legacy ledger (1,181 rows) — retained for reference |
| `reports/2026-09-09_spending_ledger.csv` | New canonical ledger (1,192 rows) |
| `reports/2026-09-09_spending_review.csv` | Pending/ambiguous items awaiting user answer (currently empty) |
| `reports/2026-09-09_spending_by_month.csv` | Dashboard input for tab `12 SPENDING` |
| `data/spending_rules.csv` | Unified classification rules (165 rules) |
| `data/spending_aliases.csv` | Merchant normalisation aliases (4 rules) |
| `scripts/import_spending.py` | The workflow script |

## Key constraints

- Do not touch `CALC`, `data/wealthcommand.xlsx`, the frozen
  `data/command-center.xlsx`, or `edu_price_analysis`.
- Do not hand-edit the HTML dashboards.
- Preserve all originals in `raw/`; never auto-delete them.
- Saved rules in `data/spending_rules.csv` win over fresh judgement.
- Spending data is point-in-time and **not** a reconciliation against wealth
  balances or the NFC-e inflation index.
- Tab `12 SPENDING` is rendered by `scripts/regenerate_dashboard.py` from the
  newest `reports/*_spending_by_month.csv`.

## Workflow script usage

```bash
python3 scripts/import_spending.py --batch 2026-10-09
make regen
```

The script loads the latest `reports/*_spending_ledger.csv` and
`reports/*_spending_review.csv`, applies any non-empty `your_answer` entries,
imports new statements from `raw/`, applies rules, detects refund pairs, and writes
new dated ledger/review/monthly CSVs.

## Validation result on 2026-09-09

- Ran against existing `raw/` statements.
- 622 raw records matched the previous clean ledger.
- 45 duplicate raw records across overlapping exports were skipped.
- 11 genuinely new raw records imported (mostly July BB statement).
- 7 refund pairs detected and netted (including Mercado Livre partial refunds).
- 8 review answers applied from `reports/2026-09-09_spending_review.csv`.
- Included total: **R$ 288,283.73** (up R$6,000 from the previous clean ledger due to four new BB `SOP-BAIRRO BESSA` `CAR` records; all other changes were category reclassifications or exclusions with no total change).
- `make regen` passed: `[ok] all 21 spot-checks passed`.

## Known open items

- `raw/` is missing originals for MP card Jul/Ago/Set invoices, post-June MP
  account statements, and most BB months. Legacy records are preserved in the
  canonical ledger but cannot be independently re-imported until originals are
  saved.
- A few duplicate-key warnings remain for records that look like overlapping
  statement exports (e.g. `COMPUTER` on 04/09 and 30/08, `TELEFONICA BRASIL
  S.A.` on 2026-01-30, `PERPLEXITY` on 2026-06-04, and the two Mercado Livre
  refund records). They are not double-counted in the total.

## Next task for another AI

If the user asks to continue, the next step is typically one of:

1. **Import a new month** — collect new raw statements, run the workflow with a
   new `--batch` date, answer any new rows in the review table, and run `make regen`.
2. **Add a saved rule** — update `data/spending_rules.csv`, re-run the workflow,
   verify the total is unchanged or explain why it changed.
3. **Audit duplicates** — investigate the remaining duplicate-key warnings and
   decide whether each is a real duplicate or two separate transactions.
4. **Answer the review table** — only needed if `reports/2026-09-09_spending_review.csv`
   is non-empty; currently it is empty.

Always run `make regen` after workflow changes and confirm the spot-checks pass.

