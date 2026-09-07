# Apple Shortcut: Personal Finance Workspace

Create this shortcut manually in **Shortcuts.app** (the CLI cannot build shortcut graphs).

## Shortcut settings

| Field | Value |
|-------|-------|
| **Name** | `Personal Finance` (or `PF-Workspace`) |
| **Icon** | Optional — pick a finance or layout icon |
| **Run with** | Shortcuts (default) |

## Actions

1. **Run Shell Script**
   - Shell: `/bin/zsh`
   - Input: *(none)*
   - Script:

```zsh
/bin/zsh "/Users/giovannini.eduardogmail.com/Documents/GitHub/Personal_Finance/scripts/launchers/personal-finance-workspace.command"
```

2. *(Optional)* **Show notification** on success — "Personal Finance workspace ready"

## Stream Deck alternative

Point a button at:

```
/Users/giovannini.eduardogmail.com/Documents/GitHub/Personal_Finance/scripts/launchers/personal-finance-workspace.command
```

Or use the same shell script path as above.

## First-run permissions

**Accessibility is required** — window verification enumerates titles through
System Events. Add **Shortcuts** (and your terminal, for `make workspace`) under
**System Settings → Privacy & Security → Accessibility**.

macOS may also prompt for **Automation** access for Spencer, Microsoft Excel,
Comet, Cursor, and Obsidian. Approve these under
**System Settings → Privacy & Security → Automation**.

## Verify

After creating the shortcut:

```zsh
/usr/bin/shortcuts list | grep -F 'Personal Finance'
/usr/bin/shortcuts run "Personal Finance"
```

See [WORKSPACE_LAYOUT.md](../../WORKSPACE_LAYOUT.md) for the full layout reference and troubleshooting.
