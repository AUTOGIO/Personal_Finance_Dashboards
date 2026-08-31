#!/usr/bin/env python3
"""
regenerate_dashboard.py

Patches bloomberg-terminal.html against wealthcommand.xlsx (CALC = single
source of truth). Does NOT rebuild the file from scratch — it does targeted,
anchored replacements of the specific figures/tables proven to be stale or
truncated vs. the source workbook. Everything else in the HTML (CSS, layout,
chart JS, all other tabs/numbers) is left untouched.

Fixes applied (all traced to wealthcommand.xlsx / CALC sheet):
  1. Subscriptions tab + CMD CTR tile + ticker: Total Stack, KEEP/mo,
     REVIEW/mo were stale (hand-typed, drifted from the register table).
  2. drawSubs() pie chart data array: same KEEP/REVIEW drift.
  3. Alert #3 (Sub Stack Bloat): said "6 services / ~R$5,400/yr", CALC's
     Section 4D says 7 services / R$7,763.28/yr.
  4. TX LOG tab: table only rendered 43 of 146 MP Cartão rows behind a
     placeholder. Now renders the full 146.
  5. LIFESTYLE tab ML+iFood table: only rendered 15 of 69 rows. Now renders
     the full 69, and the panel's item-count label is corrected to match.
  6. "Generated ... Source: financas2026-DataEntry + ..." (CMD CTR header +
     ticker) named a file that doesn't exist (leftover from an old pipeline
     that was never built). Replaced with the real source and today's date.

Deliberately NOT touched: the Net Worth figure (R$358,277 in CMD CTR / 01
NET WORTH vs R$377,473.49 in CALC). That gap traces to how the June IB→Wise
withdrawal is treated in 04 PORTFOLIO, which is an open data question, not a
stale-label bug — forcing one number over the other here would hide it
instead of fixing it. Flagged separately for the user to decide.

Usage:
    python3 scripts/regenerate_dashboard.py
        (defaults: data/wealthcommand.xlsx -> bloomberg-terminal.html, in place)

    python3 scripts/regenerate_dashboard.py <xlsx> <html_in> <html_out>
        (explicit paths, e.g. to preview into a scratch file first)
"""
import argparse
import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path

import openpyxl

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_XLSX = REPO_ROOT / "data" / "wealthcommand.xlsx"
DEFAULT_HTML = REPO_ROOT / "bloomberg-terminal.html"
NFCE_DATA = REPO_ROOT / "nfce" / "personal_inflation_data.json"


def load_calc(xlsx_path):
    wb = openpyxl.load_workbook(xlsx_path, data_only=True)
    calc = wb["CALC"]

    def cell(r, c):
        return calc.cell(r, c).value

    # Section 4D — subscription decision totals (rows 343-346)
    # cols: B=decision C=count D=mo E=yr (confirmed via reconnaissance)
    decisions = {}
    for r in range(343, 347):
        label = cell(r, 2)
        if label in ("CANCEL", "KEEP", "REVIEW"):
            decisions[label] = {
                "count": cell(r, 3),
                "mo": cell(r, 4),
                "yr": cell(r, 5),
            }
    return wb, decisions


def count_table_rows(html, header_pattern):
    """Count actual <tr> data rows inside the table whose header row matches
    header_pattern, up to the next </table>. Returns None if not found.
    Used for verification — checks the real table content, not a separate
    label that might say the right number while pointing at nothing."""
    m = re.search(header_pattern + r'(.*?)</table>', html, re.S)
    if not m:
        return None
    return len(re.findall(r'<tr[ >]', m.group(1)))  # matches <tr> and <tr style=...> alike


def fmt_money(v, decimals=2):
    if decimals == 0:
        return f"{round(v):,}"
    return f"{v:,.{decimals}f}"


def build_tx_rows(wb):
    ws = wb["02 CAPITAL FLOWS"]
    rows = []
    for r in range(15, 222):
        source = ws.cell(r, 3).value
        if source != "MP Cartão":
            continue
        date = ws.cell(r, 2).value
        category = ws.cell(r, 4).value or ""
        desc = ws.cell(r, 5).value or ""
        amount = ws.cell(r, 6).value or 0
        notes = ws.cell(r, 9).value or ""
        fatura = notes.replace("Fatura ", "").strip() if notes else ""
        intl = "Sim" if "internacional" in desc.lower() else "Não"
        merchant = desc
        # strip the "Compra internacional em " prefix for readability, matches
        # how the hand-built table already displayed these merchants
        merchant = re.sub(r"^Compra internacional em\s+", "", merchant, flags=re.I)
        cat_class = ""
        if category == "IA/Tecnologia":
            cat_class = ' class="yellow"'
        elif category == "Loteria":
            cat_class = ' class="orange"'
        intl_class = ' class="yellow"' if (intl == "Sim" and cat_class == ' class="yellow"') else ""
        amt_class = "num red"
        if category == "Viagem":
            amt_class = "num orange"
        date_str = date.strftime("%Y-%m-%d") if hasattr(date, "strftime") else str(date)
        amt_str = fmt_money(abs(amount))
        rows.append(
            f'<tr><td>{date_str}</td><td>{fatura}</td><td>{merchant}</td>'
            f'<td class="{amt_class}">−{amt_str}</td><td{cat_class}>{category}</td>'
            f'<td{intl_class}>{intl}</td></tr>'
        )
    return rows


def build_weekly_rows(wb):
    """Weekly MP Cartão spend, grouped Mon-Sun, computed live from the same
    02 CAPITAL FLOWS rows TX LOG renders. Added 2026-08-31 to cover the view
    financas-2026's old "Weekly Tracker" sheet had, WITHOUT importing that
    sheet's frozen CSV snapshot as a second, driftable source of truth --
    this recomputes from CALC's own upstream data every run instead."""
    ws = wb["02 CAPITAL FLOWS"]
    weeks = {}
    for r in range(15, 222):
        if ws.cell(r, 3).value != "MP Cartão":
            continue
        d = ws.cell(r, 2).value
        if not d:
            continue
        if hasattr(d, "date"):
            d = d.date()
        amount = ws.cell(r, 6).value or 0
        monday = d - timedelta(days=d.weekday())
        wk = weeks.setdefault(monday, {"spend": 0.0, "count": 0})
        wk["spend"] += abs(amount)
        wk["count"] += 1

    rows = []
    total_spend = 0.0
    total_count = 0
    for monday in sorted(weeks):
        sunday = monday + timedelta(days=6)
        spend = weeks[monday]["spend"]
        count = weeks[monday]["count"]
        total_spend += spend
        total_count += count
        rows.append(
            f'<tr><td>{monday.strftime("%Y-%m-%d")}</td><td>{sunday.strftime("%Y-%m-%d")}</td>'
            f'<td class="num red">{fmt_money(spend)}</td><td class="num">{count}</td></tr>'
        )
    rows.append(
        '<tr style="border-top:1px solid var(--border2);font-weight:600;">'
        f'<td colspan="2">TOTAL</td><td class="num red">{fmt_money(total_spend)}</td>'
        f'<td class="num">{total_count}</td></tr>'
    )
    return rows, total_spend, total_count


def build_lifestyle_rows(wb):
    ws = wb["05 LIFESTYLE"]
    rows = []
    for r in range(34, 103):
        date = ws.cell(r, 2).value
        platform = ws.cell(r, 3).value
        if not date or not platform:
            continue
        item = ws.cell(r, 4).value or ""
        amount = ws.cell(r, 5).value or 0
        category = ws.cell(r, 6).value or ""
        status = (ws.cell(r, 7).value or "").strip().lower()
        plat_short = "ML" if platform == "Mercado Livre" else platform
        if status == "delivered":
            badge = '<span class="badge badge-ok">✓ DELIV</span>'
            amt_class = "num"
        elif status == "failed":
            badge = '<span class="badge badge-cancel">✗ FAILED</span>'
            amt_class = "num red"
        else:  # cancelled
            badge = '<span class="badge badge-cancel">✗ CANCEL</span>'
            amt_class = "num red"
        if amount >= 1000:
            amt_class = (amt_class + " orange").strip()
        rows.append(
            f'<tr><td>{date}</td><td>{plat_short}</td><td>{item}</td>'
            f'<td class="{amt_class}">{fmt_money(amount)}</td><td>{category}</td>'
            f'<td>{badge}</td></tr>'
        )
    return rows


def build_nfce_page(data):
    """Renders the '11 NFC-E' tab from nfce/personal_inflation_data.json.
    This is a SEPARATE tracker from wealthcommand.xlsx/CALC (different data
    entirely -- grocery/pharmacy receipt inflation, not account balances).
    It is a point-in-time snapshot (generated 2026-08-19 from 499 receipts),
    NOT recomputed by this script -- re-run nfce/personal_inflation.py
    against real NFC-e receipts to refresh personal_inflation_data.json,
    then re-run this script to re-patch the tab with the new numbers."""
    k = data["kpis"]
    from_month = data["index"][0]["m"]

    yoy_rows = "\n          ".join(
        f'<tr><td>{y["year"]}{" (partial)" if y.get("partial") else ""}</td>'
        f'<td class="num{" yellow" if y["personal"]>y["ipca"] else " green"}">{y["personal"]:+.2f}%</td>'
        f'<td class="num gray">{y["ipca"]:+.2f}%</td></tr>'
        for y in data["yoy"][-8:]
    )

    cats = sorted(data["categories"], key=lambda c: -c.get("spend", 0))[:8]
    cat_rows = "\n          ".join(
        f'<tr><td>{c["cat"]}</td><td class="num">{fmt_money(c["spend"], 0)}</td>'
        f'<td class="num yellow">{c["cum_pct"]:+.1f}%</td></tr>'
        for c in cats
    )

    def prod_row(p, cls):
        desc = p["desc"].strip()
        if len(desc) > 34:
            desc = desc[:33] + "\u2026"
        return (f'<tr><td>{desc}</td><td class="num {cls}">{p["ann_pct"]:+.1f}%</td></tr>')

    riser_rows = "\n          ".join(prod_row(p, "red") for p in data["risers"][:6])
    faller_rows = "\n          ".join(prod_row(p, "green") for p in data["fallers"][:6])

    return f'''<div class="page" id="p-nfce">
  <div class="panel" style="margin-bottom:6px;">
    <div class="ph">NFC-E PERSONAL INFLATION <span class="ph-sub">Household inflation from your own grocery/pharmacy receipts</span></div>
    <div class="kpi-grid">
      <div class="kpi"><div class="kpi-lbl">Cumulative</div><div class="kpi-val red">{k["cum_pct"]:.1f}%</div></div>
      <div class="kpi"><div class="kpi-lbl">Annualized</div><div class="kpi-val yellow">{k["ann_pct"]:.2f}%/yr</div></div>
      <div class="kpi"><div class="kpi-lbl">YoY (12mo)</div><div class="kpi-val yellow">{k["yoy12_pct"]:.2f}%</div></div>
      <div class="kpi"><div class="kpi-lbl">Tracked Spend</div><div class="kpi-val orange">R$ {fmt_money(k["total_spend"], 0)}</div></div>
    </div>
    <div style="padding:8px 10px 4px;color:var(--gray);font-size:10px;line-height:1.6;">
      Snapshot from <strong style="color:var(--white)">{k["receipts"]} receipts</strong> &middot; {k["tracked_products"]} products tracked
      &middot; {k["coverage_pct"]:.0f}% category coverage &middot; {from_month} to {k["last_month"]}.
      This is <strong style="color:var(--white)">separate from CALC</strong> and does not update with <code>make regen</code> --
      it is a point-in-time run of <code>nfce/personal_inflation.py</code>, generated 2026-08-19.
      Re-run that script against real NFC-e receipts, then re-run <code>make regen</code>, to refresh this tab.
    </div>
  </div>

  <div class="row">
    <div class="col-2">
      <div class="panel">
        <div class="ph">YEAR OVER YEAR <span class="ph-sub">Personal index vs. official IPCA</span></div>
        <table class="bt">
          <tr><th>YEAR</th><th class="num">PERSONAL</th><th class="num">IPCA</th></tr>
          {yoy_rows}
        </table>
      </div>
    </div>
    <div class="col-2">
      <div class="panel">
        <div class="ph">TOP CATEGORIES BY SPEND</div>
        <table class="bt">
          <tr><th>CATEGORY</th><th class="num">SPEND (R$)</th><th class="num">CUM %</th></tr>
          {cat_rows}
        </table>
      </div>
    </div>
  </div>

  <div class="row">
    <div class="col-2">
      <div class="panel">
        <div class="ph">TOP RISERS <span class="ph-sub">biggest price increases, annualized</span></div>
        <table class="bt">
          <tr><th>PRODUCT</th><th class="num">ANN %</th></tr>
          {riser_rows}
        </table>
      </div>
    </div>
    <div class="col-2">
      <div class="panel">
        <div class="ph">TOP FALLERS <span class="ph-sub">biggest price drops, annualized</span></div>
        <table class="bt">
          <tr><th>PRODUCT</th><th class="num">ANN %</th></tr>
          {faller_rows}
        </table>
      </div>
    </div>
  </div>
</div>
'''


def patch(html, wb, decisions):
    keep_mo, cancel_mo, review_mo = (
        decisions["KEEP"]["mo"], decisions["CANCEL"]["mo"], decisions["REVIEW"]["mo"]
    )
    total_mo = keep_mo + cancel_mo + review_mo
    total_disp = fmt_money(total_mo, 0)
    keep_disp = fmt_money(keep_mo)
    review_disp = fmt_money(review_mo)
    review_yr = decisions["REVIEW"]["yr"]
    review_count = int(decisions["REVIEW"]["count"])

    n = 0

    # 1. CMD CTR "Sub Stack/mo" tile
    html, c = re.subn(
        r'(<div class="kpi-lbl">Sub Stack/mo</div><div class="kpi-val red">R\$ )1,247',
        rf'\g<1>{total_disp}', html
    )
    n += c

    # 2. Ticker "SUB STACK"
    html, c = re.subn(
        r'(SUB STACK <span class="tick-dn">R\$)1,247(/mo</span>)',
        rf'\g<1>{total_disp}\g<2>', html
    )
    n += c

    # 3. SUBS tab: Total Stack / KEEP / REVIEW tiles
    html, c = re.subn(
        r'(<div class="kpi-lbl">Total Stack/mo</div><div class="kpi-val red">R\$ )1,247',
        rf'\g<1>{total_disp}', html
    )
    n += c
    html, c = re.subn(
        r'(<div class="kpi-lbl">KEEP/mo</div><div class="kpi-val green">R\$ )431\.80',
        rf'\g<1>{keep_disp}', html
    )
    n += c
    html, c = re.subn(
        r'(<div class="kpi-lbl">REVIEW/mo</div><div class="kpi-val yellow">R\$ )449\.48',
        rf'\g<1>{review_disp}', html
    )
    n += c

    # 4. drawSubs() pie chart data
    html, c = re.subn(r"\{label:'KEEP',v:431\.8,", f"{{label:'KEEP',v:{round(keep_mo,2)},", html)
    n += c
    html, c = re.subn(r"\{label:'REVIEW',v:449\.48,", f"{{label:'REVIEW',v:{round(review_mo,2)},", html)
    n += c

    # 5. Alert #3 — two hand-typed copies (CMD CTR priority-actions panel
    # (short form) + full 08 ALERTS register (long form)), both stale.
    yr_disp = fmt_money(review_yr, 0)
    html, c = re.subn(
        r'6 services in REVIEW status · undecided',
        f'{review_count} services in REVIEW status · undecided', html
    )
    n += c
    html, c = re.subn(
        r'6 services in REVIEW status\. Annual exposure ~R\$5,400\.',
        f'{review_count} services in REVIEW status. R${review_disp}/mo (~R${yr_disp}/yr).',
        html
    )
    n += c
    html, c = re.subn(r'~5,400/yr', f'~{yr_disp}/yr', html)
    n += c

    print(f"[patch] {n} inline substitutions applied (expected 10)")

    # 6. TX LOG full table
    tx_rows = build_tx_rows(wb)
    old_tx = re.search(
        r'(<table class="bt" id="tx-table">\s*<tr><th>DATE</th>.*?</tr>\n)(.*?)(</table>)',
        html, re.S
    )
    if not old_tx:
        print("[warn] tx-table anchor not found — skipping TX LOG patch")
    else:
        new_body = "\n    " + "\n    ".join(tx_rows) + "\n  "
        html = html[:old_tx.start(2)] + new_body + html[old_tx.end(2):]
        print(f"[patch] TX LOG: rendered {len(tx_rows)} rows (was truncated to 43 + placeholder)")

    # 7. LIFESTYLE ML+iFood full table
    life_rows = build_lifestyle_rows(wb)
    old_life = re.search(
        r'(<tr><th>DATE</th><th>PLATFORM</th><th>ITEM</th><th class="num">VALUE</th><th>CATEGORY</th><th>STATUS</th></tr>\n)(.*?)(</table>)',
        html, re.S
    )
    if not old_life:
        print("[warn] ML+iFood table anchor not found — skipping LIFESTYLE patch")
    else:
        new_body = "      " + "\n      ".join(life_rows) + "\n    "
        html = html[:old_life.start(2)] + new_body + html[old_life.end(2):]
        html, c = re.subn(r'75 items · R\$27,489 total', f'{len(life_rows)} items · R$27,489 total', html)
        print(f"[patch] LIFESTYLE: rendered {len(life_rows)} rows (was truncated to 15), label {'updated now' if c else 'already correct'}")

    # 7b. WEEKLY ROLLUP — NEW (2026-08-31). See build_weekly_rows() docstring:
    # same underlying rows as TX LOG, grouped by week, recomputed live.
    weekly_rows, weekly_total_spend, weekly_total_count = build_weekly_rows(wb)
    weekly_anchor = "  <!-- search bar -->"
    if weekly_anchor not in html:
        print("[warn] weekly-rollup anchor not found — skipping WEEKLY ROLLUP patch")
    else:
        panel = (
            '  <div class="panel" style="margin-bottom:6px;" id="weekly-rollup-panel">\n'
            '    <div class="ph">WEEKLY ROLLUP · MP Cart\u00e3o spend by week (derived live from TX LOG rows)</div>\n'
            '    <div style="max-height:220px;overflow-y:auto;">\n'
            '    <table class="bt" id="weekly-rollup-table">\n'
            '      <tr><th>WEEK START</th><th>WEEK END</th><th class="num">BRL</th><th class="num">TXS</th></tr>\n'
            + "\n".join("      " + r for r in weekly_rows) + "\n"
            '    </table>\n'
            '    </div>\n'
            '  </div>\n'
        )
        if 'id="weekly-rollup-panel"' in html:
            # already patched in a previous run — replace the whole existing panel, not duplicate it
            html, c = re.subn(
                r'  <div class="panel" style="margin-bottom:6px;" id="weekly-rollup-panel">.*?\n  </div>\n',
                panel, html, count=1, flags=re.S
            )
        else:
            html = html.replace(weekly_anchor, panel + weekly_anchor, 1)
        print(f"[patch] WEEKLY ROLLUP: rendered {len(weekly_rows)-1} weeks (R${fmt_money(weekly_total_spend,0)} total / {weekly_total_count} txs)")

    # 8. Fix the fake "Source: financas2026-DataEntry" line (that file never
    # existed — leftover from an old pipeline) and stamp the real regen date.
    # Only re-stamps the date if the stale text is still there — once fixed,
    # the date freezes until something reverts it (not re-stamped every run).
    today = date.today().strftime("%-d %b %Y")
    html, c1 = re.subn(
        r'Generated \d+ \w+ \d{4} · Source: financas2026-DataEntry \+ WealthCommand_V3 \+ BCB Câmbio',
        f'Generated {today} · Source: data/wealthcommand.xlsx (CALC)', html
    )
    html, c2 = re.subn(
        r'SOURCE financas2026-DataEntry · WealthCommand_V3 · BCB Câmbio · \w+ \d{4}',
        f'SOURCE data/wealthcommand.xlsx (CALC) · {today}', html
    )
    print(f"[patch] source line: header={'updated now' if c1 else 'already correct'}, ticker={'updated now' if c2 else 'already correct'}")

    # 8b. NFC-E PERSONAL INFLATION tab — NEW (2026-08-31). Separate tracker,
    # separate data file (nfce/personal_inflation_data.json), not from CALC.
    nfce_data = None
    if NFCE_DATA.exists():
        nfce_data = json.loads(NFCE_DATA.read_text(encoding="utf-8"))
        nfce_tab = '  <div class="tab" onclick="showPage(\'nfce\')">11 NFC-E</div>\n'
        datamap_tab = '  <div class="tab" onclick="showPage(\'datamap\')">10 DATA MAP</div>\n'
        if datamap_tab in html and nfce_tab not in html:
            html = html.replace(datamap_tab, datamap_tab + nfce_tab, 1)

        nfce_page = build_nfce_page(nfce_data)
        content_end = "</div><!-- /content -->"
        if 'id="p-nfce"' in html:
            html, _ = re.subn(
                r'<div class="page" id="p-nfce">.*?\n</div>\n', nfce_page, html, count=1, flags=re.S
            )
        elif content_end in html:
            html = html.replace(content_end, nfce_page + content_end, 1)
        print(f"[patch] NFC-E tab: rendered ({nfce_data['kpis']['receipts']} receipts, "
              f"cum {nfce_data['kpis']['cum_pct']}%, yoy12 {nfce_data['kpis']['yoy12_pct']}%)")
    else:
        print("[warn] nfce/personal_inflation_data.json not found — skipping NFC-E tab patch")

    # 9. Final sync check. Every subn above reports 0/no-op identically
    # whether "already correct" or "anchor broken" — that ambiguity is exactly
    # the kind of bug this whole project exists to catch, so don't ship it in
    # the tool itself. Confirm the CURRENT correct value is actually present,
    # regardless of which run put it there.
    checks = [
        ("CMD CTR Sub Stack/mo tile", f'<div class="kpi-lbl">Sub Stack/mo</div><div class="kpi-val red">R$ {total_disp}'),
        ("SUBS tab Total Stack tile", f'<div class="kpi-lbl">Total Stack/mo</div><div class="kpi-val red">R$ {total_disp}'),
        ("SUBS tab KEEP tile", f'<div class="kpi-lbl">KEEP/mo</div><div class="kpi-val green">R$ {keep_disp}'),
        ("SUBS tab REVIEW tile", f'<div class="kpi-lbl">REVIEW/mo</div><div class="kpi-val yellow">R$ {review_disp}'),
        ("ticker SUB STACK", f'SUB STACK <span class="tick-dn">R${total_disp}/mo</span>'),
        ("pie chart KEEP slice", f"{{label:'KEEP',v:{round(keep_mo,2)},"),
        ("pie chart REVIEW slice", f"{{label:'REVIEW',v:{round(review_mo,2)},"),
        ("Alert #3 short form", f'{review_count} services in REVIEW status · undecided'),
        ("Alert #3 long form", f'{review_count} services in REVIEW status. R${review_disp}/mo (~R${yr_disp}/yr).'),
        ("Alert #3 exposure cell", f'~{yr_disp}/yr'),
        ("source line (header)", 'Source: data/wealthcommand.xlsx (CALC)'),
        ("source line (ticker)", 'SOURCE data/wealthcommand.xlsx (CALC)'),
    ]
    missing = [name for name, s in checks if s not in html]

    # Row counts are checked structurally (actual <tr> inside the real
    # table), not by trusting a nearby label that could say the right number
    # while pointing at stale or unrelated content.
    tx_actual = count_table_rows(
        html, r'<tr><th>DATE</th><th>FATURA</th><th>MERCHANT</th><th class="num">BRL</th><th>CATEGORY</th><th>INTL</th></tr>\n'
    )
    if tx_actual != len(tx_rows):
        missing.append(f"TX LOG table has {tx_actual} rows, expected {len(tx_rows)}")

    life_actual = count_table_rows(
        html, r'<tr><th>DATE</th><th>PLATFORM</th><th>ITEM</th><th class="num">VALUE</th><th>CATEGORY</th><th>STATUS</th></tr>\n'
    )
    if life_actual != len(life_rows):
        missing.append(f"LIFESTYLE table has {life_actual} rows, expected {len(life_rows)}")

    weekly_actual = count_table_rows(
        html, r'<tr><th>WEEK START</th><th>WEEK END</th><th class="num">BRL</th><th class="num">TXS</th></tr>\n'
    )
    expected_weekly_rows = len(weekly_rows)  # includes the TOTAL row
    if weekly_actual != expected_weekly_rows:
        missing.append(f"WEEKLY ROLLUP table has {weekly_actual} rows, expected {expected_weekly_rows}")
    if f'{fmt_money(weekly_total_spend)}' not in html.split('id="weekly-rollup-panel"', 1)[-1].split("</table>", 1)[0]:
        missing.append("WEEKLY ROLLUP total spend not found in its own table")

    if nfce_data is not None:
        nk = nfce_data["kpis"]
        if 'id="p-nfce"' not in html:
            missing.append("NFC-E tab (p-nfce) not found in HTML")
        else:
            nfce_section = html.split('id="p-nfce"', 1)[1].split("</div>\n\n  <div class=\"row\">", 1)[0]
            if f'{nk["cum_pct"]:.1f}%' not in nfce_section:
                missing.append("NFC-E cumulative % not found in its own tab")
            if f'{nk["receipts"]} receipts' not in nfce_section:
                missing.append("NFC-E receipt count not found in its own tab")
        if '<div class="tab" onclick="showPage(\'nfce\')">11 NFC-E</div>' not in html:
            missing.append("NFC-E nav tab not found")
        total_checks_nfce = 3
    else:
        total_checks_nfce = 0

    total_checks = len(checks) + 3 + total_checks_nfce
    if missing:
        print(f"[WARNING] {len(missing)}/{total_checks} check(s) failed — something's actually broken, look here: {'; '.join(missing)}")
    else:
        print(f"[ok] all {total_checks} spot-checks passed — dashboard confirmed in sync with the workbook")

    return html


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("xlsx", nargs="?", default=str(DEFAULT_XLSX), help=f"source workbook (default: {DEFAULT_XLSX.relative_to(REPO_ROOT)})")
    p.add_argument("html_in", nargs="?", default=str(DEFAULT_HTML), help=f"template HTML to patch (default: {DEFAULT_HTML.relative_to(REPO_ROOT)})")
    p.add_argument("html_out", nargs="?", default=None, help="output path (default: same as html_in, i.e. patch in place)")
    args = p.parse_args()

    xlsx_path = Path(args.xlsx)
    html_in = Path(args.html_in)
    html_out = Path(args.html_out) if args.html_out else html_in

    if not xlsx_path.exists():
        sys.exit(f"[error] workbook not found: {xlsx_path}")
    if not html_in.exists():
        sys.exit(f"[error] template HTML not found: {html_in}")

    wb, decisions = load_calc(str(xlsx_path))
    html = html_in.read_text(encoding="utf-8")
    html = patch(html, wb, decisions)
    html_out.write_text(html, encoding="utf-8")
    print(f"[done] wrote {html_out} ({len(html)} bytes)")


if __name__ == "__main__":
    main()
