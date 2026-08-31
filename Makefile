.DEFAULT_GOAL := help
PYTHON := python3

.PHONY: help regen open clean

help: ## Show this list
	@grep -E '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "}; {printf "  %-8s %s\n", $$1, $$2}'

regen: ## Regenerate bloomberg-terminal.html from data/wealthcommand.xlsx
	$(PYTHON) scripts/regenerate_dashboard.py

open: regen ## Regenerate, then open the dashboard in your default browser
	open bloomberg-terminal.html

clean: ## Remove macOS/Python junk files
	find . -name '.DS_Store' -delete
	find . -name '__pycache__' -type d -exec rm -rf {} +
