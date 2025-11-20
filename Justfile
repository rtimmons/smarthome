set shell := ["bash", "-lc"]
python_bin := ".venv/bin/python"

python_cmd := "if [ -x \"" + python_bin + "\" ]; then echo \"" + python_bin + "\"; elif command -v python3 >/dev/null 2>&1; then command -v python3; else command -v python || true; fi"

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

deploy addon="all":
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
