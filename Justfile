set shell := ["bash", "-lc"]
python_bin := ".venv/bin/python"

python_cmd := "if [ -x \"" + python_bin + "\" ]; then echo \"" + python_bin + "\"; elif command -v python3 >/dev/null 2>&1; then command -v python3; else command -v python || true; fi"
nvm_use := "export NVM_DIR=\"$HOME/.nvm\"; if [ -s \"$NVM_DIR/nvm.sh\" ]; then . \"$NVM_DIR/nvm.sh\"; elif [ -s \"/usr/local/opt/nvm/nvm.sh\" ]; then . \"/usr/local/opt/nvm/nvm.sh\"; else echo \"nvm not installed; see docs/setup.md\" >&2; exit 1; fi; nvm use --silent >/dev/null || { echo \"nvm use failed; ensure $(cat .nvmrc) is installed\" >&2; exit 1; }"

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
	PYTHON_CMD=$({{python_cmd}}); \
	if [ -z "$PYTHON_CMD" ]; then \
		echo "Python not found. Run 'just setup' first."; \
		exit 1; \
	fi; \
	if [ "{{addon}}" = "all" ]; then \
		for a in $("${PYTHON_CMD}" tools/addon_builder.py names); do \
			"${PYTHON_CMD}" tools/addon_builder.py build "$a"; \
		done; \
	else \
		"${PYTHON_CMD}" tools/addon_builder.py build "{{addon}}"; \
	fi

deploy addon="all": deploy-preflight setup-build-tools
	{{nvm_use}}; \
	PYTHON_CMD=$({{python_cmd}}); \
	if [ -z "$PYTHON_CMD" ]; then \
		echo "Python not found. Run 'just setup' first."; \
		exit 1; \
	fi; \
	if [ "{{addon}}" = "all" ]; then \
		for a in $("${PYTHON_CMD}" tools/addon_builder.py names); do \
			"${PYTHON_CMD}" tools/addon_builder.py deploy "$a"; \
		done; \
	else \
		"${PYTHON_CMD}" tools/addon_builder.py deploy "{{addon}}"; \
	fi
	@echo ""
	@echo "Deploying Home Assistant configs..."
	cd new-hass-configs && just deploy

test addon="all":
	PYTHON_CMD=$({{python_cmd}}); \
	if [ -z "$PYTHON_CMD" ]; then \
		echo "Python not found. Run 'just setup' first."; \
		exit 1; \
	fi; \
	if [ "{{addon}}" = "all" ]; then \
		for a in $("${PYTHON_CMD}" tools/addon_builder.py names); do \
			"${PYTHON_CMD}" tools/addon_builder.py test "$a"; \
		done; \
	else \
		"${PYTHON_CMD}" tools/addon_builder.py test "{{addon}}"; \
	fi

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
