# Personal_Finance

Local personal finance workspace: one Excel workbook, one static HTML
dashboard generated from it, and raw bank/receipt exports. No app, no
server, no build step.

## Source of truth

**`data/wealthcommand.xlsx`, sheet `CALC`.** It says so itself (cell
header: "CALC — Single Source of Truth"). Every figure on the dashboard is
derived from that one sheet — not from the other sheets in the same
workbook, not from `raw/`, not typed by hand into the HTML.

Two things that are *not* the source of truth, on purpose:
- **`raw/`** is upstream of CALC — the original bank/receipt exports CALC
  was built from. It's the ground truth for any single transaction, but
  it's unprocessed and nothing reads it automatically.
- **The workbook's own `01 NET WORTH` sheet disagrees with CALC** on net
  worth (R$358,277 vs R$377,473) — traced to how the June IB→Wise
  withdrawal is recorded on `04 PORTFOLIO`. The dashboard shows CALC's
  number throughout, since CALC is the declared source of truth, but this
  is a real unresolved disagreement, not a display bug. Worth checking
  against the actual account statements in `raw/`.

## Layout

```
Personal_Finance/
├── README.md                     you are here
├── LEIA-ME.md                    weekly update ritual (Portuguese)
├── Makefile                      make regen / make open / make clean
├── bloomberg-terminal.html       the dashboard — open directly in a browser
├── data/
│   └── wealthcommand.xlsx        the workbook (CALC = source of truth)
├── scripts/
│   └── regenerate_dashboard.py   rebuilds the dashboard from data/wealthcommand.xlsx
├── reports/
│   └── personal-finance-executive-report-2026-07.docx   point-in-time snapshot, not auto-updated
├── raw/                          bank & receipt exports, by institution — feeds the workbook manually
│   └── financas2026_import/      reference CSVs migrated from the old financas-2026 project (see below)
└── nfce/                         NFC-e personal inflation tracker — standalone, migrated from financas-2026
```

## Updating

```bash
make regen     # rebuild bloomberg-terminal.html from data/wealthcommand.xlsx
make open      # regen, then open the dashboard in your browser
make clean     # remove .DS_Store / __pycache__
```

`make regen` runs `scripts/regenerate_dashboard.py`, which patches
`bloomberg-terminal.html` in place — it does not rebuild the file from
scratch, so anything you've hand-edited elsewhere in the HTML survives a
re-run. It's idempotent: running it twice in a row with no workbook
changes produces zero diffs.

Requires `openpyxl` (already on this Mac's system Python 3; if missing:
`pip3 install --break-system-packages openpyxl`). No venv, no other
dependencies.

## NFC-E tab (11 NFC-E)

A separate personal-inflation tracker (grocery/pharmacy NFC-e receipts,
not bank/card data). Shows cumulative & annualized inflation, YoY vs.
official IPCA, top spend categories, and biggest risers/fallers.

**This tab is a snapshot, not live** — unlike everything else on the
dashboard, `make regen` does not recompute it, only re-renders whatever's
currently in `nfce/personal_inflation_data.json` (generated 2026-08-19
from 499 receipts). To refresh: get real receipts into
`nfce/notas/NFCE_XML_*/`, run `cd nfce && python3 personal_inflation.py
--verify-ground-truth`, then `make regen`.

## Weekly rollup (on the 09 TX LOG tab)

`regenerate_dashboard.py` also renders a "WEEKLY ROLLUP" table on the TX LOG
tab — MP Cartão spend grouped Mon–Sun. It's computed live from the same
`02 CAPITAL FLOWS` rows as the transaction table below it, every `make regen`
— not a stored figure, so it never needs separate updating.

## Weekly ritual

See `LEIA-ME.md` (Portuguese) — the short version is: update `data/wealthcommand.xlsx`,
then `make open`.

New to this project, or explaining it to someone who is? See `USER_GUIDE.md` —
plain-language walkthrough, no technical background assumed.

Handing this project to an AI assistant (Claude, ChatGPT/Codex, Gemini, Cursor,
or another)? Point it at `AI_GUIDE.md` — most of them will pick it up
automatically via `CLAUDE.md` / `AGENTS.md` / `GEMINI.md` / `.cursorrules`,
which all just point to it.

## Migrated from financas-2026

`financas-2026` was a separate, older sibling project with its own git
history and its own workbook (`financas2026-DataEntry.xlsx` — a different
data model from `wealthcommand.xlsx`, not a duplicate of it). Two pieces
were pulled into this project on 2026-08-31; everything else was left in
place there:

- **`nfce/`** — the NFC-e "personal inflation index" tracker. Its already-
  computed output (499 receipts, generated 2026-08-19) is now wired into
  the dashboard as tab **`11 NFC-E`** — see "NFC-E tab" below. The tool
  itself (`nfce/personal_inflation.py`, 18 passing tests) needs real NFC-e
  XML receipts under `nfce/notas/NFCE_XML_*/` to recompute; those aren't
  present here (the raw archive lives elsewhere and wasn't part of the
  migration — 4 smaller receipt files were also lost in the 2026-08-31
  merge, see `AI_GUIDE.md`).
- **`raw/financas2026_import/cancel_tracker.csv`** — turned out to be a full
  duplicate of data already in `wealthcommand.xlsx` (`CALC!C344:E346`,
  already on the dashboard as the Subscriptions tab / Alert #3). No import
  needed — kept only as an old reference copy.
- **`raw/financas2026_import/weekly_tracker.csv`** — was a frozen Jan–Jun
  2026 snapshot. Rather than import it as a second, driftable data source,
  the same rollup is now computed **live** by `regenerate_dashboard.py`
  straight from `02 CAPITAL FLOWS` (the same rows TX LOG already renders) —
  see "Weekly rollup" below. The CSV itself is no longer needed; kept for
  reference only.
