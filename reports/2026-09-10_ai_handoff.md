# AI handoff — 2026-09-10

Read AI_GUIDE.md, then reports/2026-09-10_spending_method.md. The September 10 ledger/review/monthly CSVs supersede September 9 as current outputs. Historical classifications remain authoritative; do not infer new exclusions from redacted recipient names.

Included spending: R$282,283.73 across 1,192 retained records. The four reviewed ATM withdrawals stay excluded. No new pending review rows. Similar transaction warnings remain unresolved; do not silently remove them.

Use scripts/import_spending.py --batch YYYY-MM-DD for an import and make regen to refresh tab 12. Run python3 -m unittest discover -s scripts/tests -v after importer changes. Repeated imports must preserve output bytes and totals when inputs are unchanged.

This safety update validated available raw sources, not complete historical source coverage. It does not resolve all duplicate warnings or audit all refund associations. No workbook updates were made. Preserve the unrelated command-center_V2.xlsx outside this commit.
