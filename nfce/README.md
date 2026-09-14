# NFC-e Personal Inflation

> **Frozen snapshot — not the canonical index (decided 2026-09-11).** The maintained personal
> inflation index is the IIP in `~/Documents/GitHub/edu_price_analysis`
> (`02_Models/personal_inflation_tracker-v3_classificacao.xlsx`). This folder keeps the 2026-08-19 snapshot
> (499 receipts) that Bloomberg tab 11 renders. Don't reconcile or merge the two — different
> receipt sets and methods (see `edu_price_analysis/AGENTS.md`, boundary section).

Two parallel analyses from Brazilian NFC-e XMLs. **Do not mix their inputs.**

| Track | Input | Script | Meaning |
|-------|--------|--------|---------|
| **Personal** | [`notas/`](notas/) | [`personal_inflation.py`](personal_inflation.py) | Household inflation from *your* receipts |

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
cd "$(git rev-parse --show-toplevel)/nfce"
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

Drop another `NFCE_XML_*` folder into `notas/` and rerun. Dedup is by 44-digit access key. 

---

## Tests

From repo root:

```bash
cd "$(git rev-parse --show-toplevel)/nfce"
python3 -m unittest tests.test_personal_inflation
```

Personal coverage: product identity, units, medians, log returns, chained weights, dedup.  

## Dashboard use

Serve the folder and open either app:

```bash
cd "$(git rev-parse --show-toplevel)/nfce"
python3 -m http.server 8000
```

- Personal: [http://127.0.0.1:8000/personal_inflation_index.html](http://127.0.0.1:8000/personal_inflation_index.html)

Opening the HTML files directly also works via the embedded fallback payload written by each pipeline. Bloomberg tab **11 NFC-E** shows the personal track; open the HTML files in this folder for standalone views.

## Known gaps / limits

- IPCA is a rough embedded reference line, not a live fetch.
- 2026-07 product naming breaks many YoY joins — excluded from staple YoY by design.
- Dashboards are static local apps, not a compiled frontend.
- CSV artifacts remain inspection-only and are not source of truth.

## Durability, retention, and recovery

A fresh `git clone` of this repo **fails `make check`** because the four
irreplaceable derived artifacts below are gitignored. Only the rendered
snapshot (`personal_inflation_data.json`) is tracked. The rest are backed up
by `scripts/backup.sh` on the local Mac, but a new machine without that
backup cannot regenerate them because `nfce/notas/` holds no source XMLs.

| Required artifact | Tracked in git | Backed up locally | Regenerable without source XMLs | Notes |
|---|---|---|---|---|
| `personal_inflation_data.json` | Yes | Yes | No | Frozen snapshot rendered on Bloomberg tab 11. |
| `personal_inflation_validation.json` | No | Yes | No | Validation payload used by `--verify-ground-truth`. |
| `nfce_all.json` | No | Yes | No | Full parsed receipt corpus. |
| `nfce_items.csv` | No | Yes | No | Per-item extracted lines. |
| `nfce_transactions.csv` | No | Yes | No | Per-receipt summary. |
| `notas/NFCE_XML_*` source XMLs | No | No | n/a | Directory is empty; only 14 partial XMLs recovered from Time Machine (see below). |
| `inflation_data.json` | No | Yes | Yes | Legacy intermediate; rebuilds from the tracked snapshot. |

**Recovery status of source XMLs.** A Time Machine snapshot on this Mac
contains one archive with 14 valid NFC-e XMLs (`NFCE_XML_DLJ4REU8NB.zip`, dated
2026-05-11). These were copied to a private recovery directory for
inspection:

```
~/Backups/Personal_Finance/NFCE_recovery_20260907-145513/
```

- Format: `nfeProc` / `NFe` XML, 44-digit access keys in filenames.
- Count: 14 unique XML receipts (no duplicates by key prefix).
- Provenance: user's own Downloads/Archives path in the Time Machine backup.
- Completeness: **not sufficient** to recompute the current frozen snapshot.
  The Bloomberg tab 11 snapshot was built from 499 receipts; the recovered
  archive is only a small May 2026 batch. Two additional `raw/nfce/*.json`
  summary/pending files exist in the repo but are not full XML sources.

**Decision needed.** Because the four ignored irreplaceable files are already
backed up locally, `make check` passes on this Mac. A fresh clone fails until
one of these choices is made:

1. **Track the four ignored irreplaceable files in git** (largest durability
   gain; increases repo size by ~1.3 MB and adds sensitive receipt-derived
   artifacts to git history forever).
2. **Narrow `IRREPLACEABLE` in `scripts/check_integrity.py`** to only the
   tracked `personal_inflation_data.json` (weaker durability; a fresh clone
   would then pass `make check` but could never validate or recompute the
   full pipeline without restoring the local backup).
3. **Keep the current list and accept that fresh clones need a backup restore**
   (status quo; document in onboarding).

Do not change this without explicit approval. The current backup verification
has confirmed all five IRREPLACEABLE files are present in the latest backup.

## Litoral store track — removed 2026-09-08

The Litoral store price tracker (`litoral_store_prices.*`, `litoral_price_*.json`
and its test) was removed in the 2026-09-08 cleanup. It fed nothing here — its
analysis outputs live in `edu_price_analysis`, its source in the separate
`LitoralPriceTracker` repo. Recover if ever needed:

```bash
git checkout HEAD -- nfce/litoral_store_prices.py nfce/litoral_price_data.json
```
