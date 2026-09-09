#!/usr/bin/env python3
"""Export both dashboards as clean Markdown for NotebookLM (or any LLM tool).

Why this exists: pasting the raw HTML into a notebook tool wastes most of the
context on CSS, chart-drawing JS and tag soup -- roughly 70% of those files --
and the markup competes with the numbers you actually asked about. This walks
each dashboard tab by tab and emits headings, key/value tiles and real Markdown
tables, and nothing else.

Read-only against the dashboards. Writes only into notebooklm/.
Stdlib only, matching the rest of scripts/. Run after `make regen-all`:

    python3 scripts/export_notebooklm.py
"""

import html as _html
import re
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "notebooklm"
SOURCES = [
    ("bloomberg-terminal.html", "bloomberg.md", "Wealth dashboard (bloomberg-terminal)"),
    ("command-center.html", "command-center.md", "Ops dashboard (command-center)"),
]

# Emails appear as legitimate workbook data (the SUBSCRIPTIONS "Account"
# column). They are fine in the repo; they are not fine in a file destined for
# a third-party service, so they are masked here at the export boundary rather
# than edited out of the source of truth.
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def text_of(fragment):
    """Tags out, entities decoded, whitespace collapsed."""
    s = re.sub(r"<[^>]+>", " ", fragment)
    return re.sub(r"\s+", " ", _html.unescape(s)).strip()


def md_table(table_html):
    rows = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", table_html, re.S):
        cells = [text_of(c) for c in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", tr, re.S)]
        if any(c for c in cells):
            rows.append(cells)
    if not rows:
        return ""
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    out = ["| " + " | ".join(rows[0]) + " |", "|" + "---|" * width]
    out += ["| " + " | ".join(r) + " |" for r in rows[1:]]
    return "\n".join(out)


def render_panel(panel):
    parts = []
    ph = re.search(r'<div class="ph"[^>]*>(.*?)</div>', panel, re.S)
    if ph:
        title = text_of(re.sub(r'<span class="ph-sub">.*?</span>', "", ph.group(1), flags=re.S))
        sub = re.search(r'<span class="ph-sub">(.*?)</span>', ph.group(1), re.S)
        heading = f"### {title}"
        if sub:
            heading += f" — _{text_of(sub.group(1))}_"
        parts.append(heading)

    tiles = re.findall(
        r'<div class="kpi-lbl">(.*?)</div>\s*<div class="kpi-val[^"]*">(.*?)</div>', panel, re.S
    )
    if tiles:
        parts.append("\n".join(f"- **{text_of(a)}:** {text_of(b)}" for a, b in tiles))

    for tbl in re.findall(r"<table[^>]*>(.*?)</table>", panel, re.S):
        t = md_table(tbl)
        if t:
            parts.append(t)

    prose = panel
    prose = re.sub(r"<table[^>]*>.*?</table>", " ", prose, flags=re.S)
    prose = re.sub(r'<div class="ph".*?</div>', " ", prose, flags=re.S)
    prose = re.sub(r'<div class="kpi-lbl">.*?</div>', " ", prose, flags=re.S)
    prose = re.sub(r'<div class="kpi-val[^"]*">.*?</div>', " ", prose, flags=re.S)
    prose = text_of(prose)
    if len(prose) > 40:
        parts.append(prose)
    return "\n\n".join(p for p in parts if p)


def convert(html_path, title):
    raw = html_path.read_text(encoding="utf-8")
    raw = re.sub(r"<(style|script)\b.*?</\1>", " ", raw, flags=re.S | re.I)

    labels = dict(
        (m.group(1), text_of(m.group(2)))
        for m in re.finditer(r"showPage\('([^']+)'\)\">(.*?)</div>", raw, re.S)
    )
    body = [f"# {title}", "", f"_Exported {date.today().isoformat()} from `{html_path.name}`._", ""]
    body.append(
        "Generated dashboard, exported as text. Figures trace to the workbook that "
        "owns each dashboard — never edit numbers in the HTML. Email addresses have "
        "been masked for export."
    )
    body.append("")

    # NB: the first tab is <div class="page active"> -- match any page class,
    # or the landing tab (net worth, liquidity, the KPI row) silently vanishes
    # from the export.
    starts = [
        (m.start(), m.group(1))
        for m in re.finditer(r'<div class="page[^"]*"[^>]*id="p-([^"]+)"', raw)
    ]
    for i, (pos, pid) in enumerate(starts):
        end = starts[i + 1][0] if i + 1 < len(starts) else len(raw)
        chunk = raw[pos:end]
        body.append(f"\n## {labels.get(pid, pid.upper())}\n")
        panels = re.split(r'(?=<div class="panel")', chunk)
        rendered = [render_panel(p) for p in panels if 'class="ph"' in p or "<table" in p]
        body.append("\n\n".join(r for r in rendered if r))

    out = "\n".join(body)
    out = EMAIL_RE.sub("[email masked]", out)
    return re.sub(r"\n{4,}", "\n\n\n", out).strip() + "\n"


def main():
    OUT_DIR.mkdir(exist_ok=True)
    failed = False
    for src, dst, title in SOURCES:
        p = REPO_ROOT / src
        if not p.exists():
            print(f"[warn] {src} not found — skipped")
            failed = True
            continue
        md = convert(p, title)
        leaked = EMAIL_RE.findall(md)
        if leaked:
            print(f"[WARNING] {dst}: {len(leaked)} email(s) survived masking — not written")
            failed = True
            continue
        (OUT_DIR / dst).write_text(md, encoding="utf-8")
        before, after = len(p.read_text(encoding="utf-8")), len(md)
        print(
            f"[ok] notebooklm/{dst}: {after:,} bytes from {before:,} "
            f"({after / before * 100:.0f}% of source) · "
            f"{md.count(chr(10) + '## ')} tabs · {md.count('|---')} tables"
        )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
