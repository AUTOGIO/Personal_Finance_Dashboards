# Spending import safety update — 2026-09-10

Extends reports/2026-09-09_spending_method.md; prior user classifications and exclusions remain authoritative.

## Current result

The canonical files are reports/2026-09-10_spending_ledger.csv, reports/2026-09-10_spending_review.csv, and reports/2026-09-10_spending_by_month.csv. All 1,192 record IDs, categories, actions, and included amounts were preserved relative to the corrected September 9 ledger. Included spending is R$282,283.73; the review table has no pending rows.

The four reviewed ATM withdrawals remain excluded (R$6,000 total), with original amounts retained. Specific operation rules exclude these four; future SOP-BAIRRO BESSA withdrawals defer for review.

## Changes

- Redacted recipient placeholders cannot inherit merchant rules. A redacted transaction requires an exact, nonempty operation reference for an identifier rule or legacy match.
- Exact recipient rules now require equality. Duplicate matching requires the same date and exact original amount; MP card invoice months must agree. Conflicting operation references cannot match.
- Each existing row is consumed once per import. Export deduplication preserves the maximum multiplicity of an identical fingerprint within an export, so repeated same-day charges are retained. Invoice months distinguish installments.
- Matched raw operation fingerprints are retained for subsequent imports. Legacy fallback preserves record IDs instead of reintroducing rows whose amounts were recovered.
- Already represented refund counterparts are not appended again. Import logging reports actual newly added ledger rows.
- MP account-109 gross amount is corrected to R$200.00, with included spending still R$199.99 after its R$0.01 refund. Evidence: operation 143599485605, January 31, 2026, debit and corresponding credit in the source extraction. No category or spending change.

## Verification

- 11 importer regression tests and 3 dashboard regression tests passed.
- Two live imports produced byte-identical ledger, review, and monthly outputs, adding zero records.
- All original record IDs, categories, actions, and included amounts were compared and preserved.
- Dashboard regeneration passed all 21 spot checks. Browser interaction was not tested.

## Limits

Raw coverage remains partial; only available raw sources were re-imported. Legacy records without current raw sources were retained. There are 19 duplicate-key warning groups; these are candidates, not proven duplicates. Their amounts remain as previously classified. This update does not certify every historical repeated charge or every refund pairing.

For exports lacking transaction IDs, matching identical dates, merchants and amounts across files assumes overlapping exports. Independent identical payments split across such files cannot be distinguished from duplicates with those fields alone; review source evidence before removal. Legacy merchant prefix/substring compatibility remains, with stricter date, amount, invoice and reference constraints.

Raw originals, workbooks, the command-center dashboard and edu_price_analysis were not changed. The untracked command-center_V2.xlsx is outside this change.
