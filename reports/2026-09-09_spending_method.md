# Spending ledger update — 2026-09-09

Spending ledger updated on 2026-09-09 with the local import workflow. All 1,181 clean-ledger records plus 11 genuinely new raw records were imported. Total included spending is R$288,283.73 (up R$6,000 from the previous clean ledger because four new BB `SOP-BAIRRO BESSA` ATM withdrawals were classified as `CAR`).

Current ledger: `reports/2026-09-09_spending_ledger.csv`. Dashboard input: `reports/2026-09-09_spending_by_month.csv`. Classification rules: `data/spending_rules.csv` (165 rules) and `data/spending_aliases.csv`.

The snapshot under `imports/2026-09-09_codex_classification_snapshot` is historical evidence, not the current ledger. Its 81 pending groups and lower total do not override this repository’s later decisions and wider coverage. No CALC or command-center workbook changes.

## Inherited method and decision history

# Spending ledger — method and decisions · 2026-09-08

**What this is:** a category-by-month spending view for Jan–Sep 2026, built from
`raw/` statements. **It is not a reconciliation.** Point-in-time, like everything
else in `reports/`.

`2026-09-08_spending_by_month.csv` is rendered into bloomberg tab **`12 SPENDING`**
by `regenerate_dashboard.py` (step 8c). `make regen` re-renders the tab from the
newest `reports/*_spending_by_month.csv`; it does **not** rebuild the ledger. To
refresh the tab, write a newer dated CSV in the same format and re-run `make regen`.

**Outputs (this folder):**

| File | Contents |
|---|---|
| `2026-09-08_spending_by_month.csv` | category x month matrix, 9 months |
| `2026-09-08_clean_ledger.csv` | 1.181 classified transactions, one row each |

## Sources

| Source | Coverage | Records |
|---|---|---|
| Banco do Brasil (PIX exports + Jan statement) | 2026-01-08 → 2026-09-06 | 224 |
| Mercado Pago account (full PDF statement) | 2026-01-02 → 2026-09-06 | 643 |
| Mercado Pago card (invoices Jan–Jun) | 2025-11-10 → 2026-06-05 | 215 |
| Mercado Pago card (invoices Jul/Ago/Set — added today) | 2026-06-06 → 2026-09-05 | 94 |
| Banco Inter | 2026-07-09 | 1 |

Card figures use **invoice month**; all other sources use transaction month.

## Verification performed

- Each of the three new card invoices was parsed and its transaction sum
  reconciled **to the cent** against that invoice's own `Consumos de …` header.
- The three new invoices join the existing card ledger with **no gap and no
  overlap** (previous last purchase 05/06; July invoice starts 06/06).
- `Pagamento da fatura` lines are excluded, so card purchases are not
  double-counted against the MP account statement that settles them.

## Decisions applied

Starting point: 1.083 entries carried in `Personal_Finance_AI_Handoff_2026-09-08.json`,
of which R$ 90.636,55 was unclassified across 95 review groups.

| Block | Decision | Source of the decision |
|---|---|---|
| A — 22 recurring counterparties | Mercado Pago recipient = the BB recipient; existing BB category applied | User confirmed 2026-09-08 |
| B — 8 large one-offs | Individually categorised or excluded | User table 2026-09-08 |
| C — 60 items under R$200 with no match | `Other`, counted | User confirmed 2026-09-08 |
| Lottery (`MP*LOTERIASONLINE` and the related person-to-person payments) | **excluded** | Pre-existing saved rule (`Lottery - group payments`) |
| `UBER * PENDING` | **excluded** | Pre-existing saved rule |
| Revolving interest, IOF, late fee | **excluded** | Pre-existing saved rule |
| `Banco Topazio` | **excluded** — remittance, not consumption | Pre-existing exclusion category |

Where a proposed classification conflicted with a saved rule, **the saved rule
won** and the conflict is recorded above rather than resolved silently.

Result: zero pending. Every source transaction is either categorised or
explicitly excluded, with the reason retained in the ledger's `basis` column.

## Known limitations

- **September is partial** — BB and MP account cover 01–06 Sep only, while the
  September card invoice covers 06/08–05/09. Do not compare September to a full
  month.
- Cross-source identity for the Mercado Pago counterparties is **confirmed by the
  user, not proven by CPF/CNPJ** — MP statements do not carry the identifier.
- Three months carry large one-offs (vehicle, travel, a tax payment) that
  dominate their totals. Read the category detail, not just the monthly sum.
- Nothing here feeds `CALC` or `command-center.xlsx`, and tab 12 is display-only.
  Source-of-truth rules in `AI_GUIDE.md` are unchanged.
- Tab 12 treats the **last month as month-to-date** — excluded from Typical Month
  and labelled partial. That is generic behaviour, not a September special case.

## Rebuilding

Starting 2026-09-09 the ledger is maintained by a local, stdlib-only workflow:

```bash
python3 scripts/import_spending.py --batch 2026-MM-DD
```

Inputs are the original statements in `raw/` plus the unified rules in
`data/spending_rules.csv` and `data/spending_aliases.csv`. Outputs:

| File | Contents |
|---|---|
| `reports/<date>_spending_ledger.csv` | Canonical ledger with `original_amount_brl` and `included_amount_brl` |
| `reports/<date>_spending_review.csv` | Pending/ambiguous items with one blank `your_answer` column |
| `reports/<date>_spending_by_month.csv` | Dashboard input for tab `12 SPENDING` |

Run `make regen` afterwards to refresh `bloomberg-terminal.html`.

### Validation performed on 2026-09-09

- The workflow was run against the existing `raw/` statements.
- 622 raw records matched the previous `2026-09-09_clean_ledger.csv`.
- 45 duplicate raw records across overlapping statement exports were skipped.
- 11 genuinely new raw records were imported (mostly the July BB statement and a few MP account lines not in the previous ledger).
- 7 refund pairs were detected and netted (Mercado Livre partial refunds and other purchase/refund pairs).
- The resulting included total is **R$ 288,283.73**.
- 8 review answers from `2026-09-09_spending_review.csv` were applied.
- `make regen` passed: `[ok] all 21 spot-checks passed`.

### Differences from the previous `2026-09-09_clean_ledger.csv`

- **Format:** the canonical ledger now keeps both `original_amount_brl` (statement amount) and `included_amount_brl` (what counts toward spending). Previously only one amount column existed and excluded records were recorded as `0.00`, losing the original value.
- **Blank categories:** 230 legacy records with blank category were classified using saved rules (self-transfers, family transfers, insurance, credit-card payments, income/yield, etc.).
- **Original statement amounts preserved:** excluded records such as credit-card bill payments and self-transfers now show their gross original amount with `included_amount_brl = 0.00`.
- **Source and reason recorded:** every row now has `source_reference`, `rule_id`, `basis`, `review_status`, and `import_batch`.
- **R$ +6,000.00 from new BB records:** four `SOP-BAIRRO BESSA` ATM withdrawals on 2026-07-02/03 were present in the July BB raw statement but not in the previous clean ledger. The user classified them as `CAR` in the review table; a reusable rule (`BB081`) was added so future occurrences are classified automatically.
- **Mercado Livre category changes with no total change:** two February Mercado Livre purchases were reclassified from `Shopping` to `HOME SPENDINGS` and `Home Office` based on the user's review answers. The refund pairs were correctly netted, so the included amount did not change.
- **Pix transfers excluded:** two redacted person-to-person Pix transfers (`Keep out` / `Out`) were excluded from spending with zero included amount.

### Known remaining issues

- `raw/` is missing the original PDF/CSV statements for MP card Jul/Ago/Set and post-June MP account statements, and for most BB months. The current ledger retains these records as legacy data, but they cannot be independently re-imported until the originals are saved.
- The duplicate-key warning still flags a few records that look like real duplicates or overlapping statement exports (e.g. `COMPUTER` on 04/09 and 30/08, `TELEFONICA BRASIL S.A.` on 2026-01-30, `PERPLEXITY` on 2026-06-04, and the two Mercado Livre refund records). These are not double-counted in the total; review the list if you want to clean them up.

