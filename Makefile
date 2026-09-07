.DEFAULT_GOAL := help
PYTHON ?= /usr/bin/python3

.PHONY: help regen regen-all open workspace clean

help: ## Show this list
	@grep -E '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "}; {printf "  %-12s %s\n", $$1, $$2}'

regen: ## Regenerate bloomberg-terminal.html from data/wealthcommand.xlsx
	$(PYTHON) scripts/regenerate_dashboard.py

regen-all: regen ## Regenerate both dashboards
	$(PYTHON) scripts/generate_command_center.py

open: regen ## Regenerate, then open the dashboard in your default browser
	open bloomberg-terminal.html

workspace: ## Regenerate both dashboards + restore Personal Finance Spencer layout
	@zsh scripts/restore-personal-finance-layout.zsh

clean: ## Remove macOS/Python junk files
	find . -name '.DS_Store' -delete
	find . -name '__pycache__' -type d -exec rm -rf {} +
