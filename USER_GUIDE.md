# User Guide — How This Money Tracker Works

This explains the whole project in plain language. If you can double-click
an icon and copy-paste a line of text, you can use this.

## 1. What even is this?

This is a personal money tracker. It has **two notebook + poster pairs** —
same spy-movie look, different jobs:

| Pair | Notebook (spreadsheet) | Poster (dashboard) | Best for |
|---|---|---|---|
| **Wealth dashboard** | `data/wealthcommand.xlsx` | `bloomberg-terminal.html` | Weekly wealth ritual — net worth, subscriptions, NFC-e inflation, data audit |
| **Command center** | `data/command-center.xlsx` | `command-center.html` | iMac ops board — repos, projects, config thresholds, host info |

The important rule for **both**: **the poster is made FROM the notebook.**
You never write numbers directly on the poster — you write in the notebook,
then print a new poster from it.

## 2. How to look at the dashboards

1. Find `bloomberg-terminal.html` or `command-center.html` in the project
   folder.
2. Double-click either one. It opens in your web browser (Safari, Chrome,
   whatever).
3. That's it — no login, no internet needed, no app to install.

**Which one to open?**
- **`bloomberg-terminal.html`** — the main wealth view (12 tabs). Start
  here for the weekly money check.
- **`command-center.html`** — the iMac-focused ops view (13 tabs). Same
  dark Bloomberg style, but mirrors `command-center.xlsx` sheet-for-sheet
  and adds REPOS, PROJECTS, CONFIG, and SYSTEM tabs.

## 3. What all the buttons do

- **Tabs across the top** — click one to switch pages. Each tab is a
  different topic (bank balances, subscriptions, FX operations, alerts,
  and so on). Tab names differ slightly between the two dashboards; see
  section 5.
- **`A−` / `A+` buttons, top right** — makes everything on the page
  bigger or smaller. There's a `100%` number between them that shows the
  current size.
- **Search boxes** (on transaction tabs — `09 TX LOG` in Bloomberg,
  `03 TRANSACTIONS` in Command Center) — type a word (like a store name)
  and the table below filters to just matching rows.
- **Scrolling** — if a page has more stuff than fits on your screen, just
  scroll down like any normal webpage.
- **Ticker tape** (orange bar at the very bottom) — scrolls key numbers
  (net worth, liquidity, card spend, etc.).

Nothing you click can break anything or delete any data. It's just a
screen for looking — feel free to click around.

## 4. How to update it (the weekly job)

Every week, new numbers need to go in. The project has **two notebooks**
that do **not** sync automatically. If you use both dashboards, update
**both** when balances, card transactions, or subscriptions change.

**Recommended order each week:**

1. Collect raw statements → save under `raw/` (unchanged originals).
2. **Wealth pass** — edit `wealthcommand.xlsx`, run `make open`.
3. **Command center pass** — edit `command-center.xlsx`, run the ops
   generator (checklist below).
4. Open both posters and review. If the same concept (e.g. net worth)
   differs between dashboards, **investigate** — do not pick one number
   and force the other to match (see section 6, rule 5).

### Step 0 — Collect source files (both dashboards)

Download current bank, card, BCB, and subscription statements. Save
exports under `raw/` by institution (`raw/mercado_pago/`,
`raw/banco_inter/`, etc.). Keep raw files private and unchanged.

### Wealth dashboard pass

1. **Open the notebook.** Double-click `data/wealthcommand.xlsx`.
2. **Find the sheet (tab) called `CALC`.** That's the ONE sheet that
   matters for the wealth dashboard — it's the "real" numbers.
3. **Type in the new numbers** — balances, card flows (`02 CAPITAL
   FLOWS`), subscriptions (Section 4D), whatever changed. Save (Cmd+S)
   and close.
4. **Print the wealth poster.** In Terminal:
   ```
   cd ~/Documents/GitHub/Personal_Finance && make open
   ```
   Confirm the last line says `[ok] all N spot-checks passed` (not
   `[WARNING]`). Your browser opens with the updated wealth dashboard.
   Optional safety: `make check` verifies both workbooks still have the
   expected sheets.

### Command center pass (detailed checklist)

Open `data/command-center.xlsx`. Edit **blue/input cells only** — never
overwrite formula cells for age, risk, or counts.

1. **Update balances** — confirmed balances, dates, notes
   (`BALANCES!A4:G17`). Verify liquidity and estimated net worth
   recalculate.
2. **Record FX operations** — append each operation with direction:
   `Outbound`, `Inbound`, `IB Deposit`, `IB Withdraw`, or
   `Fund Deposit`. Check the direction summary (`FX_OPS!A4:I45`).
3. **Import card transactions** — append entries; **negative values for
   spending**. Reuse categories; flag international purchases
   (`TRANSACTIONS!A4:G67`).
4. **Update PIX activity** — separate PIX, FX, and IOF into their columns;
   verify flow totals (`PIX!A4:F41`).
5. **Review subscriptions** — renewal dates, statuses; classify each as
   `KEEP`, `CANCEL`, or `REVIEW`. Confirm projected savings and monthly
   stack (`SUBSCRIPTIONS!A4:J27`).
6. **Refresh operational tracking** — repo status and project actions
   (`REPOS!A4:J12`, `PROJECTS!A4:G15`).
7. **Check alert parameters** — compare against liquidity, spending,
   subscription, FX, and staleness thresholds. Change limits in CONFIG
   only when your preferences genuinely change (`CONFIG!A4:D16`).
8. **Verify derived sheets** — `MONTHLY`, `CATEGORIES`, and `ALERTS` are
   usually formula-driven from the sheets above. Spot-check them after
   updating transactions and FX; edit only if your workbook uses manual
   rows there.
9. **Quality checks** — missing dates, duplicate transactions, unknown
   currencies, outdated statuses, wrong signs, formula errors.
10. **Regenerate the ops poster** — never type figures into
    `command-center.html`. In Terminal:
    ```
    cd ~/Documents/GitHub/Personal_Finance && python3 scripts/generate_command_center.py
    ```
    Confirm `[ok] wrote command-center.html` with matching tag counts (no
    MISMATCH). Open with `open command-center.html` if the browser did
    not open automatically.

There is no `make` shortcut for the command center — use the Python command
above. **`make open` is for the wealth dashboard only.**

### Dual-workbook overlap (keep both in sync)

These concepts exist in **both** notebooks. Update both when they change:

| Concept | Wealth (`wealthcommand.xlsx`) | Command center (`command-center.xlsx`) |
|---|---|---|
| Subscriptions | `CALC` Section 4D | `SUBSCRIPTIONS` sheet |
| Card transactions | `CALC` → `02 CAPITAL FLOWS` | `TRANSACTIONS` sheet |
| Balances / net worth | `CALC` (+ portfolio sheets) | `BALANCES` sheet |

Updating only one notebook leaves the other dashboard stale.

### Using AI help (optional)

After regenerating both dashboards, you can ask an AI to review alerts
and suggest actions. See **`AI_GUIDE.md` → "Weekly workflows"** for the
prompt template and guardrails (read `AI_GUIDE.md` first; do not paste
real figures into public chats).

If any Terminal step looks scary or throws an error, copy the message and
ask for help.

## 5. What each folder is (in plain words)

```
Personal_Finance/
├── bloomberg-terminal.html   wealth poster — double-click to look at it
├── command-center.html       ops poster — double-click to look at it
├── data/
│   ├── wealthcommand.xlsx    wealth notebook — CALC sheet is the boss
│   └── command-center.xlsx   ops notebook — 11 sheets, one per tab topic
├── raw/                      filing cabinet of original bank statements/receipts
├── reports/                  old printed summaries (one per date)
├── nfce/                     grocery inflation tracker (feeds Bloomberg tab 11)
├── scripts/
│   ├── regenerate_dashboard.py   "printer" for bloomberg-terminal.html
│   └── generate_command_center.py   "printer" for command-center.html
└── Makefile                  cheat-sheet of short commands (make open, etc.)
```

You will mostly touch:
- **`data/wealthcommand.xlsx`** + **`make open`** — weekly wealth ritual
- **`data/command-center.xlsx`** + **`generate_command_center.py`** — when
  updating the ops board

Everything else runs itself or is reference material.

## 6. The golden rules

1. **Never delete either workbook in `data/`.** They are the only copies
   of the real numbers. The HTML posters can always be rebuilt from them;
   the workbooks cannot be rebuilt from the posters.
2. **Never type numbers directly into either HTML file.** They get
   overwritten every time someone runs the generator — anything you typed
   there by hand would just vanish. Numbers only go in the spreadsheets.
3. **Wealth dashboard source of truth:** sheet **`CALC`** in
   `wealthcommand.xlsx`. If a number on `bloomberg-terminal.html` looks
   wrong, check `CALC` first — `CALC` wins.
4. **Command center source of truth:** **`data/command-center.xlsx`**
   (all 11 sheets). Every tab on `command-center.html` mirrors one sheet.
5. **The two dashboards can show different numbers for the same concept**
   (e.g. net worth) because they read from different workbooks with
   different formulas. That's documented on Bloomberg's `10 DATA MAP`
   tab — don't panic, but do investigate if the gap grows.

## 7. If something looks broken

- **Dashboard shows old numbers** → someone edited the notebook but forgot
  to run the generator. Run `make open` (wealth) or
  `python3 scripts/generate_command_center.py` (ops).
- **A tab looks weird or numbers are cut off** → try clicking `A−` once or
  twice to shrink things back down.
- **Terminal says something you don't understand** → that's fine, copy the
  message and ask an adult or Claude what it means.

See `README.md` for the more technical version of all this,
`LEIA-ME.md` for the Portuguese weekly-ritual checklist, and
`AI_GUIDE.md` → Weekly workflows for AI-assisted reviews.
