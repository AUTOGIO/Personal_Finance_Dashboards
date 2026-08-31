---
name: AI_GUIDE
description: Instructions for any AI assistant (Claude, ChatGPT/Codex, Gemini, Cursor, or others) working in this repo — read this before making changes.
---

# AI Guide — Personal_Finance

You are an AI assistant (any vendor) about to read, edit, or run something in
this repository. This file is the one thing you need before you touch
anything. `CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, and `.cursorrules` all just
point here — this is the canonical copy. If you edit these instructions,
edit this file only; the others stay as one-line pointers.

## What this project is

A personal finance workspace for one person: an Excel workbook holding real
account balances, transactions, and subscriptions, and a static HTML
dashboard generated from it. No server, no database, no build step, no
external services. Everything runs locally with Python 3 + `openpyxl`.

**This data is real and sensitive** — bank balances, transaction history,
personal spending. Treat every file under `data/`, `raw/`, `reports/`, and
the rendered dashboard as private. Don't paste figures from them into
shared/public contexts, don't publish the dashboard as a public web page,
don't send this data to a third-party service the user hasn't already
connected here, and don't include real values in commit messages, issue
titles, or anywhere that might get shared beyond this repo.

## The one rule that matters most

**`data/wealthcommand.xlsx`, sheet `CALC`, is the single source of truth.**
It says so in its own header cell. Every number on the dashboard should
trace back to that sheet, and only that sheet — not other sheets in the same
workbook, not `raw/`, not hand-typed HTML.

Two corollaries:
- **Never hand-edit numbers directly in `bloomberg-terminal.html`.** It's a
  generated artifact. Anything typed there by hand gets silently overwritten
  (or silently ignored) the next time someone runs the generator, and it
  reintroduces the exact class of bug this project has spent real effort
  eliminating: values drifting from their source. If a number needs to
  change, change it in `data/wealthcommand.xlsx` → `CALC`, then regenerate.
- **Never delete or overwrite `data/wealthcommand.xlsx` without the user's
  explicit confirmation in the current conversation.** It's the only copy.
  Nothing else in this repo can be rebuilt if it's lost.

## Layout

```
Personal_Finance/
├── AI_GUIDE.md                    this file (+ CLAUDE.md / AGENTS.md / GEMINI.md / .cursorrules pointers)
├── README.md                      technical overview, for humans
├── LEIA-ME.md                     weekly ritual, Portuguese
├── USER_GUIDE.md                  plain-language walkthrough, no jargon
├── Makefile                       make regen / make open / make clean / make help
├── bloomberg-terminal.html        the dashboard — GENERATED, do not hand-edit its data
├── data/wealthcommand.xlsx        the workbook — sheet CALC is the source of truth
├── scripts/regenerate_dashboard.py  the generator — patches the HTML from CALC
├── reports/                       dated point-in-time snapshots (docx), not auto-updated
├── raw/                           original bank/receipt exports, by institution — feeds the workbook manually, nothing reads it automatically
│   └── financas2026_import/       reference CSVs migrated from financas-2026 (weekly_tracker, cancel_tracker) — NOT wired into CALC
└── nfce/                          standalone NFC-e inflation tracker, migrated from financas-2026 — own README, own tests, NOT wired into CALC or the dashboard
```

## Commands

```bash
make regen     # rebuild bloomberg-terminal.html from data/wealthcommand.xlsx
make open      # regen, then open the dashboard in the default browser (macOS `open`)
make clean     # remove .DS_Store / __pycache__
make help      # list targets
```

Or run the script directly:
```bash
python3 scripts/regenerate_dashboard.py                          # defaults, patches in place
python3 scripts/regenerate_dashboard.py <xlsx> <html_in> <html_out>  # explicit paths, e.g. to preview into a scratch file
```

Dependency: `openpyxl` (already on this Mac's system Python 3.10; if
missing elsewhere: `pip3 install --break-system-packages openpyxl`). No
venv. Don't add one, and don't add other dependencies unless the task
genuinely requires them — see "Guardrails" below.

## How the generator actually works — read this before changing it

`scripts/regenerate_dashboard.py` does **not** rebuild `bloomberg-terminal.html`
from scratch. It's a targeted patcher: it opens the existing HTML, finds
specific known-stale spots by anchor (a regex or a unique surrounding
string), and replaces just those spots with values freshly computed from
`CALC`. Everything else in the HTML — CSS, layout, the SVG chart-drawing
JS, every tab not explicitly patched — is left byte-for-byte alone.

This was a deliberate choice over a full rebuild: smaller blast radius,
verifiable diffs, safe to run repeatedly. **Keep this approach** unless the
user explicitly asks for a full rebuild of the dashboard — that's a much
bigger, riskier change (every value would need a verified cell mapping,
not just the ones currently tracked) and has been discussed and deferred
more than once in this project's history.

**Currently patched (Tier 1 — script-verified, tracked directly from CALC cells):**
1. Subscriptions tab tiles + pie chart, CMD CTR "Sub Stack/mo" tile, ticker → `CALC!C344:E346`
2. Alert #3 ("Sub Stack Bloat") exposure + service count → `CALC!C346:E346`
3. `09 TX LOG` — all 146 rows → `02 CAPITAL FLOWS!B15:I221`, filtered `Source="MP Cartão"`
4. `05 LIFESTYLE` ML+iFood orders — all 69 rows → `05 LIFESTYLE!B34:G102`
5. The "Generated ... Source: ..." line (CMD CTR header + ticker) — stamped with today's date and the real source path
6. `09 TX LOG` "WEEKLY ROLLUP" table (added 2026-08-31) — same `02 CAPITAL FLOWS` rows as #3, grouped Mon–Sun and totalled live. Replaces financas-2026's old frozen `weekly_tracker.csv` snapshot — don't reintroduce that CSV as a second source; if the grouping logic needs to change, edit `build_weekly_rows()`.
7. `11 NFC-E` tab (added 2026-08-31) — renders `nfce/personal_inflation_data.json` (KPIs, YoY vs IPCA, top categories, risers/fallers). **Not derived from CALC** — a separate tracker, separate data file, and NOT recomputed on `make regen` (see "Migrated content" above for how to refresh it). If you edit `build_nfce_page()`, keep the "point-in-time, not live" framing in the tab's own text — don't let it start implying it auto-updates.

**Not yet patched (Tier 2):** the rest of the dashboard's tiles (Net Worth,
Total Liquidity, IB Deployed, FX Outbound, etc.) were hand-typed in the
original build. CALC has its own self-declared map for these — see sheet
`CALC`, rows 121–154 ("Section 6 · Master KPI Cells" + "KPI ROW REFERENCE
MAP") — and the dashboard's own `10 DATA MAP` tab shows, field by field,
which of these currently match CALC and which don't. **Before "fixing" any
Tier 2 tile, open the `10 DATA MAP` tab and check its status there first** —
some are legitimately unresolved data questions, not bugs (see "Known open
items" below), and forcing a fix without understanding why they disagree
can hide a real discrepancy instead of resolving it.

### The pattern for adding a new patch

If you're wiring a new field into Tier 1 (recommended over hand-editing),
follow the existing pattern in `patch()`:
1. Add a `re.subn(...)` (or a table-anchor `re.search` + splice, like the
   TX LOG / LIFESTYLE tables) that replaces the stale text with the value
   computed from the tracked CALC cell.
2. **Add a corresponding entry to the verification `checks` list near the
   end of `patch()`** (or, for a table, add a `count_table_rows()` check).
   This isn't optional — the verification step exists specifically because
   an earlier version of this script's own success/failure messages were
   ambiguous (a genuine failure and "already up to date" printed
   identically). Don't reintroduce that ambiguity. A patch without a
   verification check is a patch nobody will notice silently breaking.
3. Run it and confirm the final line says `[ok] all N spot-checks passed`.
   If it says `[WARNING]`, something is actually broken — don't report the
   task as done.
4. If you're promoting a Tier 2 field to Tier 1, update the `10 DATA MAP`
   tab in the HTML to move that row from "Tier 2" to "Tier 1 · LIVE", and
   update the "Currently patched" list above in this file.

## Known open items — do not silently resolve

- **Net Worth**: CALC says R$377,473.49 (`CALC!E137`). The workbook's own
  `01 NET WORTH` sheet, and the CMD CTR tile, say R$358,277. Traced to how
  the June IB→Wise withdrawal (R$19,195.81) is treated on `04 PORTFOLIO`.
  The dashboard displays CALC's number since CALC is the declared source
  of truth, but the discrepancy itself is real and unresolved.
- **IB Deployed**: same root cause. The tile shows the gross deposit figure
  (`CALC!E124`, R$197,706.57) where CALC's own KPI map says it should show
  the net-of-withdrawal figure (`CALC!E126` "IB NET DEPLOYED", R$178,510.76).

Both are documented in `README.md` → "Source of truth" and on the `10 DATA
MAP` tab. If asked to investigate or fix these, that means reconciling the
withdrawal treatment on `04 PORTFOLIO` against the actual bank statements
in `raw/` — not picking one existing number and forcing the other to match
it. If you resolve it, update both of those docs and the DATA MAP tab.

## Guardrails

Follow these unless the user explicitly asks otherwise in the moment:

- **Don't add infrastructure this project doesn't have**: no server, no
  database, no scheduler/cron, no build step, no venv, no test framework,
  no CI, no new external dependencies. This is a personal, single-user,
  weekly-cadence tool. If a task seems to need one of these, say so and ask
  before adding it, rather than adding it.
- **Don't rewrite `bloomberg-terminal.html` from scratch.** Patch it, per
  the pattern above.
- **Don't delete files** in `raw/`, `data/`, or `reports/` without asking —
  they hold real financial data with no other copy. (`archive/` used to
  exist for exactly this kind of superseded file; it was fully cleaned out
  and removed — there is currently no "soft delete" location, so anything
  removed is gone.)
- **Don't git-init or commit** unless the user explicitly asks. This folder
  is not currently a git repository.
- **Keep README.md, LEIA-ME.md, and USER_GUIDE.md in sync** with whatever
  structural changes you make — they've each drifted from reality before
  in this project's history, and catching that drift (twice) took real
  effort. Don't reintroduce it.
- **When you're not sure whether something is a bug or an open data
  question**, treat it like the Net Worth item above: document it, don't
  silently pick a side.

## Migrated content from financas-2026 (2026-08-31)

`financas-2026` was a separate sibling project (own git history, own
`financas2026-DataEntry.xlsx` workbook — a different data model, not a
duplicate). Most of it was intentionally left there.

- **`nfce/`** — a working, tested (18/18) NFC-e inflation tracker. A prior
  Claude Code session (folder `nfce01/`, since merged into `nfce/`) had
  already run it against 499 real receipts and produced
  `nfce/personal_inflation_data.json` (generated 2026-08-19). That output
  is now wired into the dashboard as tab **`11 NFC-E`** (patch step "8b" in
  `regenerate_dashboard.py`, function `build_nfce_page()`).
  **This tab is a snapshot, not live** — `make regen` does NOT recompute
  it, it only re-renders whatever is currently in
  `personal_inflation_data.json`. To refresh it: get real NFC-e receipts
  into `nfce/notas/NFCE_XML_*/` (the raw archive referenced by the old
  ingest log, at `~/.financas-notas/personal/` under an old macOS
  username, was NOT recovered — see "2026-08-31 nfce01 merge" below), run
  `cd nfce && python3 personal_inflation.py --verify-ground-truth`, then
  `make regen` again.
  Separately: **4 small receipt `.txt` files were lost** during the
  2026-08-31 `nfce01` → `nfce` merge (a `find -type f` bug skipped them
  before `nfce01` was deleted) — no other copy exists on this Mac or in
  `financas-2026`'s git history. The computed output already captured
  them, so no dashboard number is wrong, but future receipt-recount work
  should know 21 of the original 499 receipts' raw files are gone.
- **`raw/financas2026_import/cancel_tracker.csv`** — was already fully
  duplicated in `CALC` (Section 4D). No dashboard change needed; nothing
  to keep in sync.
- **`raw/financas2026_import/weekly_tracker.csv`** — superseded by the
  live "WEEKLY ROLLUP" table (Tier 1 patch #6 above). The CSV is a dead
  reference file now; safe to ignore.

## Verifying your own work

Don't declare a change done without checking it:
1. Run `make regen` (or the script directly) and confirm the last line is
   `[ok] all N spot-checks passed` — not a `[WARNING]`.
2. Sanity-check HTML tag balance if you touched the HTML directly:
   `python3 -c "import re; html=open('bloomberg-terminal.html').read(); [print(t, len(re.findall(f'<{t}[ >]',html)), len(re.findall(f'</{t}>',html))) for t in ['table','tr','td','div']]"`
3. If Playwright/a headless browser is available, load the file and click
   through the tabs you changed — screenshot and look at it. Don't assume
   a regex substitution rendered correctly without looking.
4. If you added or changed a Tier 1 patch, re-run the script a second time
   immediately after. It should report the same fields as "already
   correct" / 0 new substitutions and still pass all spot-checks —
   confirming the patch is idempotent, not something that drifts on repeat
   runs.
