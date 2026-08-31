# User Guide — How This Money Tracker Works

This explains the whole project in plain language. If you can double-click
an icon and copy-paste a line of text, you can use this.

## 1. What even is this?

This is a family money tracker. It has two parts:

1. **A notebook** — a spreadsheet file called `wealthcommand.xlsx` where
   every real number lives (how much money is in each bank, what
   subscriptions cost, etc.)
2. **A poster** — a file called `bloomberg-terminal.html` that shows all
   those numbers on a cool dark screen that looks like something out of a
   spy movie.

The important rule: **the poster is made FROM the notebook.** You never
write on the poster directly — you write in the notebook, and then you
print a new poster from it. More on that in section 4.

## 2. How to look at the dashboard

1. Find the file named `bloomberg-terminal.html` in the project folder.
2. Double-click it. It opens in your web browser (Safari, Chrome, whatever).
3. That's it — no login, no internet needed, no app to install.

## 3. What all the buttons do

- **Tabs across the top** (`00 CMD CTR`, `01 NET WORTH`, `06 SUBSCRIPTIONS`,
  etc.) — click one to switch pages. Each tab is a different topic (bank
  balances, subscriptions to cancel, big purchases, and so on).
- **`A−` / `A+` buttons, top right** — makes everything on the page bigger
  or smaller. There's a `100%` number between them that shows the current
  size.
- **Search boxes** (only on some tabs, like `09 TX LOG`) — type a word (like
  a store name) and the table below filters to just show matching rows.
- **Scrolling** — if a page has more stuff than fits on your screen, just
  scroll down like any normal webpage now.

Nothing you click can break anything or delete any data. It's just a
screen for looking — feel free to click around.

## 4. How to update it (the weekly job)

Every week, new numbers need to go in. Here's the whole process:

1. **Open the notebook.** Double-click `data/wealthcommand.xlsx`. It opens
   in Excel (or Numbers).
2. **Find the sheet (tab) called `CALC`.** That's the ONE sheet that
   matters — it's the "real" numbers. (The workbook has other sheets too,
   but `CALC` is the boss of all of them.)
3. **Type in the new numbers** for the week — new bank balances, new
   purchases, whatever changed. Save the file (Cmd+S) and close it.
4. **Now "print" the new poster.** This is the only slightly technical
   step:
   - Open the **Terminal** app (search for "Terminal" with Spotlight —
     the magnifying glass icon top-right of the screen, or Cmd+Space).
   - A window with text shows up. Type this exactly and press Enter:
     ```
     cd ~/Documents/GitHub/Personal_Finance && make open
     ```
   - Wait a couple seconds. Your browser will pop open automatically with
     the freshly updated dashboard.

That's the entire ritual. If step 4 ever looks scary or throws an error,
that's normal — just ask an adult (or Claude) to run it for you.

## 5. What each folder is (in plain words)

```
Personal_Finance/
├── bloomberg-terminal.html   the poster — double-click to look at it
├── data/wealthcommand.xlsx   the notebook — the only file you type new numbers into
├── raw/                      a filing cabinet of the original bank statements/receipts
├── reports/                  old printed summaries (like a school report card, one per date)
├── scripts/                  the "printer" — the program that turns the notebook into the poster
└── Makefile                  a cheat-sheet of short commands (like "make open")
```

You will basically only ever touch `data/wealthcommand.xlsx` (to type
numbers) and `bloomberg-terminal.html` (to look at the result). Everything
else runs itself.

## 6. The three golden rules

1. **Never delete `data/wealthcommand.xlsx`.** It's the only copy of the
   real numbers. Everything else can be rebuilt from it; it can't be
   rebuilt from anything else.
2. **Never type numbers directly into `bloomberg-terminal.html`.** It gets
   overwritten every time someone runs `make open` — anything you typed
   there by hand would just vanish. Numbers only go in the notebook
   (`CALC` sheet).
3. **If a number on the dashboard looks wrong,** the notebook's `CALC`
   sheet is always right (it's the "source of truth" — the one everyone
   trusts). If something disagrees with `CALC`, `CALC` wins.

## 7. If something looks broken

- **Dashboard shows old numbers** → someone edited the notebook but forgot
  to run `make open`. Just run it (section 4, step 4).
- **A tab looks weird or numbers are cut off** → try clicking `A−` once or
  twice to shrink things back down.
- **Terminal says something you don't understand** → that's fine, copy the
  message and ask an adult or Claude what it means.

See `README.md` for the more technical version of all this, and
`LEIA-ME.md` for the Portuguese weekly-ritual checklist.
