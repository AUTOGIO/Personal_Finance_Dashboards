#!/bin/zsh
# Stream Deck / Finder entry point for the Personal Finance workspace.
# Self-locating: resolves the repo from this script's own path, so it keeps
# working if the repo moves. Do not hard-code an absolute repo path here.
export SD_SKIP_DIALOGS=1
SD_DIR="${0:A:h}"                       # .../scripts/launchers
exec /bin/zsh "${SD_DIR:h}/restore-personal-finance-layout.zsh"
