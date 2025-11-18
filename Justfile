set shell := ["bash", "-lc"]
addons := `python tools/addon_builder.py names`

setup:
	if [ ! -d .venv ]; then python -m venv .venv; fi
	. .venv/bin/activate && pip install -r requirements.txt

ha-addon addon="all":
	if [ "{{addon}}" = "all" ]; then \
		for a in {{addons}}; do \
			python tools/addon_builder.py build "$a"; \
		done; \
	else \
		python tools/addon_builder.py build "{{addon}}"; \
	fi

deploy addon="all":
	if [ "{{addon}}" = "all" ]; then \
		for a in {{addons}}; do \
			python tools/addon_builder.py deploy "$a"; \
		done; \
	else \
		python tools/addon_builder.py deploy "{{addon}}"; \
	fi

test addon="all":
	if [ "{{addon}}" = "all" ]; then \
		for a in {{addons}}; do \
			python tools/addon_builder.py test "$a"; \
		done; \
	else \
		python tools/addon_builder.py test "{{addon}}"; \
	fi

addons:
	python tools/addon_builder.py list
