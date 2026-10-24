#!/bin/zsh
# Restore Spencer "FINANCE WORKSPACE" layout: regen dashboards, open documents, position windows.
set -euo pipefail

SCRIPT_DIR="${0:A:h}"
# shellcheck source=lib/personal-finance-layout.env
source "${SCRIPT_DIR}/lib/personal-finance-layout.env"
# shellcheck source=lib/spencer-common.zsh
source "${SCRIPT_DIR}/lib/spencer-common.zsh"

log() { print -u2 -- "$*"; }

open_cursor_workspace() {
  if command -v cursor >/dev/null 2>&1; then
    cursor "$CURSOR_WS"
  else
    open -a Cursor "$CURSOR_WS"
  fi
}

open_obsidian_graph() {
  if [[ ! -d "$OBSIDIAN_VAULT" ]]; then
    log "error: Obsidian vault not found at $OBSIDIAN_VAULT"
    return 1
  fi

  open -a Obsidian "$OBSIDIAN_VAULT"
  sleep 2
  open "obsidian://graph?vault=${OBSIDIAN_VAULT_NAME}"
}

regenerate_dashboards() {
  log "info: regenerating bloomberg-terminal.html..."
  if ! (cd "$REPO_ROOT" && python3 scripts/regenerate_dashboard.py); then
    log "error: regenerate_dashboard.py failed"
    return 2
  fi

  log "info: regenerating command-center.html..."
  if ! (cd "$REPO_ROOT" && python3 scripts/generate_command_center.py); then
    log "error: generate_command_center.py failed"
    return 2
  fi

  return 0
}

open_documents() {
  if [[ ! -f "$EXCEL_DOC" ]]; then
    log "error: Excel workbook missing: $EXCEL_DOC"
    return 3
  fi
  if [[ ! -f "$COMET_DOC" ]]; then
    log "error: command-center.html missing: $COMET_DOC"
    return 3
  fi
  if [[ ! -f "$CURSOR_WS" ]]; then
    log "error: Cursor workspace missing: $CURSOR_WS"
    return 3
  fi

  log "info: opening documents in apps..."
  open -a "Microsoft Excel" "$EXCEL_DOC"
  open -a "Comet" "$COMET_DOC"
  open_cursor_workspace
  open_obsidian_graph
}

main() {
  log "info: Personal Finance workspace restore starting..."

  ensure_spencer_installed || exit 4
  verify_displays || exit 1

  regenerate_dashboards || exit 2

  ensure_spencer_running || exit 4

  if ! spencer_cli --list 2>/dev/null | grep -Fq "$LAYOUT_NAME"; then
    log "error: Spencer layout not found: \"$LAYOUT_NAME\""
    log "hint: create or update it in Spencer → Layout Manager"
    exit 4
  fi

  open_documents || exit 3

  log "info: waiting for app windows..."
  wait_for_windows || exit 3

  log "info: restoring Spencer layout \"$LAYOUT_NAME\"..."
  if ! retry_restore "$LAYOUT_NAME" false; then
    log "error: Spencer restore or window verification failed"
    exit 4
  fi

  log "ok: Personal Finance workspace ready"
  exit 0
}

main "$@"
