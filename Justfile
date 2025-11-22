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
	if [ ! -d .venv ]; then python3 -m venv .venv; fi
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
