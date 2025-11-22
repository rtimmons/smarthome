import "./tools/just/nvm.just"

set shell := ["bash", "-lc"]
python_bin := ".venv/bin/python"
addon_runner := "tools/run_for_addons.sh"

python_cmd := "if [ -x \"" + python_bin + "\" ]; then echo \"" + python_bin + "\"; elif command -v python3 >/dev/null 2>&1; then command -v python3; else command -v python || true; fi"

deploy-preflight:
	#!/usr/bin/env bash
	set -euo pipefail
	if [ ! -f ".nvmrc" ]; then
		echo "Missing .nvmrc; cannot select Node runtime." >&2
		exit 1
	fi
	python_major_minor="3.12"
	if [ -f ".python-version" ]; then
		python_version_raw=$(tr -d '[:space:]' < .python-version | awk -F. '{print $1"."$2}' || true)
		if [ -n "${python_version_raw:-}" ]; then
			python_major_minor="$python_version_raw"
		fi
	fi
	python_formula="python@${python_major_minor}"
	if ! command -v python3 >/dev/null 2>&1; then
		if command -v brew >/dev/null 2>&1; then
			echo "Installing ${python_formula} via Homebrew (one-time)..." >&2
			HOMEBREW_NO_AUTO_UPDATE=1 brew install "${python_formula}"
		else
			echo "Missing required tool: python3" >&2
			exit 1
		fi
	fi
	{{nvm_use}}
	expected=$(tr -d ' \t\r\n' < .nvmrc)
	current=$(nvm current)
	if [ "${current#v}" != "${expected#v}" ]; then
		echo "Node version mismatch (expected ${expected}, got ${current}). Run 'nvm install' then retry." >&2
		exit 1
	fi
	for bin in python3 rsync ssh scp tar; do
		if ! command -v "$bin" >/dev/null 2>&1; then
			echo "Missing required tool: $bin" >&2
			exit 1
		fi
	done

setup-build-tools:
	#!/usr/bin/env bash
	set -euo pipefail
	if [ ! -x ".venv/bin/python3" ]; then
		rm -rf .venv
		python3 -m venv .venv
	fi
	. .venv/bin/activate && pip install -r requirements.txt

ha-addon addon="all":
	args=(); \
	if [ "{{addon}}" != "all" ]; then args+=("{{addon}}"); fi; \
	"{{addon_runner}}" ha-addon "${args[@]}"

deploy addon="all": deploy-preflight setup-build-tools
	{{nvm_use}}; \
	args=(); \
	if [ "{{addon}}" != "all" ]; then args+=("{{addon}}"); fi; \
	"{{addon_runner}}" deploy "${args[@]}"
	@echo ""
	@echo "Deploying Home Assistant configs..."
	cd new-hass-configs && just deploy

test addon="all":
	args=(); \
	if [ "{{addon}}" != "all" ]; then args+=("{{addon}}"); fi; \
	"{{addon_runner}}" test "${args[@]}"

addons:
	PYTHON_CMD=$({{python_cmd}}); \
	if [ -z "$PYTHON_CMD" ]; then \
		echo "Python not found. Run 'just setup' first."; \
		exit 1; \
	fi; \
	"$PYTHON_CMD" tools/addon_builder.py list

setup:
	@bash tools/setup_dev_env.sh

kill:
	PYTHON_CMD=$({{python_cmd}}); \
	if [ -z "$PYTHON_CMD" ]; then \
		echo "Python not found. Run 'just setup' first."; \
		exit 1; \
	fi; \
	"$PYTHON_CMD" tools/manage_ports.py kill

dev:
	.venv/bin/python tools/dev_orchestrator.py
