# NFC-e Personal Inflation + Litoral Store Track

Two parallel analyses from Brazilian NFC-e XMLs. **Do not mix their inputs.**

| Track | Input | Script | Meaning |
|-------|--------|--------|---------|
| **Personal** | [`notas/`](notas/) | [`personal_inflation.py`](personal_inflation.py) | Household inflation from *your* receipts |
| **Litoral store** | [`notas_litoral/`](notas_litoral/) → `LitoralPriceTracker/data/raw/NOTAS_LITORAL` | [`litoral_store_prices.py`](litoral_store_prices.py) | One-day-per-year store price snapshots (Supermercado Litoral) |

## Personal track — source of truth

- Primary input: XML files under [`notas/`](notas/)
- Current XML inventory: `NFCE_XML_*` export folders, unique keys after dedup, cancelled keys excluded
- Supporting artifacts only: CSVs / derived JSON (not sufficient to reproduce the index alone)

## Personal pipeline

- Entry point: [`personal_inflation.py`](personal_inflation.py)
- Method:
  - product identity = valid EAN, else `CNPJ-root + normalized description`
  - commercial unit stays in the grouping key
  - monthly product price = median unit price
  - price gaps are spread with monthly log returns
  - jumps larger than `4x` are filtered
  - monthly inflation = spend-weighted mean of active log returns
  - chained base = `100` at the first active month

### Run (personal)

```bash
cd "$(git rev-parse --show-toplevel)/src/nfce"
python3 personal_inflation.py --verify-ground-truth
```

Optional flags: `--skip-html`, `--output-json`, `--validation-json`, `--notes-dir`.

### Outputs (personal)

- `personal_inflation_data.json` / `personal_inflation_validation.json`
- [`personal_inflation_index.html`](personal_inflation_index.html) (+ `.js` / `.css`)

### Expected metrics

Ground-truth baseline lives in [`personal_inflation_baseline.json`](personal_inflation_baseline.json).
Verify with `--verify-ground-truth`; refresh after intentional data additions with
`--accept-new-baseline`. `EXPECTED_METRICS` in `personal_inflation.py` is only a
fallback if the JSON file is missing.

### Incremental refresh (personal)

Drop another `NFCE_XML_*` folder into `notas/` and rerun. Dedup is by 44-digit access key. Never drop Litoral store dumps here.

---

## Litoral store track

Store-wide NFC-e dumps for **Supermercado Litoral** (CNPJ `08189400000107`, Cabedelo/PB). Each export folder is typically **one calendar day** (26/Dec for 2020–2025; 2026-07-01 naming differs and is excluded from YoY joins).

This is a **local price benchmark**, not household inflation. The macOS app under `Downloads/NOTAS_LITORAL/LitoralPriceTracker` explores the same XMLs interactively.

### Setup notes dir

XMLs stay out of git (~330MB+). Symlink your local checkout of the sibling
`LitoralPriceTracker` repository:

```bash
cd "$(git rev-parse --show-toplevel)/src/nfce"
ln -sfn "$HOME/Documents/GitHub/LitoralPriceTracker/data/raw/NOTAS_LITORAL" notas_litoral
```

Expected layout under that root: year folders `2020/`…`2026/` with `NFCE_*.xml` (legacy `NFCE_XML_*` still works), plus optional `NFCE_*.txt` SEFAZ dumps. Refresh = add new XMLs/TXTs there and rerun.

### Run (Litoral)

```bash
cd "$(git rev-parse --show-toplevel)/src/nfce"
python3 litoral_store_prices.py
```

Optional: `--notes-dir`, `--personal-json` (for the compare panel), `--skip-html`.

### Method (Litoral)

1. Reuse `parse_receipts` for year folders `20XX/` (or legacy `NFCE_XML_*`); also ingest SEFAZ `NFCE_*.txt` pipe exports (no EAN; grouped by emission timestamp)
2. Keep CNPJ `08189400000107` only (TXT assumed Litoral)
3. Snapshot price = median unit price within each calendar year, keyed by normalized description + UOM (merges XML+TXT)
4. Staples matched by product label; equal-weight geometric basket on Dec-eligible years (2026 = naming drift)
5. Optional compare panel vs `personal_inflation_data.json` by keyword family

Refresh TXT: drop new `NFCE_YYYYMMDDhhmmss.txt` files into `notas_litoral/` (same folder as the XMLs) and rerun.

### Outputs (Litoral)

- `litoral_price_data.json` / `litoral_price_validation.json` (gitignored; rebuild locally)
- [`litoral_store_prices.html`](litoral_store_prices.html) — overview, vs personal, product table

---

## Tests

From repo root:

```bash
python3 -m unittest tests.test_personal_inflation tests.test_litoral_store_prices
```

Personal coverage: product identity, units, medians, log returns, chained weights, dedup.  
Litoral coverage: CNPJ filter, YoY eligibility / naming drift, staple match, basket rebase.

## Dashboard use

Serve the folder and open either app:

```bash
cd "$(git rev-parse --show-toplevel)/src/nfce"
python3 -m http.server 8000
```

- Personal: [http://127.0.0.1:8000/personal_inflation_index.html](http://127.0.0.1:8000/personal_inflation_index.html)
- Litoral: [http://127.0.0.1:8000/litoral_store_prices.html](http://127.0.0.1:8000/litoral_store_prices.html)

Opening the HTML files directly also works via the embedded fallback payload written by each pipeline. The main financas dashboard links both under the NFC-e panel.

## Known gaps / limits

- IPCA is a rough embedded reference line, not a live fetch.
- Litoral sampling is directional (≈1 day/year), not continuous monthly inflation.
- 2026-07 product naming breaks many YoY joins — excluded from staple YoY by design.
- Dashboards are static local apps, not a compiled frontend.
- CSV artifacts remain inspection-only and are not source of truth.
