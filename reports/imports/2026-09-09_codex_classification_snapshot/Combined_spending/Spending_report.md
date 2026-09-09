# Combined spending report

Included spending: **R$201,375.56**. Pending review: **R$70,970.99**, across **81 groups**. Working total includes both confirmed and previously inferred categories.

Latest update: 14 returned answers applied, adding R$18,576.66 to included spending and excluding Banco Topazio R$1,088.90 as US-dollar transfer. Unanswered rows retained. FOOD is preserved as the broad user category.

| Source | Included BRL | Pending BRL |
|---|---:|---:|
| BB | 84792.75 | 5500.52 |
| Inter | 0.00 | 24.75 |
| MP account | 69330.42 | 65445.72 |
| MP card | 47252.39 | 0.00 |

## JSON comparison

All 146 JSON card entries match the reviewed PDF ledger by invoice, date, merchant and amount. All 473 JSON account movements match the account ledger by operation ID, date and signed amount. Five account descriptions differ because of redaction or truncation, without date/amount/ID differences. No JSON transaction added. JSON monthly totals omit installment rows; January zero is missing coverage, not zero spending. JSON card coverage is February–June invoices; account coverage ends June 22.

## Counting and rules

- Existing card decisions and BB decisions preserved. Blank JM answers remain excluded. Prior BB/Inter UNKNOWN - CHECK items remain pending; the instruction to discard blanks applied to the returned JM table only.
- BB rules require recipient identifiers; MP account statements do not carry matching CPF/CNPJ. Unconfirmed name-only candidates are listed for review with the saved category suggested. Their amounts are withheld, so conflicting older inferred categories are not silently counted.
- Named Cursor account charges use Home Office; lottery group payments excluded. Remaining account merchant classifications retain their original inferred status, visible in the ledger basis.
- Two possible BB/MP overlaps: Cristiano Borba da Silva R$100 and Matias Alejandro Sanchez R$88 gross. The latter has R$2 refunded on MP, leaving R$86 withheld. MP copies totaling R$186 net are withheld pending verification; BB copies retained. This is not proof of duplicates.
- Original BB exact duplicates were already removed; Inter screenshots repeat BB records and are not additional bank transactions. Inter CSV/PDF count once. JSON and order-history representations are not added again.
- Card bill settlements, internal transfers, yields and refunds are not consumption. Previously matched refunds reduce retained debit amounts. Full refunds stay excluded. No source records deleted.
- No same-day/amount card-to-MP-account candidates found; date differences or merchant aggregation can hide overlaps. Cross-source identity is not universally proven. Source IDs and references are retained for audit.

## Coverage and files

Card totals use January–June statement months (some purchase dates in 2025). BB and MP account totals use transaction months through September 6; Inter contains one July 9 payment. This is unequal source coverage, not a complete January–September spending estimate. Monthly_totals.csv keeps source separate. Existing July–September card statement coverage is unavailable here.

Use Items_to_review.csv or Items_to_review.md to return decisions. Category_totals_by_source.csv and Combined_ledger.csv provide the traceable totals. Input files remain unchanged; all consolidation changes live in this output folder. Underlying earlier reports are historical snapshots. No automated background import has been configured.
