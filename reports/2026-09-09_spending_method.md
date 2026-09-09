# Spending ledger update — 2026-09-09

Eight explicit category decisions from the Codex conversation applied by record ID. Amounts, all 1181 records and July–September coverage retained. Total remains R$282283.73; all monthly totals unchanged. See 2026-09-09_classification_updates.csv for exact changes.

Current ledger: 2026-09-09_clean_ledger.csv. Dashboard input: 2026-09-09_spending_by_month.csv. Additional reusable MP account rules: 2026-09-09_mp_account_classification_rules.csv.

The snapshot under imports/2026-09-09_codex_classification_snapshot is historical evidence, not the current ledger. Its 81 pending groups and lower total do not override this repository’s later decisions and wider coverage. No CALC or command-center workbook changes.

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

There is no generator for this. It was a one-off analysis over `raw/`. If it is
repeated, the inputs are the statements listed above plus the saved
classification rules in `Personal_Finance_AI_Handoff_2026-09-08.json`.
