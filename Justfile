import "./talos/just/nvm.just"

set shell := ["bash", "-lc"]
talos_bin := "talos/build/bin/talos"

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

talos-build:
	#!/usr/bin/env bash
	set -euo pipefail
	./talos/build.sh

printer-image:
	#!/usr/bin/env bash
	set -euo pipefail
	REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
	just --justfile "${REPO_ROOT}/printer/Justfile" --working-directory "${REPO_ROOT}/printer" build

ha-addon addon="all": talos-build
	args=(); \
	if [ "{{addon}}" != "all" ]; then args+=("{{addon}}"); fi; \
	"{{talos_bin}}" addons run ha-addon "${args[@]}"

deploy addon="all": deploy-preflight talos-build
	REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"; \
	export NVM_DIR="$REPO_ROOT/build/nvm"; \
	{{nvm_use}}; \
	args=(); \
	if [ "{{addon}}" != "all" ]; then args+=("{{addon}}"); fi; \
	"{{talos_bin}}" addons run deploy "${args[@]}"
	@echo ""
	@echo "Deploying Home Assistant configs..."
	cd new-hass-configs && just deploy

test addon="all":
		@if [ ! -x "{{talos_bin}}" ]; then ./talos/build.sh; fi; \
		( cd talos && build/venv/bin/python -m pip install -e '.[test]' >/dev/null && build/venv/bin/python -m pytest tests ); \
		args=(); \
		if [ "{{addon}}" != "all" ]; then args+=("{{addon}}"); fi; \
		"{{talos_bin}}" addons run test "${args[@]}"

addons:
	if [ ! -x "{{talos_bin}}" ]; then ./talos/build.sh; fi; \
	"{{talos_bin}}" addon list

setup:
	@bash talos/setup_dev_env.sh

kill:
	if [ ! -x "{{talos_bin}}" ]; then ./talos/build.sh; fi; \
	"{{talos_bin}}" ports kill

dev:
	if [ ! -x "{{talos_bin}}" ]; then ./talos/build.sh; fi; \
	"{{talos_bin}}" dev
