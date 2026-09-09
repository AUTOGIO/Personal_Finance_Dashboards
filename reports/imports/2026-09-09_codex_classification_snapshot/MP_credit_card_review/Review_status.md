# Mercado Pago credit-card review

June statement: 42 line items extracted from original PDF pages 2–6, adding to the stated consumption amount R$6,850.32. This is a source extraction check, not a cash-flow reconciliation. Categories are pending review; these items have not been merged into overall spending totals. Installments are the billed amounts, not full purchase amounts. Repeated line items are preserved as printed. Other statements still require validation; January text extraction has character-encoding errors.

Lottery update: 7 MP*LOTERIASONLINE charges totaling R$1,153.50 in June are excluded as group payments. Reusable prefix rule saved in Classification_rules.csv; apply when other months are imported.

Order evidence added: ml_orders.json contains delivery dates (verified on ML.pdf pages 5–7), not necessarily purchase dates. Novastar R$1798 and Logitech mouse R$1590 are probable installment matches, not confirmed order-ID matches. Three June food charges totaling R$230.63 classified Restaurants using ifood_orders.json. Order amounts are supporting evidence, not additional spending; zero-valued orders are not assumed free. IFD*iFood R$7.95 remains pending because source describes an unspecified fee/order.

User update: Novastar VC2 / MERCADOLIVRE*KF classified HOME SPENDINGS. June installment R$449.50 included; purchase-specific rule saved for other installments when imported. Full R$1798 order value not added separately.

User update: Logitech mouse installment classified Home Office. June R$397.50 included; purchase-specific rule saved. Order link remains a probable match; full R$1590 order value not added separately.

User update: March 8 Mercado Livre purchase identified as CPAP; classified PERSONAL following earlier CPAP decision. June installment R$1678.30 included, with purchase-specific rule saved. Three installments total R$5034.90; no full order amount added separately.

Apple update: user provided current subscription screenshots. June Apple charges R$151.70 provisionally categorized Subscriptions / software, separate from confirmed classifications. No screenshot prices added as transactions. Exact historical subscription matches remain unconfirmed; R$31.90 unidentified. Saved rule suggests category for review.

2026-09-08: Applied returned table answers to 25 charges. HOME normalized to HOME SPENDINGS; software categories changed to Home Office as instructed. UBER * PENDING excluded, DL*UberRides PERSONAL; Vivo kept PERSONAL / HOME without splitting. iFood R$7.95 remains pending and Apple R$151.70 provisional. June_category_summary.csv is June only and supersedes earlier interim category status. Other statement periods are not yet consolidated.

2026-09-08: User confirmed iFood R$7.95 as LUNCH / DINNER, mapped to Restaurants; June restaurant total now R$238.58. No June items remain uncategorized. Apple R$151.70 still provisional; other statement periods remain unconsolidated.

2026-09-08: User confirmed all three reviewed Apple charges (R$151.70) as app purchases. Category App purchases, included spending; previous provisional subscription interpretation superseded and saved rule updated. No pending or provisional rows remain in the June ledger. Other statement periods remain unconsolidated.

2026-09-08 January–May processing complete: all five purchase totals validated, rules applied, 39 grouped review items generated. Jan_Jun_spending_report.md is the current card-only overview. Earlier statements that other months await extraction are superseded. Bank/account ledgers remain unmerged.

2026-09-08: Returned JM table applied: 26 included groups R$28502.29; 13 blank groups R$4920.06 explicitly excluded. All 39 review groups resolved; January–June included card spending R$47252.39. Previous pending totals superseded. Sources retained.
