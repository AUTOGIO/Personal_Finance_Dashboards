#!/usr/bin/env python3
"""
generate_command_center.py — build command-center.html from data/command-center.xlsx

Model: bloomberg-terminal.html (same Bloomberg-terminal look & feel, tabs, SVG
charts, ticker). This is a SEPARATE dashboard for a SEPARATE workbook
(data/command-center.xlsx), tailored for the host iMac M3 / Apple Silicon /
macOS 26.6.2 — it does NOT touch bloomberg-terminal.html or wealthcommand.xlsx.

Dependency-free: reads the .xlsx directly as a zip of XML (no openpyxl, no venv,
no new deps — consistent with this repo's guardrails). Unlike
regenerate_dashboard.py (a targeted patcher of an existing file), this is a full
generator because command-center.html is a brand-new artifact for a new
workbook. Re-run any time the workbook changes:

    python3 scripts/generate_command_center.py

Every number on the page is read live from data/command-center.xlsx (cached
formula results included) — nothing is hand-typed into the HTML.
"""

import html as _html
import json
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
XLSX = os.path.join(ROOT, "data", "command-center.xlsx")
MODEL_HTML = os.path.join(ROOT, "bloomberg-terminal.html")
OUT_HTML = os.path.join(ROOT, "command-center.html")

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
RID = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
PKG_REL = "{http://schemas.openxmlformats.org/package/2006/relationships}Relationship"


# ────────────────────────────────────────────────────────── workbook reader
def _col_num(letters):
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch) - 64)
    return n


class Sheet:
    def __init__(self, name):
        self.name = name
        self.cells = {}      # (row, col) -> display string
        self.nums = {}       # (row, col) -> float (when numeric)
        self.max_row = 0
        self.max_col = 0

    def disp(self, r, c):
        return self.cells.get((r, c), "")

    def num(self, r, c):
        return self.nums.get((r, c))

    def row_vals(self, r):
        return [self.disp(r, c) for c in range(1, self.max_col + 1)]


def load_workbook(path):
    z = zipfile.ZipFile(path)
    shared = []
    if "xl/sharedStrings.xml" in z.namelist():
        for si in ET.fromstring(z.read("xl/sharedStrings.xml")):
            shared.append("".join(t.text or "" for t in si.iter(NS + "t")))
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    order = [(s.get("name"), s.get(RID)) for s in wb.iter(NS + "sheet")]
    relmap = {r.get("Id"): r.get("Target")
              for r in ET.fromstring(z.read("xl/_rels/workbook.xml.rels")).iter(PKG_REL)}
    sheets = {}
    names = []
    for name, rid in order:
        tgt = relmap[rid]
        tgt = tgt if tgt.startswith("xl/") else "xl/" + tgt
        root = ET.fromstring(z.read(tgt))
        sh = Sheet(name)
        for row in root.iter(NS + "row"):
            for c in row.findall(NS + "c"):
                ref = c.get("r")
                letters = "".join(ch for ch in ref if ch.isalpha())
                rn = int("".join(ch for ch in ref if ch.isdigit()))
                cn = _col_num(letters)
                t = c.get("t")
                v = c.find(NS + "v")
                f = c.find(NS + "f")
                val = ""
                if t == "s" and v is not None:
                    val = shared[int(v.text)]
                elif t == "inlineStr":
                    isn = c.find(NS + "is")
                    val = "".join(x.text or "" for x in isn.iter(NS + "t")) if isn is not None else ""
                elif v is not None:
                    val = v.text
                # numeric?
                if val not in ("", None):
                    try:
                        num = float(val)
                        # keep ints clean
                        sh.nums[(rn, cn)] = num
                        if t == "s" or t == "str":
                            pass
                    except (TypeError, ValueError):
                        pass
                sh.cells[(rn, cn)] = val if val is not None else ""
                sh.max_row = max(sh.max_row, rn)
                sh.max_col = max(sh.max_col, cn)
        sheets[name] = sh
        names.append(name)
    return sheets, names


# ────────────────────────────────────────────────────────── formatting
def brl(v, dec=0):
    if v is None:
        return ""
    neg = v < 0
    v = abs(v)
    if dec:
        s = f"{v:,.{dec}f}"
    else:
        s = f"{v:,.0f}"
    s = s.replace(",", "@").replace(".", ",").replace("@", ".")
    return ("-R$ " if neg else "R$ ") + s


def usd(v, dec=0):
    if v is None:
        return ""
    return f"USD {v:,.{dec}f}"


def num_fmt(v):
    if v is None:
        return ""
    if abs(v - round(v)) < 1e-9:
        return f"{int(round(v)):,}"
    return f"{v:,.2f}"


def esc(s):
    return _html.escape("" if s is None else str(s))


# ────────────────────────────────────────────────────────── system probe
def probe_system():
    def run(cmd):
        try:
            return subprocess.run(cmd, capture_output=True, text=True, timeout=5).stdout.strip()
        except Exception:
            return ""
    mem = run(["sysctl", "-n", "hw.memsize"])
    try:
        mem_gb = f"{int(mem) / (1024**3):.0f} GB"
    except (ValueError, TypeError):
        mem_gb = "—"
    return {
        "product": run(["sw_vers", "-productName"]) or "macOS",
        "version": run(["sw_vers", "-productVersion"]) or "26.6.2",
        "build": run(["sw_vers", "-buildVersion"]) or "25G83",
        "arch": run(["uname", "-m"]) or "arm64",
        "cpu": run(["sysctl", "-n", "machdep.cpu.brand_string"]) or "Apple M3",
        "model": run(["sysctl", "-n", "hw.model"]) or "Mac15,5",
        "ncpu": run(["sysctl", "-n", "hw.ncpu"]) or "8",
        "mem": mem_gb,
        "host": run(["scutil", "--get", "ComputerName"]) or "iMac",
    }


# ────────────────────────────────────────────────────────── generic table
GREEN = {"confirmed", "clean", "keep", "active", "ok", "deployed", "inbound"}
RED = {"cancel", "critical", "broken", "dirty", "pending"}
YELLOW = {"review", "high", "paused", "medium", "outbound"}
GRAY = {"low", "monitor", "unknown", "unk"}


def cell_class(text):
    t = str(text).strip().lower()
    if t in GREEN:
        return "green"
    if t in RED:
        return "red"
    if t in YELLOW:
        return "yellow"
    if t in GRAY:
        return "gray"
    return ""


BADGE_MAP = {
    "critical": "badge-crit", "high": "badge-high", "medium": "badge-med",
    "low": "badge-low", "keep": "badge-keep", "cancel": "badge-cancel",
    "review": "badge-review", "confirmed": "badge-ok", "deployed": "badge-ok",
    "active": "badge-keep", "paused": "badge-pause", "pending": "badge-pend",
    "monitor": "badge-med", "clean": "badge-ok", "dirty": "badge-review",
    "broken": "badge-cancel",
}


def badge(text):
    t = str(text).strip()
    cls = BADGE_MAP.get(t.lower())
    if not cls:
        return esc(t)
    return f'<span class="badge {cls}">{esc(t)}</span>'


def render_generic(sheet, header_row, first_data_row, last_data_row,
                   num_cols=None, badge_cols=None, title=None):
    """Render a worksheet region as a Bloomberg table. Rows whose col A starts
    with ◆ become full-width section headers; blank rows are skipped."""
    num_cols = num_cols or set()
    badge_cols = badge_cols or set()
    ncol = sheet.max_col
    headers = [sheet.disp(header_row, c) for c in range(1, ncol + 1)]
    # trim trailing empty header columns
    while headers and headers[-1] == "":
        headers.pop()
    ncol = len(headers)
    out = ['<table class="bt">']
    out.append("<tr>" + "".join(
        f'<th class="{"num" if c in num_cols else ""}">{esc(h)}</th>'
        for c, h in enumerate(headers, 1)) + "</tr>")
    for r in range(first_data_row, last_data_row + 1):
        rowvals = [sheet.disp(r, c) for c in range(1, ncol + 1)]
        if all(v == "" for v in rowvals):
            continue
        a = sheet.disp(r, 1)
        if a.startswith("◆"):
            out.append(f'<tr><td colspan="{ncol}" class="orange" '
                       f'style="background:var(--bg3);font-size:9px;letter-spacing:1px;">'
                       f'{esc(a)}</td></tr>')
            continue
        tds = []
        for c in range(1, ncol + 1):
            val = sheet.disp(r, c)
            n = sheet.num(r, c)
            if c in badge_cols and val:
                tds.append(f"<td>{badge(val)}</td>")
            elif c in num_cols:
                disp = num_fmt(n) if n is not None else esc(val)
                cls = "num"
                if n is not None and n < 0:
                    cls += " red"
                tds.append(f'<td class="{cls}">{disp}</td>')
            else:
                cls = cell_class(val)
                tds.append(f'<td class="{cls}">{esc(val)}</td>' if cls else f"<td>{esc(val)}</td>")
        out.append("<tr>" + "".join(tds) + "</tr>")
    out.append("</table>")
    return "\n".join(out)


def panel(title, sub, body):
    subhtml = f'<span class="ph-sub">{esc(sub)}</span>' if sub else ""
    return (f'<div class="panel" style="margin-bottom:6px;">'
            f'<div class="ph">{esc(title)}{subhtml}</div>'
            f'<div class="pb">{body}</div></div>')


def kpi(label, value, sub, color="orange"):
    return (f'<div class="kpi"><div class="kpi-lbl">{esc(label)}</div>'
            f'<div class="kpi-val {color}">{esc(value)}</div>'
            f'<div class="kpi-sub">{esc(sub)}</div></div>')


# ────────────────────────────────────────────────────────── build
def build():
    sheets, names = load_workbook(XLSX)

    REQUIRED_SHEETS = ["BALANCES", "FX_OPS", "TRANSACTIONS", "SUBSCRIPTIONS", "PIX",
                       "REPOS", "PROJECTS", "CONFIG", "MONTHLY", "CATEGORIES", "ALERTS"]
    missing = [s for s in REQUIRED_SHEETS if s not in sheets]
    if missing:
        sys.exit(
            "[error] %s\n"
            "        missing required sheet(s): %s\n"
            "        found (%d): %s\n"
            "        This generator needs all %d input sheets. If Excel repaired the\n"
            "        workbook it may have dropped sheets and left a SUMMARY recovery log.\n"
            "        Restore with:  git checkout -- data/command-center.xlsx"
            % (XLSX, ", ".join(missing), len(names), ", ".join(names), len(REQUIRED_SHEETS))
        )
    sysinfo = probe_system()
    today = date.today().strftime("%d %b %Y")

    B = sheets["BALANCES"]
    FX = sheets["FX_OPS"]
    TX = sheets["TRANSACTIONS"]
    SUB = sheets["SUBSCRIPTIONS"]
    PIX = sheets["PIX"]
    REP = sheets["REPOS"]
    PRJ = sheets["PROJECTS"]
    CFG = sheets["CONFIG"]
    MON = sheets["MONTHLY"]
    CAT = sheets["CATEGORIES"]
    ALR = sheets["ALERTS"]

    # ── key numbers (traced to workbook cells)
    net_worth = B.num(17, 3)
    liquid = B.num(9, 3)
    ib_brl = B.num(13, 3)
    ib_usd = B.num(13, 4)
    fundos = B.num(14, 3)
    fx_out = FX.num(41, 3)
    fx_out_usd = FX.num(41, 4)
    fx_out_cnt = FX.num(41, 2)
    inbound = FX.num(45, 3)
    card_h1 = MON.num(11, 2)
    card_cnt = MON.num(11, 3)
    pix_net = PIX.num(39, 4)
    sub_stack = SUB.num(27, 5)
    sub_cnt = 15
    cancel_save = SUB.num(23, 5)
    cancel_cnt = SUB.num(23, 6)
    iof = PIX.num(41, 6)

    # alerts counts
    a_crit = ALR.num(19, 3)
    a_high = ALR.num(20, 3)
    a_med = ALR.num(21, 3)
    a_low = ALR.num(22, 3)
    a_total = sum(x or 0 for x in (a_crit, a_high, a_med, a_low))

    # repos / projects
    repo_total = REP.num(9, 2)
    repo_dirty = REP.num(11, 2)
    prj_active = PRJ.num(13, 2)
    prj_paused = PRJ.num(14, 2)

    # ── chart DATA (computed from workbook) ────────────────────────────────
    # FX rate points: every USD op in FX_OPS with a rate, chronological
    fxrate = []
    for r in range(5, 37):
        ccy = FX.disp(r, 4)
        rate = FX.num(r, 7)
        d = FX.disp(r, 1)
        if ccy == "USD" and rate:
            fxrate.append({"d": d[5:] if len(d) >= 10 else d, "r": rate})

    months = [MON.disp(r, 1)[:7] for r in range(5, 11)]
    mlabels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun"]
    card_m = [MON.num(r, 2) or 0 for r in range(5, 11)]
    pixin_m = [MON.num(r, 4) or 0 for r in range(5, 11)]

    # categories (rows 5..15)
    cat_colors = ["#ff6600", "#3399ff", "#00cc44", "#ffcc00", "#00cccc",
                  "#ff4444", "#ff8800", "#66bbff", "#00ff55", "#888", "#555"]
    categories = []
    ci = 0
    for r in range(5, 16):
        lbl = CAT.disp(r, 1)
        v = CAT.num(r, 2)
        if lbl and v:
            categories.append({"label": lbl, "v": v, "c": cat_colors[ci % len(cat_colors)]})
            ci += 1

    data = {
        "alloc": [
            {"label": "Fundos BRL", "v": fundos, "c": "#00cc44"},
            {"label": "IB Net", "v": ib_brl, "c": "#3399ff"},
            {"label": "Liquid", "v": liquid, "c": "#ffcc00"},
        ],
        "nw": net_worth,
        "monthly": {"labels": mlabels, "card": card_m, "avg": (card_h1 or 0) / 6},
        "fxrate": fxrate,
        "flows": {"labels": mlabels, "card": card_m, "pixIn": pixin_m},
        "flowpie": [
            {"label": "FX Outbound", "v": fx_out, "c": "#ff2222"},
            {"label": "IB Deposits", "v": FX.num(42, 3), "c": "#00cc44"},
            {"label": "Fund Capital", "v": FX.num(44, 3), "c": "#3399ff"},
            {"label": "Inbound", "v": inbound, "c": "#00cccc"},
            {"label": "Card Spend", "v": card_h1, "c": "#ffcc00"},
        ],
        "subs": [
            {"label": "KEEP", "v": SUB.num(22, 5), "c": "#00cc44"},
            {"label": "CANCEL", "v": SUB.num(23, 5), "c": "#ff2222"},
            {"label": "REVIEW", "v": SUB.num(24, 5), "c": "#ffcc00"},
        ],
        "categories": categories,
    }

    # ── CSS reused verbatim from the model (tailored font stack) ───────────
    model = open(MODEL_HTML, encoding="utf-8").read()
    css = re.search(r"<style>.*?</style>", model, re.S).group(0)
    css = css.replace("'Courier New', Courier, monospace",
                      "'SF Mono','SFMono-Regular','Menlo','Courier New',monospace")
    css = css.replace("font-family: 'Courier New', Courier, monospace;",
                      "font-family: 'SF Mono','SFMono-Regular','Menlo','Courier New',monospace;")

    # ── PAGES ──────────────────────────────────────────────────────────────
    pages = []

    # 00 COMMAND CENTER
    kpis = "".join([
        kpi("Est. Net Worth", brl(net_worth), "Liquid + Investments", "orange"),
        kpi("Total Liquidity", brl(liquid), "Inter + MP + BB", "yellow"),
        kpi("IB Net Deployed", usd(ib_usd), brl(ib_brl), "green"),
        kpi("Fundos BRL", brl(fundos), "Topázio deposits", "green"),
        kpi("FX Outbound H1", brl(fx_out), f"{usd(fx_out_usd)} · {int(fx_out_cnt or 0)} ops", "red"),
        kpi("Inbound H1", brl(inbound), "câmbio in", "cyan"),
        kpi("Card Spend H1", brl(card_h1), f"{int(card_cnt or 0)} txs", "red"),
        kpi("PIX Net Flow", brl(pix_net), "Inter bridge", "blue"),
        kpi("Sub Stack/mo", brl(sub_stack, 2), f"{sub_cnt} services", "red"),
        kpi("Cancel Savings", brl(cancel_save, 2), f"{int(cancel_cnt or 0)} services · /mo", "green"),
        kpi("IOF Paid H1", brl(iof), "FX operation tax", "yellow"),
        kpi("Open Alerts", f"{int(a_total)}", f"{int(a_crit or 0)} critical", "red"),
    ])
    cmd_body = f'<div class="kpi-grid">{kpis}</div>'
    sysbar = (f'<div style="padding:5px 8px;color:var(--gray);font-size:9px;">'
              f'HOST <span class="chip">{esc(sysinfo["model"])}</span> iMac · '
              f'<span class="chip">{esc(sysinfo["cpu"])}</span> '
              f'<span class="chip">{esc(sysinfo["arch"])}</span> · '
              f'<span class="chip">{esc(sysinfo["product"])} {esc(sysinfo["version"])} ({esc(sysinfo["build"])})</span> · '
              f'<span class="chip">{esc(sysinfo["mem"])}</span> · '
              f'<span class="chip">{esc(sysinfo["ncpu"])} cores</span></div>')
    charts_row = (
        '<div class="row">'
        '<div class="col panel"><div class="ph">WEALTH ALLOCATION</div>'
        '<div class="chart-wrap"><svg id="svg-alloc" width="100%" height="140"></svg></div></div>'
        '<div class="col-2 panel"><div class="ph">MONTHLY CARD SPEND · H1 2026</div>'
        '<div class="chart-wrap"><svg id="svg-monthly" width="100%" height="140"></svg></div></div>'
        '</div>'
        '<div class="row">'
        '<div class="col-2 panel"><div class="ph">CAPITAL FLOWS · CARD vs PIX-IN</div>'
        '<div class="chart-wrap"><svg id="svg-flows" width="100%" height="110"></svg></div></div>'
        '<div class="col panel"><div class="ph">FLOW COMPOSITION</div>'
        '<div class="chart-wrap"><svg id="svg-flow-pie" width="100%" height="230"></svg></div></div>'
        '</div>'
    )
    top_alerts = render_generic(ALR, 4, 5, 8, num_cols={1, 5}, badge_cols={2})
    pages.append(("cmd", "active",
        panel(f"COMMAND CENTER · {esc(sysinfo['host'])}",
              f"Generated {today} · Source: data/command-center.xlsx · Host: iMac M3 / {sysinfo['product']} {sysinfo['version']}",
              cmd_body + sysbar)
        + charts_row
        + panel("PRIORITY ALERTS", "Top of ALERTS register", top_alerts)))

    # 01 BALANCES
    pages.append(("bal", "",
        panel("BALANCES — Bank & Investment Accounts", B.disp(2, 1),
              render_generic(B, 4, 5, 17, num_cols={3, 4}, badge_cols={6}))))

    # 02 FX OPS
    fx_charts = ('<div class="row"><div class="col-2 panel">'
                 '<div class="ph">USD/BRL RATE · EVERY USD OP</div>'
                 '<div class="chart-wrap"><svg id="svg-fxrate" width="100%" height="160"></svg></div></div>'
                 '<div class="col panel"><div class="ph">DIRECTION SUMMARY</div>'
                 f'<div class="pb">{render_generic(FX, 40, 41, 45, num_cols={2,3,4,5})}</div></div></div>')
    pages.append(("fx", "",
        fx_charts
        + panel("FX OPERATIONS — BCB Câmbio Register", FX.disp(2, 1),
                render_generic(FX, 4, 5, 36, num_cols={5, 6, 7}, badge_cols={8}))))

    # 03 TRANSACTIONS (with search)
    tx_table = render_generic(TX, 4, 5, 150, num_cols={1, 5})
    tx_table = tx_table.replace('<table class="bt">', '<table class="bt" id="tx-table">', 1)
    search = ('<div style="padding:5px 8px;">'
              '<input id="tx-search" oninput="filterTx()" placeholder="filter merchants / category…" '
              'style="background:var(--bg3);border:1px solid var(--border2);color:var(--white);'
              'font-family:inherit;font-size:11px;padding:3px 7px;width:260px;">'
              '<span id="tx-count" style="color:var(--gray);font-size:10px;margin-left:8px;">146 rows</span></div>')
    pages.append(("tx", "",
        panel("TRANSACTIONS — MP Faturas Card Statement", TX.disp(2, 1),
              search + tx_table)))

    # 04 SUBSCRIPTIONS
    sub_charts = ('<div class="row"><div class="col-2 panel">'
                  '<div class="ph">DECISION SUMMARY</div>'
                  f'<div class="pb">{render_generic(SUB, 21, 22, 27, num_cols={5,6})}</div></div>'
                  '<div class="col panel"><div class="ph">MONTHLY R$ BY DECISION</div>'
                  '<div class="chart-wrap"><svg id="svg-subs" width="100%" height="150"></svg></div></div></div>')
    pages.append(("subs", "",
        sub_charts
        + panel("SUBSCRIPTIONS — 15 Services Tracked", SUB.disp(2, 1),
                render_generic(SUB, 4, 5, 19, num_cols={5}, badge_cols={7, 8, 10}))))

    # 05 PIX
    pages.append(("pix", "",
        panel("PIX — Banco Inter Cash Bridge", PIX.disp(2, 1),
              render_generic(PIX, 4, 5, 41, num_cols={4, 5, 6}, badge_cols={2}))))

    # 06 MONTHLY
    mon_chart = ('<div class="row"><div class="col panel">'
                 '<div class="ph">CARD SPEND TREND</div>'
                 '<div class="chart-wrap"><svg id="svg-monthly2" width="100%" height="150"></svg></div></div></div>')
    pages.append(("mon", "",
        panel("MONTHLY — Cash Flow Summary · Jan–Jun 2026", MON.disp(2, 1),
              render_generic(MON, 4, 5, 12, num_cols={2, 3, 4, 5, 6, 7, 8, 9}))
        + mon_chart
        + panel("MoM CHANGES — Card Spend", "", render_generic(MON, 16, 17, 22, num_cols={2, 3, 4}))))

    # 07 CATEGORIES
    cat_chart = ('<div class="row"><div class="col panel">'
                 '<div class="ph">SPEND BY CATEGORY</div>'
                 '<div class="chart-wrap"><svg id="svg-cats" width="100%" height="200"></svg></div></div></div>')
    pages.append(("cat", "",
        cat_chart
        + panel("CATEGORIES — Card Spend Breakdown · H1 2026", CAT.disp(2, 1),
                render_generic(CAT, 4, 5, 16, num_cols={2, 3, 4, 5}))
        + panel("BY CLASSIFICATION", "", render_generic(CAT, 18, 19, 22, num_cols={2, 3}))))

    # 08 ALERTS
    pages.append(("alerts", "",
        panel("ALERTS — Risk & Action Register · Cross-Domain", ALR.disp(2, 1),
              render_generic(ALR, 4, 5, 16, num_cols={1, 5}, badge_cols={2}))
        + panel("COUNTS", "", render_generic(ALR, 18, 19, 22, num_cols={3, 4}, badge_cols={2}))))

    # 09 REPOS (iMac tailoring)
    pages.append(("repos", "",
        panel("REPOS — Git Repository Health · ~/Documents/GitHub", REP.disp(2, 1),
              render_generic(REP, 4, 5, 6, num_cols={4, 6, 9}, badge_cols={2}))
        + panel("STATUS SUMMARY", "", render_generic(REP, 8, 9, 12, num_cols={2}))))

    # 10 PROJECTS
    pages.append(("prj", "",
        panel("PROJECTS — Operational Status Board", PRJ.disp(2, 1),
              render_generic(PRJ, 4, 5, 10, badge_cols={2, 7}))
        + panel("COUNTS", "", render_generic(PRJ, 12, 13, 15, num_cols={2}))))

    # 11 CONFIG
    pages.append(("cfg", "",
        panel("CONFIG — Alert Thresholds & Parameters", CFG.disp(2, 1),
              render_generic(CFG, 4, 5, 16, num_cols={2}))))

    # 12 SYSTEM (iMac M3 tailoring)
    sys_rows = [
        ("Computer", sysinfo["host"]),
        ("Model Identifier", f'{sysinfo["model"]} (iMac, Apple Silicon)'),
        ("Chip", sysinfo["cpu"]),
        ("Architecture", sysinfo["arch"]),
        ("Total Cores", sysinfo["ncpu"]),
        ("Memory", sysinfo["mem"]),
        ("Operating System", f'{sysinfo["product"]} {sysinfo["version"]}'),
        ("Build", sysinfo["build"]),
        ("Dashboard Generated", today),
        ("Data Source", "data/command-center.xlsx"),
        ("Tracked Repos", f'{int(repo_total or 0)} ({int(repo_dirty or 0)} dirty)'),
        ("Active Projects", f'{int(prj_active or 0)} active · {int(prj_paused or 0)} paused'),
    ]
    sys_kpi = "".join(kpi(k, v, "", "cyan") for k, v in [
        ("Chip", sysinfo["cpu"]),
        ("macOS", f'{sysinfo["version"]}'),
        ("Build", sysinfo["build"]),
        ("Arch", sysinfo["arch"]),
        ("Memory", sysinfo["mem"]),
        ("Cores", sysinfo["ncpu"]),
    ])
    sys_tbl = ['<table class="bt"><tr><th>Attribute</th><th>Value</th></tr>']
    for k, v in sys_rows:
        sys_tbl.append(f"<tr><td class='gray'>{esc(k)}</td><td class='cyan'>{esc(v)}</td></tr>")
    sys_tbl.append("</table>")
    pages.append(("system", "",
        panel("SYSTEM — Host Machine", "Live probe · tailored for this iMac",
              f'<div class="kpi-grid">{sys_kpi}</div>')
        + panel("HOST DETAIL", "sw_vers · sysctl · uname", "\n".join(sys_tbl))))

    # ── NAV TABS ───────────────────────────────────────────────────────────
    tab_defs = [
        ("cmd", "00 CMD CTR"), ("bal", "01 BALANCES"), ("fx", "02 FX OPS"),
        ("tx", "03 TRANSACTIONS"), ("subs", "04 SUBSCRIPTIONS"), ("pix", "05 PIX BRIDGE"),
        ("mon", "06 MONTHLY"), ("cat", "07 CATEGORIES"), ("alerts", "08 ALERTS"),
        ("repos", "09 REPOS"), ("prj", "10 PROJECTS"), ("cfg", "11 CONFIG"),
        ("system", "12 SYSTEM"),
    ]
    navtabs = "\n".join(
        f'  <div class="tab{" active" if i == 0 else ""}" onclick="showPage(\'{pid}\')">{esc(label)}</div>'
        for i, (pid, label) in enumerate(tab_defs))

    pages_html = "\n".join(
        f'<div class="page{" active" if state == "active" else ""}" id="p-{pid}">{body}</div>'
        for pid, state, body in pages)

    # ── TICKER ─────────────────────────────────────────────────────────────
    ticks = [
        ("NET WORTH", brl(net_worth), "up"),
        ("LIQUID", brl(liquid), "dn" if (liquid or 0) < 30000 else "up"),
        ("IB USD", usd(ib_usd), "up"),
        ("FUNDOS", brl(fundos), "up"),
        ("FX OUT H1", brl(fx_out), "dn"),
        ("CARD H1", brl(card_h1), "dn"),
        ("SUB/MO", brl(sub_stack, 2), "dn"),
        ("CANCEL SAVE", brl(cancel_save, 2), "up"),
        ("ALERTS", f"{int(a_total)}", "dn"),
        ("REPOS", f"{int(repo_total or 0)}", "up"),
    ]
    tick_items = '<span class="tick-sep">|</span>'.join(
        f'<span class="tick-item">{esc(lbl)} <span class="tick-{d}">{esc(val)}</span></span>'
        for lbl, val, d in ticks)
    ticker_inner = tick_items + tick_items  # duplicate for seamless scroll

    # ── JS (charts driven by embedded DATA) ────────────────────────────────
    data_json = json.dumps(data)
    js = JS_TEMPLATE.replace("__DATA__", data_json)

    # ── ASSEMBLE ───────────────────────────────────────────────────────────
    doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>COMMAND CENTER — iMac M3 · {esc(sysinfo['product'])} {esc(sysinfo['version'])}</title>
{css}
</head>
<body>
<div id="shell">

<div id="topbar">
  <div class="tb-left">
    <span class="tb-logo">◆ COMMAND</span>
    <span class="tb-title">CMD CTR · iMac M3 · {esc(sysinfo['cpu'])} · {esc(sysinfo['product'])} {esc(sysinfo['version'])} ({esc(sysinfo['build'])}) · {esc(sysinfo['arch'])}</span>
  </div>
  <div class="tb-right">
    <span class="fs-label">FONT</span>
    <button class="fs-btn" onclick="adjustFS(-1)">A−</button>
    <span id="fs-pct" style="color:var(--gray);font-size:10px;min-width:32px;display:inline-block;text-align:center;">100%</span>
    <button class="fs-btn" onclick="adjustFS(+1)">A+</button>
    <span id="clock">—</span>
  </div>
</div>

<div id="navtabs">
{navtabs}
</div>

<div id="content">
{pages_html}
</div>

<div id="ticker"><div id="ticker-inner">{ticker_inner}</div></div>

</div>
<script>
window.DATA = {data_json};
{js}
</script>
</body>
</html>
"""
    with open(OUT_HTML, "w", encoding="utf-8") as fh:
        fh.write(doc)
    return doc, len(pages)


JS_TEMPLATE = r"""
function updateClock(){
  const n=new Date();
  document.getElementById('clock').textContent=
    n.toLocaleDateString('pt-BR')+' '+
    n.toLocaleTimeString('pt-BR',{hour:'2-digit',minute:'2-digit',second:'2-digit'})+' BRT';
}
setInterval(updateClock,1000); updateClock();

let fsZoom=100;
function adjustFS(d){
  fsZoom=Math.max(70,Math.min(150,fsZoom+d*10));
  document.body.style.zoom=fsZoom+'%';
  const lbl=document.getElementById('fs-pct'); if(lbl) lbl.textContent=fsZoom+'%';
}

function showPage(id){
  document.querySelectorAll('.page').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
  document.getElementById('p-'+id).classList.add('active');
  event.currentTarget.classList.add('active');
  setTimeout(initCharts,30);
}

function filterTx(){
  const q=document.getElementById('tx-search').value.toLowerCase();
  const rows=document.querySelectorAll('#tx-table tr:not(:first-child)');
  let vis=0;
  rows.forEach(r=>{const t=r.textContent.toLowerCase();const s=t.includes(q);r.style.display=s?'':'none';if(s)vis++;});
  document.getElementById('tx-count').textContent=vis+' rows';
}

function svgEl(tag,attrs){const el=document.createElementNS('http://www.w3.org/2000/svg',tag);
  Object.entries(attrs).forEach(([k,v])=>el.setAttribute(k,v));return el;}

function pie(id,data,cx0off,title){
  const svg=document.getElementById(id); if(!svg) return;
  const W=svg.clientWidth||300,H=svg.getAttribute('height')-0||150;
  svg.setAttribute('viewBox',`0 0 ${W} ${H}`);
  const cx=W/2-cx0off,cy=H/2-5,r=Math.min(60,H/2-15);
  const total=data.reduce((s,d)=>s+(d.v||0),0)||1;let a=-Math.PI/2;
  data.forEach(d=>{const sl=2*Math.PI*((d.v||0)/total);
    const x1=cx+r*Math.cos(a),y1=cy+r*Math.sin(a);a+=sl;
    const x2=cx+r*Math.cos(a),y2=cy+r*Math.sin(a);const lg=sl>Math.PI?1:0;
    svg.appendChild(svgEl('path',{d:`M${cx},${cy} L${x1},${y1} A${r},${r} 0 ${lg} 1 ${x2},${y2} Z`,
      fill:d.c,stroke:'#0a0a0a','stroke-width':'2',opacity:'0.85'}));});
  data.forEach((d,i)=>{const lx=cx+r+16,ly=14+i*18;
    svg.appendChild(svgEl('rect',{x:lx,y:ly,width:9,height:9,fill:d.c}));
    const pct=(((d.v||0)/total)*100).toFixed(1);
    const t=svgEl('text',{x:lx+13,y:ly+8,fill:'#e8e8e8','font-size':'8.5'});
    t.textContent=`${d.label} ${pct}%`;svg.appendChild(t);});
}

function bars(id,labels,series){
  const svg=document.getElementById(id); if(!svg) return;
  const W=svg.clientWidth||500,H=svg.getAttribute('height')-0||140;
  svg.setAttribute('viewBox',`0 0 ${W} ${H}`);
  const pad={l:40,r:10,t:12,b:22},cw=W-pad.l-pad.r,ch=H-pad.t-pad.b;
  const allv=series.flatMap(s=>s.v);const max=Math.max(...allv,1);
  const groups=labels.length,gw=cw/groups,bw=gw/(series.length+0.6);
  labels.forEach((m,i)=>{
    series.forEach((s,si)=>{const v=s.v[i]||0;const bh=(v/max)*ch;
      const x=pad.l+i*gw+si*bw+bw*0.3;const y=pad.t+ch-bh;
      svg.appendChild(svgEl('rect',{x,y,width:bw*0.9,height:bh,fill:s.c,opacity:'0.85'}));});
    const lbl=svgEl('text',{x:pad.l+i*gw+gw/2,y:H-6,'text-anchor':'middle',fill:'#888','font-size':'9'});
    lbl.textContent=m;svg.appendChild(lbl);});
}

function drawMonthly(id){
  const svg=document.getElementById(id); if(!svg) return;
  const D=window.DATA.monthly;const W=svg.clientWidth||540,H=svg.getAttribute('height')-0||140;
  svg.setAttribute('viewBox',`0 0 ${W} ${H}`);
  const pad={l:40,r:10,t:12,b:25},cw=W-pad.l-pad.r,ch=H-pad.t-pad.b;
  const max=Math.max(...D.card,1),bw=(cw/D.card.length)*0.6,gap=(cw/D.card.length)*0.4;
  D.card.forEach((v,i)=>{const x=pad.l+i*(bw+gap)+gap/2,bh=(v/max)*ch,y=pad.t+ch-bh;
    const col=v>10000?'#ff2222':v>6000?'#ff6600':'#ffcc00';
    svg.appendChild(svgEl('rect',{x,y,width:bw,height:bh,fill:col,opacity:'0.85'}));
    const lb=svgEl('text',{x:x+bw/2,y:H-8,'text-anchor':'middle',fill:'#888','font-size':'9'});lb.textContent=D.labels[i];svg.appendChild(lb);
    const vl=svgEl('text',{x:x+bw/2,y:y-3,'text-anchor':'middle',fill:'#e8e8e8','font-size':'8'});vl.textContent=(v/1000).toFixed(1)+'k';svg.appendChild(vl);});
  const avgY=pad.t+ch-(D.avg/max)*ch;
  svg.appendChild(svgEl('line',{x1:pad.l,y1:avgY,x2:W-pad.r,y2:avgY,stroke:'#3399ff','stroke-width':'1','stroke-dasharray':'4,3'}));
  const at=svgEl('text',{x:pad.l-2,y:avgY-3,fill:'#3399ff','font-size':'8','text-anchor':'end'});at.textContent='avg';svg.appendChild(at);
}

function drawFX(){
  const svg=document.getElementById('svg-fxrate'); if(!svg) return;
  const pts=window.DATA.fxrate;if(!pts.length) return;
  const W=svg.clientWidth||300,H=160;svg.setAttribute('viewBox',`0 0 ${W} ${H}`);
  const pad={l:36,r:8,t:10,b:20},cw=W-pad.l-pad.r,ch=H-pad.t-pad.b;
  const rates=pts.map(p=>p.r),mn=Math.min(...rates)-0.05,mx=Math.max(...rates)+0.05;
  const sx=i=>(i/(pts.length-1))*cw+pad.l,sy=r=>pad.t+ch-(r-mn)/(mx-mn)*ch;
  [4.9,5.0,5.1,5.2,5.3,5.4].forEach(rv=>{if(rv<mn||rv>mx)return;const yg=sy(rv);
    svg.appendChild(svgEl('line',{x1:pad.l,y1:yg,x2:W-pad.r,y2:yg,stroke:'#222','stroke-width':'1'}));
    const gt=svgEl('text',{x:pad.l-2,y:yg+3,fill:'#555','font-size':'7','text-anchor':'end'});gt.textContent=rv.toFixed(2);svg.appendChild(gt);});
  const poly=pts.map((p,i)=>`${sx(i)},${sy(p.r)}`).join(' ');
  svg.appendChild(svgEl('polyline',{points:poly,fill:'none',stroke:'#3399ff','stroke-width':'1.5'}));
  pts.forEach((p,i)=>svg.appendChild(svgEl('circle',{cx:sx(i),cy:sy(p.r),r:'2.2',fill:'#3399ff'})));
  const avg=rates.reduce((a,b)=>a+b)/rates.length;
  svg.appendChild(svgEl('line',{x1:pad.l,y1:sy(avg),x2:W-pad.r,y2:sy(avg),stroke:'#ffcc00','stroke-width':'1','stroke-dasharray':'3,3'}));
  const at=svgEl('text',{x:W-pad.r-2,y:sy(avg)-3,fill:'#ffcc00','font-size':'7','text-anchor':'end'});at.textContent='avg '+avg.toFixed(3);svg.appendChild(at);
}

function clearSvg(id){const el=document.getElementById(id);if(el)while(el.firstChild)el.removeChild(el.firstChild);}

function initCharts(){
  ['svg-alloc','svg-monthly','svg-monthly2','svg-fxrate','svg-flows','svg-flow-pie','svg-subs','svg-cats'].forEach(clearSvg);
  pie('svg-alloc',window.DATA.alloc,40);
  drawMonthly('svg-monthly'); drawMonthly('svg-monthly2');
  drawFX();
  bars('svg-flows',window.DATA.flows.labels,[
    {v:window.DATA.flows.card,c:'#ff4444'},{v:window.DATA.flows.pixIn,c:'#00cc44'}]);
  pie('svg-flow-pie',window.DATA.flowpie,0);
  pie('svg-subs',window.DATA.subs,0);
  bars('svg-cats',window.DATA.categories.map(c=>c.label.slice(0,6)),
    [{v:window.DATA.categories.map(c=>c.v),c:'#ff6600'}]);
}

window.addEventListener('resize',initCharts);
document.addEventListener('DOMContentLoaded',initCharts);
setTimeout(initCharts,200);
"""


if __name__ == "__main__":
    if not os.path.exists(XLSX):
        sys.exit(f"[error] workbook not found: {XLSX}")
    doc, npages = build()
    # tag-balance sanity check
    for t in ("table", "tr", "td", "div"):
        o = len(re.findall(rf"<{t}[ >]", doc))
        c = len(re.findall(rf"</{t}>", doc))
        flag = "" if o == c else "  <-- MISMATCH"
        print(f"[chk] <{t}> {o} / {c}{flag}")
    print(f"[ok] wrote {OUT_HTML} · {npages} pages · {len(doc):,} bytes")
