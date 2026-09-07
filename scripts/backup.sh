#!/bin/zsh
# Timestamped backup of Personal_Finance — outside iCloud on purpose.
# Usage: zsh scripts/backup.sh
set -euo pipefail

SCRIPT_DIR="${0:A:h}"
PF="${SCRIPT_DIR:h}"
TS="$(date +%Y%m%d-%H%M%S)"
DEST="${HOME}/Backups/Personal_Finance/${TS}"

if [[ ! -d "${PF}/.git" ]]; then
  print -u2 -- "error: not a git repo: ${PF}"
  exit 1
fi

mkdir -p "${DEST}"
print -- "Backing up ${PF}"
print -- "         → ${DEST}"

git -C "${PF}" bundle create "${DEST}/repo.bundle" --all

tar -C "$(dirname "${PF}")" -czf "${DEST}/worktree.tar.gz" "$(basename "${PF}")"

(
  cd "${PF}"
  # Only checksum paths that exist (wealthcommand.xlsx may be data/-only).
  typeset -a files
  files=(
    data/wealthcommand.xlsx
    data/command-center.xlsx
    bloomberg-terminal.html
    command-center.html
    nfce/personal_inflation_data.json
    nfce/personal_inflation_validation.json
    nfce/nfce_all.json
    nfce/inflation_data.json
    nfce/nfce_items.csv
    nfce/nfce_transactions.csv
    nfce/litoral_price_data.json
  )
  : > "${DEST}/MANIFEST.sha256"
  for f in "${files[@]}"; do
    if [[ -f "${f}" ]]; then
      shasum -a 256 "${f}" >> "${DEST}/MANIFEST.sha256"
    else
      print -u2 -- "warn: skip missing ${f}"
    fi
  done
)

print -- "--- verification ---"
git bundle verify "${DEST}/repo.bundle"
print -- "tarball entries: $(tar -tzf "${DEST}/worktree.tar.gz" | wc -l | tr -d ' ')"
(
  cd "${PF}"
  shasum -a 256 -c "${DEST}/MANIFEST.sha256"
)
du -sh "${DEST}"
print -- "ok: backup at ${DEST}"
ln -sfn "${DEST}" "${HOME}/Backups/Personal_Finance/LATEST"
print -- "ok: LATEST → ${DEST}"
