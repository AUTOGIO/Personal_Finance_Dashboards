# Rules for future spending imports

These rules persist the decisions from the interactive Q&A. Apply them before generic merchant classification in future imports using this workspace. No background monitoring or scheduled import has been configured.

Match normalized recipient name AND recipient identifier. Normalize case, accents, and repeated whitespace. Preserve the original description and identifiers. Bank-truncated names from these BB files are explicitly represented. If another source omits identifiers, uses a different/truncated name, or has multiple possible matches, require review rather than guessing identity.

- include: assign the saved category to completed purchases/payments. Calculate only the retained amount after verified refunds; preserve original amounts.
- exclude: keep the record but do not count it as spending (foreign transfers, physical currency purchases, card settlements).
- defer: leave unresolved and outside identified spending. Do not infer a category or repeatedly ask during the current pass.
- Refunds, reversals, credits and duplicates must be handled before computing spending. An include rule never turns a refund or incoming transfer into spending.
- Later user corrections override earlier rules. Unmatched recipients remain review candidates.
- Some rules record a user-confirmed purpose mapped by the assistant to PERSONAL; their basis is explicitly marked.

Source scope: rules originate from the BB Q&A. Apply across banks only when identity matches reliably; the newly supplied Mercado Pago files have not yet been processed. This CSV is reusable data, not a bank-side setting; future import workflows must load it to apply these rules automatically.

## Available review category

- `UNKNOWN - CHECK`: recipient or payment purpose still needs user review. Keep separate from confirmed spending categories until resolved; this label does not itself authorize inclusion or exclusion. Created at user request. No recipients assigned by this category-creation step.
