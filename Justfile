# Smarthome Project Root Justfile
# Main orchestration for Home Assistant addon development and deployment

# Import shared libraries
import "./talos/just/common.just"
import "./talos/just/nvm.just"

# ============================================================================
# SETTINGS
# ============================================================================

set dotenv-load

# ============================================================================
# PROJECT VARIABLES
# ============================================================================

# Home Assistant configs directory
hass_configs_dir := "new-hass-configs"

# ============================================================================
# SETUP AND VALIDATION
# ============================================================================

# Validate deployment prerequisites
[group: 'validation']
deploy-preflight:
	#!/usr/bin/env bash
	set -euo pipefail
	REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
	if [ ! -f ".nvmrc" ]; then
		echo "Missing .nvmrc; cannot select Node runtime." >&2
		exit 1
	fi
	if [ ! -f ".python-version" ]; then
		echo "Missing .python-version; cannot select Python runtime." >&2
		exit 1
	fi
	# Ensure pyenv is available
	if ! command -v pyenv >/dev/null 2>&1; then
		echo "pyenv is required but not available. Run 'just setup' first." >&2
		exit 1
	fi
	# Initialize pyenv (no shell profile modifications needed)
	eval "$(pyenv init -)"
	# Check Python version
	required_python=$(tr -d '[:space:]' < .python-version)
	if ! pyenv versions --bare | grep -q "^${required_python}$"; then
		echo "Python ${required_python} not installed via pyenv. Run 'just setup' first." >&2
		exit 1
	fi
	pyenv local "$required_python"
	# Check Node version using self-contained nvm
	export NVM_DIR="$REPO_ROOT/build/nvm"
	{{nvm_use}}
	expected=$(tr -d ' \t\r\n' < .nvmrc)
	current=$(nvm current)
	if [ "${current#v}" != "${expected#v}" ]; then
		echo "Node version mismatch (expected ${expected}, got ${current}). Re-run 'just setup' to install the correct Node version via self-contained nvm." >&2
		exit 1
	fi
	# Check required tools
	for bin in python3 rsync ssh scp tar; do
		if ! command -v "$bin" >/dev/null 2>&1; then
			echo "Missing required tool: $bin" >&2
			exit 1
		fi
	done

# Build talos binary with proper Python environment
[group: 'build']
talos-build:
	#!/usr/bin/env bash
	set -euo pipefail
	# Ensure pyenv is initialized before building talos
	if ! command -v pyenv >/dev/null 2>&1; then
		echo "pyenv is required but not available. Run 'just setup' first." >&2
		exit 1
	fi
	eval "$(pyenv init -)"
	required_python=$(tr -d '[:space:]' < .python-version)
	pyenv local "$required_python"
	./talos/build.sh

# Build printer service container image
[group: 'build']
printer-image:
	#!/usr/bin/env bash
	set -euo pipefail
	REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
	just --justfile "${REPO_ROOT}/printer/Justfile" --working-directory "${REPO_ROOT}/printer" build

# ============================================================================
# ADDON MANAGEMENT
# ============================================================================

# Build Home Assistant addons
[group: 'build']
ha-addon addon="all": talos-build
	args=(); \
	if [ "{{addon}}" != "all" ]; then args+=("{{addon}}"); fi; \
	if [ ${#args[@]} -eq 0 ]; then \
		"{{talos_bin}}" addons run ha-addon; \
	else \
		"{{talos_bin}}" addons run ha-addon "${args[@]}"; \
	fi

# ============================================================================
# DEPLOYMENT
# ============================================================================

# Deploy addons and Home Assistant configs
[group: 'deploy']
deploy addon="all" *args="":
	@just deploy-preflight >/dev/null 2>&1
	@if [ ! -x "{{talos_bin}}" ]; then ./talos/build.sh >/dev/null 2>&1; fi
	@echo "🚀 Starting enhanced deployment..."
	@set -e; \
	REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"; \
	export NVM_DIR="$$REPO_ROOT/build/nvm"; \
	{{nvm_use}} >/dev/null 2>&1; \
	if [ "{{addon}}" != "all" ]; then \
		"{{talos_bin}}" addons deploy "{{addon}}" {{args}}; \
	else \
		"{{talos_bin}}" addons deploy {{args}}; \
	fi
	@echo ""
	@echo "🏠 Deploying Home Assistant configs..."
	@cd new-hass-configs && just deploy >/dev/null 2>&1
	@echo "✅ Deployment completed successfully!"

# Deploy with verbose output for troubleshooting
[group: 'deploy']
deploy-verbose addon="all" *args="":
	@just deploy-preflight >/dev/null 2>&1
	@if [ ! -x "{{talos_bin}}" ]; then ./talos/build.sh >/dev/null 2>&1; fi
	@echo "🚀 Starting enhanced deployment (verbose mode)..."
	@set -e; \
	REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"; \
	export NVM_DIR="$$REPO_ROOT/build/nvm"; \
	{{nvm_use}} >/dev/null 2>&1; \
	if [ "{{addon}}" != "all" ]; then \
		"{{talos_bin}}" addons deploy "{{addon}}" --verbose {{args}}; \
	else \
		"{{talos_bin}}" addons deploy --verbose {{args}}; \
	fi
	@echo ""
	@echo "🏠 Deploying Home Assistant configs..."
	@cd new-hass-configs && just deploy >/dev/null 2>&1
	@echo "✅ Deployment completed successfully!"

# Dry run deployment to see what would be deployed
[group: 'deploy']
deploy-dry-run addon="all":
	@just deploy-preflight >/dev/null 2>&1
	@if [ ! -x "{{talos_bin}}" ]; then ./talos/build.sh >/dev/null 2>&1; fi
	@echo "🔍 Dry run deployment preview..."
	@set -e; \
	REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"; \
	export NVM_DIR="$$REPO_ROOT/build/nvm"; \
	{{nvm_use}} >/dev/null 2>&1; \
	if [ "{{addon}}" != "all" ]; then \
		"{{talos_bin}}" addons deploy "{{addon}}" --dry-run; \
	else \
		"{{talos_bin}}" addons deploy --dry-run; \
	fi
	@echo ""
	@echo "🏠 Home Assistant configs would also be deployed"
	@echo ""
	@echo "📋 This was a dry run - no changes were made"

# Detailed dry run with verbose output for troubleshooting
[group: 'deploy']
deploy-dry-run-verbose addon="all":
	@just deploy-preflight >/dev/null 2>&1
	@if [ ! -x "{{talos_bin}}" ]; then ./talos/build.sh >/dev/null 2>&1; fi
	@echo "🔍 Detailed dry run deployment preview..."
	@set -e; \
	REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"; \
	export NVM_DIR="$$REPO_ROOT/build/nvm"; \
	{{nvm_use}} >/dev/null 2>&1; \
	if [ "{{addon}}" != "all" ]; then \
		"{{talos_bin}}" addons deploy "{{addon}}" --dry-run --verbose; \
	else \
		"{{talos_bin}}" addons deploy --dry-run --verbose; \
	fi
	@echo ""
	@echo "🏠 Home Assistant configs would also be deployed"
	@echo ""
	@echo "📋 This was a detailed dry run - no changes were made"

# ============================================================================
# TESTING
# ============================================================================

# Run fast tests for addons (excludes slow integration tests)
[group: 'test']
test addon="all":
		@set -e; \
		if [ ! -x "{{talos_bin}}" ]; then ./talos/build.sh; fi; \
		echo "⚡ Running fast tests (excluding slow integration tests)..."; \
		( cd talos && build/venv/bin/python -m pip install -e '.[test]' >/dev/null && build/venv/bin/python -m pytest -m "not slow" tests ); \
		args=(); \
		if [ "{{addon}}" != "all" ]; then args+=("{{addon}}"); fi; \
		if [ ${#args[@]} -eq 0 ]; then \
			"{{talos_bin}}" addons run test; \
			echo ""; \
			echo "Running container build tests..."; \
			"{{talos_bin}}" addons run container-test; \
		else \
			"{{talos_bin}}" addons run test "${args[@]}"; \
			echo ""; \
			echo "Running container build tests..."; \
			"{{talos_bin}}" addons run container-test "${args[@]}"; \
		fi

# Run all tests including slow integration tests
[group: 'test']
test-all addon="all":
		@set -e; \
		if [ ! -x "{{talos_bin}}" ]; then ./talos/build.sh; fi; \
		echo "🧪 Running all tests (including slow integration tests)..."; \
		( cd talos && build/venv/bin/python -m pip install -e '.[test]' >/dev/null && build/venv/bin/python -m pytest tests ); \
		args=(); \
		if [ "{{addon}}" != "all" ]; then args+=("{{addon}}"); fi; \
		if [ ${#args[@]} -eq 0 ]; then \
			"{{talos_bin}}" addons run test; \
			echo ""; \
			echo "Running container build tests..."; \
			"{{talos_bin}}" addons run container-test; \
		else \
			"{{talos_bin}}" addons run test "${args[@]}"; \
			echo ""; \
			echo "Running container build tests..."; \
			"{{talos_bin}}" addons run container-test "${args[@]}"; \
		fi

# Run only slow/integration tests
[group: 'test']
test-slow:
		@set -e; \
		if [ ! -x "{{talos_bin}}" ]; then ./talos/build.sh; fi; \
		echo "🐌 Running slow and integration tests..."; \
		( cd talos && build/venv/bin/python -m pip install -e '.[test]' >/dev/null && build/venv/bin/python -m pytest -m "slow or integration" tests )

# ============================================================================
# INFORMATION AND UTILITIES
# ============================================================================

# List all available addons
[group: 'info']
addons:
	if [ ! -x "{{talos_bin}}" ]; then ./talos/build.sh; fi; \
	"{{talos_bin}}" addon list

# ============================================================================
# SETUP AND DEVELOPMENT
# ============================================================================

# Set up development environment
[group: 'setup']
setup:
	@set -euo pipefail; \
	REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"; \
	cd "$REPO_ROOT"; \
	if git submodule status >/dev/null 2>&1; then \
		git submodule update --init --recursive; \
	fi; \
	bash talos/setup_dev_env.sh

# Kill development services on conflicting ports
[group: 'dev']
kill:
	if [ ! -x "{{talos_bin}}" ]; then ./talos/build.sh; fi; \
	"{{talos_bin}}" ports kill

# Start development environment
[group: 'dev']
dev:
	@if [ ! -x "{{talos_bin}}" ]; then ./talos/build.sh; fi
	@"{{talos_bin}}" dev

# ============================================================================
# ALIASES FOR COMMON COMMANDS
# ============================================================================

# Aliases for deployment
alias d := deploy
alias dd := deploy-dry-run
alias dv := deploy-verbose

# Aliases for testing
alias t := test

# Aliases for development
alias s := setup
alias k := kill

# Aliases for information
alias ls := addons
