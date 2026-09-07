# Stream Deck ↔ Personal Finance shortcuts

## Correct button target

Point Stream Deck / Shortcuts launchers at:

```
/Users/giovannini.eduardogmail.com/Documents/GitHub/Personal_Finance/scripts/launchers/personal-finance-workspace.command
```

That is `scripts/launchers/personal-finance-workspace.command` under this clone:

`~/Documents/GitHub/Personal_Finance`.

## Installed shortcuts (this Mac)

`shortcuts list` includes finance-related entries such as:

- `SD-Open-Finance-Project`
- `SD-Start-Workspace`
- `SD-Backup-Todays-Reports`

### Can we update them via CLI?

**No.** Apple's `shortcuts` CLI only supports `run`, `list`, `view`, and `sign`. There is no create/edit/retarget subcommand. Update targets in **Shortcuts.app** (or re-import a signed shortcut file).

## Retired / broken paths

Installed `SD-*` shortcuts may still point at dead paths under the former home, for example:

- `/Users/eduardofgiovannini/Automation/...`

Treat those as **retired**. Retarget each shortcut in Shortcuts.app to the launcher path above (or to actions that open this repo).

## Recipe

See [Personal-Finance-Workspace.recipe.md](./Personal-Finance-Workspace.recipe.md) for the intended workspace shortcut recipe.
