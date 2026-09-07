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

A personal finance workspace for one person: **two Excel workbooks** and
**two static HTML dashboards** generated from them. No server, no database,
no build step, no external services. Everything runs locally with Python 3.

- **`wealthcommand.xlsx` → `bloomberg-terminal.html`** — primary wealth
  dashboard (12 tabs). Patched by `regenerate_dashboard.py` (uses `openpyxl`).
- **`command-center.xlsx` → `command-center.html`** — iMac ops dashboard
  (13 tabs). Fully rebuilt by `generate_command_center.py` (dependency-free
  xlsx-as-zip reader — no `openpyxl`).

Canonical clone: **`~/Documents/GitHub/Personal_Finance`**. The private
GitHub remote for *this* project is **`AUTOGIO/Personal_Finance_Dashboards`**
(or whatever `origin` points at after cutover). Do **not** treat
`AUTOGIO/Personal_Finance` as this repo — that name now holds a different
project. Treat every file as sensitive even when private.

**This data is real and sensitive** — bank balances, transaction history,
personal spending. Treat every file under `data/`, `raw/`, `reports/`, and
the rendered dashboard as private. Don't paste figures from them into
shared/public contexts, don't publish the dashboard as a public web page,
don't send this data to a third-party service the user hasn't already
connected here, and don't include real values in commit messages, issue
titles, or anywhere that might get shared beyond this repo.

## The one rule that matters most

**Each dashboard has its own source of truth — don't cross them.**

| Dashboard | Workbook | Source of truth |
|---|---|---|
| `bloomberg-terminal.html` | `data/wealthcommand.xlsx` | Sheet **`CALC`** only |
| `command-center.html` | `data/command-center.xlsx` | **All 11 sheets** (1:1 with tabs) |

For the wealth dashboard, `CALC` says so in its own header cell. Every
number on `bloomberg-terminal.html` should trace back to `CALC` — not other
sheets in the same workbook, not `raw/`, not hand-typed HTML, not
`command-center.xlsx`.

For the command center, every number on `command-center.html` should trace
back to `command-center.xlsx` — the generator reads every sheet live.

Three corollaries:
- **Never hand-edit numbers directly in either HTML file.** Both are
  generated artifacts. Hand-typed values get silently overwritten on the
  next generator run and reintroduce values drifting from their source.
- **Never delete or overwrite either workbook in `data/` without the user's
  explicit confirmation in the current conversation.** They are the only
  copies. Posters can be rebuilt from workbooks; workbooks cannot.
- **Don't "fix" a disagreement between the two dashboards by forcing one
  number to match the other** without understanding which workbook owns
  that field. They use different data models (see "Known open items").

## Layout

```
Personal_Finance/
├── AI_GUIDE.md                       this file (+ CLAUDE.md / AGENTS.md / GEMINI.md / .cursorrules pointers)
├── README.md                         technical overview, for humans
├── LEIA-ME.md                        weekly ritual, Portuguese
├── USER_GUIDE.md                     plain-language walkthrough, no jargon
├── Makefile                          make regen / regen-all / check / workspace / open / clean
├── WORKSPACE_LAYOUT.md               Spencer 3-display layout — see make workspace
├── bloomberg-terminal.html           wealth dashboard — GENERATED, do not hand-edit its data
├── command-center.html               ops dashboard — GENERATED, do not hand-edit its data
├── data/
│   ├── wealthcommand.xlsx            wealth workbook — sheet CALC is the source of truth
│   └── command-center.xlsx           ops workbook — 11 sheets (BALANCES, FX_OPS, TRANSACTIONS, …)
├── scripts/
│   ├── regenerate_dashboard.py       patches bloomberg-terminal.html from wealthcommand.xlsx (CALC)
│   ├── generate_command_center.py    full rebuild of command-center.html from command-center.xlsx
│   ├── check_integrity.py            sheet-count + irreplaceable-file preflight (make check)
│   ├── backup.sh                     timestamped bundle + tarball outside iCloud
│   └── restore-personal-finance-layout.zsh   Spencer "Personal Finance" 3-display restore
├── reports/                          dated point-in-time snapshots (docx), not auto-updated
├── raw/                              original bank/receipt exports, by institution — feeds workbooks manually
└── nfce/                             standalone NFC-e inflation tracker — wired into bloomberg tab 11 only
```

## Commands

**Wealth dashboard (`bloomberg-terminal.html`):**
```bash
make regen     # patch bloomberg-terminal.html from data/wealthcommand.xlsx
make open      # regen, then open in the default browser (macOS `open`)
make check     # workbook sheet integrity + irreplaceable nfce/ files
make clean     # remove .DS_Store / __pycache__
make help      # list targets
```

Or run the patcher directly:
```bash
python3 scripts/regenerate_dashboard.py                          # defaults, patches in place
python3 scripts/regenerate_dashboard.py <xlsx> <html_in> <html_out>  # explicit paths
```

**Command center (`command-center.html`):**
```bash
python3 scripts/generate_command_center.py   # full rebuild from data/command-center.xlsx
open command-center.html                      # view (no make target yet)
```

**Both dashboards + Spencer workspace:**
```bash
make regen-all    # bloomberg-terminal.html + command-center.html
make check && make workspace   # integrity first, then regen-all + Spencer layout
zsh scripts/backup.sh          # verified backup under ~/Backups/Personal_Finance/
```
See **`WORKSPACE_LAYOUT.md`** for monitor arrangement, Stream Deck/Shortcut setup, and troubleshooting. Do not invent ad-hoc Spencer commands — use `scripts/restore-personal-finance-layout.zsh` or `make workspace`.

**Dependencies:**
- `regenerate_dashboard.py` needs `openpyxl` (on this Mac's system Python;
  elsewhere: `pip3 install --break-system-packages openpyxl`).
- `generate_command_center.py` needs **nothing beyond stdlib** — reads `.xlsx`
  as zip/XML directly.
- No venv. Don't add one, and don't add other dependencies unless the task
  genuinely requires them — see "Guardrails" below.

## Weekly workflows

Two dashboards → two notebooks → two generators. They **do not sync
automatically**. Overlapping fields (balances, card txs, subscriptions)
must be updated in **both** workbooks when both dashboards are in use.

### Combined weekly sequence (human or AI-assisted)

1. **Collect** — save new exports under `raw/` (unchanged originals).
2. **Wealth pass** — edit `data/wealthcommand.xlsx` sheet **`CALC`**
   (balances, `02 CAPITAL FLOWS`, Section 4D subscriptions). Run
   `make open`; confirm `[ok] all N spot-checks passed`.
3. **Ops pass** — edit `data/command-center.xlsx` input cells (see manual
   checklist in `USER_GUIDE.md` §4). Run
   `python3 scripts/generate_command_center.py`; confirm
   `[ok] wrote command-center.html` with no tag MISMATCH.
4. **Review** — open both HTML files. Compare cross-dashboard concepts
   (net worth, subscriptions, card spend). **Do not force-match** — see
   "Known open items".
5. **Reconcile** — if a gap is real, fix the **owning** workbook using
   `raw/` statements, then regenerate that dashboard again.

**Derived ops sheets:** `MONTHLY`, `CATEGORIES`, and `ALERTS` are usually
formula-driven from `TRANSACTIONS`, `FX_OPS`, `PIX`, and `CONFIG`.
Spot-check after input updates; don't maintain a parallel ledger outside
`FX_OPS`.

### Manual ops checklist (command-center.xlsx only)

When the user asks for a weekly review **without** AI, or you are doing
data entry only:

| Step | Sheet / range | Action |
|---|---|---|
| Balances | `BALANCES!A4:G17` | Input cells: balances, dates, notes |
| FX | `FX_OPS!A4:I45` | Append ops: Outbound / Inbound / IB Deposit / IB Withdraw / Fund Deposit |
| Card | `TRANSACTIONS!A4:G67` | Append txs; negative = spending; reuse categories |
| PIX | `PIX!A4:F41` | PIX / FX / IOF columns; verify totals |
| Subscriptions | `SUBSCRIPTIONS!A4:J27` | Dates, status, KEEP / CANCEL / REVIEW |
| Repos / projects | `REPOS!A4:J12`, `PROJECTS!A4:G15` | Status only — don't overwrite formula columns |
| Config | `CONFIG!A4:D16` | Thresholds — change only when preferences change |
| QA | all input sheets | Duplicates, signs, dates, currencies, formula errors |
| Regenerate | — | `python3 scripts/generate_command_center.py` — **never** edit `command-center.html` |

Wealth pass in parallel: `CALC` + `make open` (see `USER_GUIDE.md` §4).

### AI-assisted weekly review

When the user wants analysis **and** workbook updates from statements:

1. **Read this file (`AI_GUIDE.md`) first** — especially source-of-truth
   rules and "Known open items".
2. **Clarify scope** — wealth only, ops only, or both notebooks.
3. **Use `raw/` + regenerated dashboards** as inputs — not stale HTML.
4. **Update owning workbook(s)** — never HTML. For subscriptions also
   sync `CALC` Section 4D **and** `SUBSCRIPTIONS` when both dashboards
   matter. Reconcile `FX_OPS` against BCB/IB/Wise receipts — don't create
   a duplicate FX ledger elsewhere.
5. **Regenerate** after every workbook save; report generator verification
   output.
6. **Analysis output** should flag cross-dashboard gaps as reconciliation
   work (e.g. net-worth discrepancy from IB→Wise withdrawal treatment),
   not recommend picking one dashboard number over the other. Spending
   "caps" are personal budget rules — implement via categories and CONFIG
   thresholds, not a built-in feature.
7. **Privacy** — don't paste real figures into commit messages, PRs, or
   public contexts.

**Example user prompt:**

> Read `AI_GUIDE.md`, then perform my weekly review using the attached
> statements in `raw/`. Update **both** workbooks where overlapping data
> changed (`CALC` + command-center input sheets). Reconcile FX in
> `FX_OPS` against BCB/IB/Wise — do not create a separate ledger. Identify
> alerts, suggest KEEP/CANCEL/REVIEW for subscriptions, and flag any
> cross-dashboard discrepancies for reconciliation (do not force-match).
> Regenerate both dashboards and confirm generator verification passed.

**Example analysis-only prompt** (after the user already ran generators):

> Read `AI_GUIDE.md`. Review the regenerated `bloomberg-terminal.html` and
> `command-center.html`. Summarize alerts, highest-value actions, and any
> cross-dashboard gaps. Do not edit files — list which workbook cells to
> change and why.


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

## How command-center.html works — read this before changing it

`scripts/generate_command_center.py` is a **full generator** (not a patcher).
It reads `data/command-center.xlsx` (all 11 sheets via stdlib zip/XML), probes
the host iMac (`sw_vers`, `sysctl`) for the SYSTEM tab, and writes
`command-center.html` from scratch every run. CSS is copied from
`bloomberg-terminal.html` (SF Mono font stack substituted for Retina).

**Workbook sheets → dashboard tabs (1:1):**
BALANCES, FX_OPS, TRANSACTIONS, SUBSCRIPTIONS, PIX, MONTHLY, CATEGORIES,
ALERTS, REPOS, PROJECTS, CONFIG — plus a generated SYSTEM tab (host probe).

**Chart architecture (data-driven, unlike Bloomberg's hardcoded draw* fns):**
- Python embeds a `window.DATA` JSON blob (alloc, monthly, fxrate, flows,
  flowpie, subs, categories).
- Generic JS primitives draw from it: `pie()`, `bars()`, `drawMonthly(id)`,
  `drawFX()`, orchestrated by `initCharts()`.
- Tables are HTML rendered by Python, not drawn by the chart functions.

**Verification today:** tag-balance check only (`table/tr/td/div` counts).
No field-level spot-checks like the wealth patcher has. If you extend the
generator, consider adding checks.

**Keep this approach** unless the user asks to convert command-center to a
patcher model — the full-rebuild pattern is intentional for a new workbook.

## Known open items — do not silently resolve

- **Net Worth**: CALC says R$377,473.49 (`CALC!E137`). The workbook's own
  `01 NET WORTH` sheet, and the CMD CTR tile, say R$358,277. Traced to how
  the June IB→Wise withdrawal (R$19,195.81) is treated on `04 PORTFOLIO`.
  CALC is the declared source of truth, but the CMD CTR tile is still a
  Tier 2 hand-typed value — the discrepancy is real and unresolved.
- **IB Deployed**: same root cause. The tile shows the gross deposit figure
  (`CALC!E124`, R$197,706.57) where CALC's own KPI map says it should show
  the net-of-withdrawal figure (`CALC!E126` "IB NET DEPLOYED", R$178,510.76).

Both are documented in `README.md` → "Source of truth" and on the `10 DATA
MAP` tab. If asked to investigate or fix these, that means reconciling the
withdrawal treatment on `04 PORTFOLIO` against the actual bank statements
in `raw/` — not picking one existing number and forcing the other to match
it. If you resolve it, update both of those docs and the DATA MAP tab.

- **Wealth vs command-center net worth**: `command-center.xlsx` BALANCES
  shows R$377,473 (IB net deployed). `bloomberg-terminal.html` CMD CTR
  shows R$358,277. Same underlying data tension as above, but the command
  center uses the BALANCES-sheet formula directly with no DATA MAP audit
  tab. Do not silently harmonize without reconciling the withdrawal.

## Guardrails

Follow these unless the user explicitly asks otherwise in the moment:

- **Don't add infrastructure this project doesn't have**: no server, no
  database, no scheduler/cron, no build step, no venv, no test framework,
  no CI, no new external dependencies. This is a personal, single-user,
  weekly-cadence tool. If a task seems to need one of these, say so and ask
  before adding it, rather than adding it.
- **Don't rewrite `bloomberg-terminal.html` from scratch.** Patch it, per
  the pattern above.
- **Don't rewrite `command-center.html` by hand.** Regenerate it with
  `generate_command_center.py`. Edit the generator or the workbook instead.
- **Don't delete files** in `raw/`, `data/`, or `reports/` without asking —
  they hold real financial data with no other copy. (`archive/` used to
  exist for exactly this kind of superseded file; it was fully cleaned out
  and removed — there is currently no "soft delete" location, so anything
  removed is gone.)
- **Don't commit or push** unless the user explicitly asks. Push only to
  this project's private `origin` (not the archived `Personal_Finance`
  remote that now holds another project). Never commit secrets
  (`.env`, credentials) or paste real financial figures into commit messages.
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
  `personal_inflation_data.json` (tracked in git; generated 2026-08-19).
  **`nfce/notas/` is empty on this Mac** — source XMLs were not recovered
  from indexed storage; Time Machine is the only remaining place to look
  by hand. Until receipts land under `nfce/notas/NFCE_XML_*/`, tab 11 stays
  frozen. Then: `cd nfce && python3 personal_inflation.py --verify-ground-truth`,
  then `make regen` again.
  Separately: **4 small receipt `.txt` files were lost** during the
  2026-08-31 `nfce01` → `nfce` merge (a `find -type f` bug skipped them
  before `nfce01` was deleted) — no other copy exists on this Mac or in
  `financas-2026`'s git history. The computed output already captured
  them, so no dashboard number is wrong, but future receipt-recount work
  should know 21 of the original 499 receipts' raw files are gone.
- **Dead reference CSVs removed (2026-08-31)** — `cancel_tracker.csv` and
  `weekly_tracker.csv` from the old financas-2026 import were duplicates
  of data already in `CALC` / live WEEKLY ROLLUP. Do not reintroduce them
  as a second source.

## Verifying your own work

Don't declare a change done without checking it:

**Wealth dashboard:**
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

**Command center:**
1. Run `python3 scripts/generate_command_center.py` and confirm
   `[ok] all N ops spot-checks passed` and `[ok] wrote command-center.html`
   with matching tag counts (no MISMATCH).
2. Re-run immediately — output should be identical (idempotent rebuild).
3. Spot-check CMD CTR, FX OPS (rate chart), TRANSACTIONS (search), and
   SYSTEM tabs in a browser if available.

**Integrity (both):**
1. Run `make check` after any workbook edit and before trusting `make workspace`.
2. Run `zsh scripts/backup.sh` after material data changes (writes under
   `~/Backups/Personal_Finance/`).
