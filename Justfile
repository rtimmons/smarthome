import "./talos/just/nvm.just"

set shell := ["bash", "-lc"]
talos_bin := "talos/build/bin/talos"

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

talos-build:
	#!/usr/bin/env bash
	set -euo pipefail
	./talos/build.sh

ha-addon addon="all": talos-build
	args=(); \
	if [ "{{addon}}" != "all" ]; then args+=("{{addon}}"); fi; \
	"{{talos_bin}}" addons run ha-addon "${args[@]}"

deploy addon="all": deploy-preflight talos-build
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
