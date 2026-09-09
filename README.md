# Personal_Finance

Local personal finance workspace: **two Excel workbooks**, **two static HTML
dashboards** generated from them, and raw bank/receipt exports. No app, no
server, no build step.

## Source of truth

**Each dashboard has its own workbook — don't cross them.**

| Dashboard | Workbook | Source of truth |
|---|---|---|
| `bloomberg-terminal.html` | `data/wealthcommand.xlsx` | Sheet **`CALC`** only |
| `command-center.html` | `data/command-center.xlsx` | **All 11 sheets** (1:1 with tabs) |

For the wealth dashboard, `CALC` declares itself "Single Source of Truth".
Every patched figure on `bloomberg-terminal.html` traces to `CALC` — not
other sheets in the same workbook, not `raw/`, not hand-typed HTML.

Two things that are *not* the source of truth, on purpose:
- **`raw/`** is upstream — original bank/receipt exports. Ground truth for
  any single transaction, but nothing reads it automatically.
- **Net worth disagreements** between dashboards and within the wealth
  workbook (CALC vs `01 NET WORTH` tile) are documented open items — see
  `AI_GUIDE.md` → "Known open items". Reconcile against `raw/` statements;
  don't force one number to match another.

## Layout

```
Personal_Finance/
├── README.md                     you are here
├── AI_GUIDE.md                   canonical guide for humans and AI assistants
├── USER_GUIDE.md                 plain-language walkthrough + weekly checklist
├── LEIA-ME.md                    weekly ritual (Portuguese)
├── Makefile                      make regen / check / workspace / open / clean
├── WORKSPACE_LAYOUT.md           Spencer 3-display layout
├── bloomberg-terminal.html       wealth dashboard — GENERATED
├── command-center.html           ops dashboard — GENERATED, FROZEN 2026-09-08
├── data/
│   ├── wealthcommand.xlsx        wealth workbook (CALC = source of truth)
│   └── command-center.xlsx       ops workbook (11 sheets)
├── scripts/
│   ├── regenerate_dashboard.py   patches bloomberg-terminal.html from CALC
│   ├── generate_command_center.py   rebuilds command-center.html from workbook
│   ├── check_integrity.py        make check — sheet + irreplaceable-file preflight
│   └── backup.sh                 timestamped backup outside iCloud
├── reports/                      point-in-time snapshots (docx/csv/md/json), not auto-updated
├── docs/                         gitignored audit / plan / execution history
├── notebooklm/                   gitignored Markdown export (make notebooklm)
├── raw/                          bank & receipt exports — feeds workbooks manually
└── nfce/                         NFC-e personal inflation tracker (Bloomberg tab 11)
```

**Location:** `~/Documents/GitHub/Personal_Finance` (not iCloud).  
**GitHub:** `AUTOGIO/Personal_Finance_Dashboards` (private).

## Updating

**Wealth dashboard:**
```bash
make regen     # patch bloomberg-terminal.html from data/wealthcommand.xlsx
make open      # regen, then open in your browser
make check     # workbook sheets + irreplaceable nfce/ files
make clean     # remove .DS_Store / __pycache__
```

**Command center:**
```bash
python3 scripts/generate_command_center.py   # full rebuild from command-center.xlsx
open command-center.html
```

**Export for NotebookLM / other notebook tools:**
```bash
make notebooklm    # notebooklm/bloomberg.md + notebooklm/command-center.md
```
Clean Markdown — tabs, KPI tiles and tables, no CSS or JS (about a third the
size of the HTML), with e-mail addresses masked. Gitignored: regenerate rather
than commit.

`make regen` runs `scripts/regenerate_dashboard.py`, which patches
`bloomberg-terminal.html` in place — it does not rebuild from scratch.
Confirm `[ok] all N spot-checks passed` after every run.

`python3 scripts/generate_command_center.py` fully rebuilds
`command-center.html` and performs field-level spot-checks before writing.
Confirm `[ok] all N ops spot-checks passed` and `[ok] wrote command-center.html`
with matching tag counts (no MISMATCH).

Requires `openpyxl` for the wealth patcher (system Python on this Mac;
elsewhere: `pip3 install --break-system-packages openpyxl`). The command
center generator uses stdlib only. No venv.

**Tested environment:** Python 3.9.6 with openpyxl 3.1.5.

**Regression tests:**
```bash
cd ~/Documents/GitHub/Personal_Finance
python3 -m unittest scripts/tests/test_regenerate_dashboard.py -v   # wealth patcher failure handling
cd nfce && python3 -m unittest discover -s tests -v                 # NFC-e pipeline
```

No CI pipeline — verification is intentional, local, and run on demand.

## Weekly ritual

See **`USER_GUIDE.md` §4** (combined wealth + ops checklist) and
**`AI_GUIDE.md` → Weekly workflows** (AI prompt templates).

Short version:
1. Save exports under `raw/`
2. Update `wealthcommand.xlsx` (`CALC`) → `make open`
3. Update `command-center.xlsx` (input cells) → `python3 scripts/generate_command_center.py`
4. Review both dashboards; reconcile cross-dashboard gaps in the owning workbook

Portuguese checklist: `LEIA-ME.md`.

## Spending ledger (reports/, 2026-09-08)

`reports/2026-09-08_spending_by_month.csv` and `2026-09-08_clean_ledger.csv` hold
a category-by-month spending view for Jan–Sep 2026, built once from `raw/`
statements. **Point-in-time — the ledger is not regenerated.** The month/category
CSV is rendered into bloomberg tab **`12 SPENDING`** on every `make regen`, the
same way tab 11 renders the NFC-e snapshot. Drop a newer dated CSV in `reports/`
and re-run `make regen` to refresh the tab.

Method, sources, verification and the classification decisions:
`reports/2026-09-08_spending_method.md`.

September is partial (BB and MP account cover 01–06 Sep only). This answers
"what did I spend, by category, month over month" — it is not a reconciliation
and must not be used to adjust net worth or liquidity figures.

## NFC-E tab (11 NFC-E)

Personal-inflation tracker (grocery/pharmacy NFC-e receipts). **Snapshot,
not live** — `make regen` re-renders `nfce/personal_inflation_data.json`
(tracked; dated 2026-08-19) without recomputing it. **`nfce/notas/` is
empty**, so the tab is frozen until source XMLs are restored (check Time
Machine manually). Then: receipts under `nfce/notas/NFCE_XML_*/`,
`cd nfce && python3 personal_inflation.py --verify-ground-truth`, then
`make regen`.

## Weekly rollup (09 TX LOG tab)

Computed live from `02 CAPITAL FLOWS` (MP Cartão rows) on every `make regen` —
no separate CSV to maintain.

## Migrated from financas-2026

`financas-2026` was a sibling project with a different workbook model. Pulled
into this repo on 2026-08-31:

- **`nfce/`** — NFC-e inflation tracker wired into Bloomberg tab **`11 NFC-E`**
  (see `AI_GUIDE.md` for refresh steps and merge notes).
- **Reference CSVs removed** — old `cancel_tracker.csv` and `weekly_tracker.csv`
  duplicates were deleted; data lives in `CALC` and the live WEEKLY ROLLUP.

Handing this to an AI assistant? Point it at **`AI_GUIDE.md`** — picked up
automatically via `CLAUDE.md` / `AGENTS.md` / `GEMINI.md` / `.cursorrules`.
