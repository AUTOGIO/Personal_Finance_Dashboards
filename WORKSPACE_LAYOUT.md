# Personal Finance — Spencer workspace layout

Three-monitor Spencer layout **Personal Finance** for weekly finance work. Reference screenshots: [`screenshots/3displays.png`](screenshots/3displays.png), [`screenshots/29s.png`](screenshots/29s.png), [`screenshots/iMac.png`](screenshots/iMac.png).

## One-liner

From the repo root (prefer `make check` first after workbook edits):

```bash
make check && make workspace
```

This regenerates both dashboards, opens the correct documents, and restores Spencer window positions.

## First-time layout capture

If `spencer --list` does not show **Personal Finance**:

1. Arrange the four apps as in the table below (close extra Comet windows).
2. Run `spencer --create` and name the layout **`Personal Finance`** exactly (that is what `LAYOUT_NAME` expects).
3. Then `make workspace` should exit 0.

## Target layout

| Physical monitor | Spencer display | App | Document |
|------------------|-----------------|-----|----------|
| iMac (left) | 2 | Comet | `command-center.html` |
| LG Ultrawide (center, main) | 1 | Microsoft Excel | `data/command-center.xlsx` |
| LG Ultrawide (right) | 3 | Cursor (left half) | `Personal_Finance.code-workspace` |
| LG Ultrawide (right) | 3 | Obsidian (right half) | `~/Documents/Obsidian` (script opens Graph; any Obsidian title passes verify) |

```text
┌─────────────┬──────────────────────┬──────────────────────┐
│    iMac     │   LG Ultrawide (main)│  LG Ultrawide (right)│
│   Comet     │   Excel (full width) │ Cursor │  Obsidian   │
│ command-    │   command-center.xlsx│  workspace │ graph  │
│ center.html │                      │              │       │
└─────────────┴──────────────────────┴──────────────────────┘
```

## Required display arrangement

In **System Settings → Displays → Arrangement**:

1. **iMac** on the **left**
2. **LG Ultrawide (100 Hz)** in the **center** — set as **main display**
3. **LG Ultrawide (75 Hz)** on the **right**

All three must be online before running `make workspace`. The launcher checks for 3 displays and at least 2 ultrawides at 2560×1080.

Spencer stores stable monitor UUIDs for this arrangement (do not rearrange casually):

- Main ultrawide: `0F24310D-DBD8-4D9A-9643-1B31770934D3`
- iMac: `37D8832A-2D66-02CA-B9F7-8F30A301B230`
- Right ultrawide: `7AFB535E-986C-4147-9A8E-BFD0FC6E47FF`

## One-time prerequisites

**Accessibility permission (required).** Window verification reads titles through
System Events, because Cursor and Obsidian are Electron apps and do not expose
windows via the standard AppleScript suite. Grant your terminal (and Shortcuts,
if you use the shortcut) access under **System Settings → Privacy & Security →
Accessibility**. Without it the script reports
`could not read window titles (grant Accessibility permission)`.

**`openpyxl` (required by the wealth generator).** Installed on this Mac. If a
fresh machine reports `ModuleNotFoundError: No module named 'openpyxl'`:

```bash
pip3 install --break-system-packages openpyxl
```

(On this Mac it is already installed; the flag matches `AI_GUIDE.md` for a fresh machine.)

## Spencer CLI (one-time setup)

Optional symlink so `spencer` works in any terminal:

```bash
sudo mkdir -p /usr/local/bin
sudo ln -sf /Applications/Spencer.app/Contents/MacOS/SpencerCLI /usr/local/bin/spencer
```

The restore script uses the app bundle path directly; the symlink is for manual use.

## Launch options

| Method | Command / path |
|--------|----------------|
| Makefile | `make workspace` |
| Script | `zsh scripts/restore-personal-finance-layout.zsh` |
| Stream Deck | `scripts/launchers/personal-finance-workspace.command` |
| Apple Shortcut | See [`scripts/shortcuts/Personal-Finance-Workspace.recipe.md`](scripts/shortcuts/Personal-Finance-Workspace.recipe.md) |

## Recapture after manual tweaks

If you resize or move windows and want Spencer to remember the new geometry:

1. Arrange all four windows exactly as you want them.
2. Run:

```bash
spencer --update "Personal Finance"
```

(or use Spencer → Layout Manager → update the layout)

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `expected 3 displays, found N` | Plug in all monitors; check Arrangement |
| `Spencer layout not found` | Open Spencer → Layout Manager → confirm **Personal Finance** exists |
| Comet shows wrong page | Script opens `command-center.html`; close extra Comet tabs |
| Excel wrong workbook | Layout expects `data/command-center.xlsx` (not `wealthcommand.xlsx`) |
| Obsidian window not detected | Title check only needs the substring `Obsidian`; Graph is opened via URI but not required as the active tab |
| Window verify timeout | Wait for slow apps, re-run; grant Accessibility permission |
| `could not read window titles` | Grant Accessibility to your terminal (see prerequisites) |
| Generator failure | Fix workbook errors first; script aborts before Spencer restore |

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Display arrangement mismatch |
| 2 | Dashboard generator failed |
| 3 | App/document open or window wait timeout |
| 4 | Spencer install, readiness, or restore failure |

## Files

- [`scripts/restore-personal-finance-layout.zsh`](scripts/restore-personal-finance-layout.zsh) — orchestrator
- [`scripts/lib/personal-finance-layout.env`](scripts/lib/personal-finance-layout.env) — paths and constants
- [`scripts/lib/spencer-common.zsh`](scripts/lib/spencer-common.zsh) — Spencer CLI helpers
