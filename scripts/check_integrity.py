#!/usr/bin/env python3
"""
check_integrity.py -- fail loudly when a workbook stops looking like itself.

Exists because Excel silently repaired data/command-center.xlsx on 2026-09-01,
dropped three sheets, and nothing noticed for six days. Cheap, no dependencies,
run it before trusting a dashboard.

    python3 scripts/check_integrity.py     (or: make check)
"""
import hashlib
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"

EXPECTED = {
    # 01 NET WORTH / 03 INTERNATIONAL / 04 PORTFOLIO removed on purpose in
    # 474ab36 (2026-09-10 scope cut: domestic outflows only).
    "data/wealthcommand.xlsx": [
        "00 COMMAND CENTER", "CALC", "02 CAPITAL FLOWS", "05 LIFESTYLE",
        "06 SUBSCRIPTION MGR", "07 CASH BRIDGE", "08 ALERTS", "_DATA",
        "09 CHARTS",
    ],
    "data/command-center.xlsx": [
        "BALANCES", "FX_OPS", "TRANSACTIONS", "SUBSCRIPTIONS", "PIX",
        "REPOS", "PROJECTS", "CONFIG", "MONTHLY", "CATEGORIES", "ALERTS",
    ],
}

# Files with no other copy and no way to regenerate them.
IRREPLACEABLE = [
    "nfce/personal_inflation_data.json",
    "nfce/personal_inflation_validation.json",
    "nfce/nfce_all.json",
    "nfce/nfce_items.csv",
    "nfce/nfce_transactions.csv",
]


def sheets_of(path):
    wb = ET.fromstring(zipfile.ZipFile(path).read("xl/workbook.xml"))
    return [s.get("name") for s in wb.iter(NS + "sheet")]


def main():
    problems = []

    for rel, expected in EXPECTED.items():
        p = ROOT / rel
        if not p.exists():
            problems.append("%s is MISSING" % rel)
            continue
        try:
            found = sheets_of(p)
        except Exception as exc:
            problems.append("%s is unreadable (%s)" % (rel, exc))
            continue
        missing = [s for s in expected if s not in found]
        extra = [s for s in found if s not in expected]
        digest = hashlib.sha256(p.read_bytes()).hexdigest()[:12]
        status = "ok" if not missing else "PROBLEM"
        print("[%s] %-28s %2d sheets  sha256:%s" % (status, rel, len(found), digest))
        if missing:
            problems.append("%s missing sheet(s): %s" % (rel, ", ".join(missing)))
        if extra:
            # SUMMARY is what an Excel repair leaves behind.
            note = " (SUMMARY = Excel repair log)" if "SUMMARY" in extra else ""
            problems.append("%s unexpected sheet(s): %s%s" % (rel, ", ".join(extra), note))

    for rel in IRREPLACEABLE:
        p = ROOT / rel
        if p.exists():
            print("[ok] %-28s %d bytes" % (rel, p.stat().st_size))
        else:
            problems.append("%s is MISSING and cannot be regenerated "
                            "(nfce/notas/ holds no source XMLs)" % rel)

    if problems:
        print("\n[FAIL] %d problem(s):" % len(problems))
        for x in problems:
            print("  - %s" % x)
        print("\n  A workbook that lost sheets was probably repaired by Excel.")
        print("  Recover with:  git checkout -- <the workbook named above>")
        return 1

    print("\n[ok] integrity check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
