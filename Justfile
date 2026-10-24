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

# Repository-local Home Assistant SSH identity (ignored by Git)
ha_ssh_key := ".ssh/id_ed25519_codex_smarthome"
ha_ssh_target := "root@homeassistant.local"

# ============================================================================
# SETUP AND VALIDATION
# ============================================================================

# Create the repository-local Home Assistant SSH keypair
[group: 'setup']
ha-ssh-key-create:
	#!/usr/bin/env bash
	set -euo pipefail
	REPO_ROOT="$(git rev-parse --show-toplevel)"
	KEY_PATH="${REPO_ROOT}/{{ha_ssh_key}}"
	KEY_DIR="$(dirname "${KEY_PATH}")"
	umask 077
	mkdir -p "${KEY_DIR}"
	chmod 700 "${KEY_DIR}"
	if [[ -e "${KEY_PATH}" || -e "${KEY_PATH}.pub" ]]; then
		if [[ ! -f "${KEY_PATH}" || ! -f "${KEY_PATH}.pub" ]]; then
			echo "Incomplete SSH keypair at ${KEY_PATH}; refusing to overwrite it." >&2
			exit 1
		fi
		ssh-keygen -lf "${KEY_PATH}.pub" >/dev/null
		chmod 600 "${KEY_PATH}"
		chmod 644 "${KEY_PATH}.pub"
		echo "Home Assistant SSH keypair already exists at ${KEY_PATH}."
		exit 0
	fi
	ssh-keygen -q -t ed25519 -N "" -C "codex-smarthome@homeassistant.local" -f "${KEY_PATH}"
	chmod 600 "${KEY_PATH}"
	chmod 644 "${KEY_PATH}.pub"
	echo "Created Home Assistant SSH keypair at ${KEY_PATH}."

# Install the repository-local public key on Home Assistant (human-run; may invoke 1Password once)
[group: 'setup']
ha-ssh-key-copy: ha-ssh-key-create
	#!/usr/bin/env bash
	set -euo pipefail
	REPO_ROOT="$(git rev-parse --show-toplevel)"
	KEY_PATH="${REPO_ROOT}/{{ha_ssh_key}}"
	ssh-copy-id -i "${KEY_PATH}.pub" -o IdentitiesOnly=no "{{ha_ssh_target}}"
	ssh -i "${KEY_PATH}" -o IdentitiesOnly=yes -o BatchMode=yes "{{ha_ssh_target}}" exit
	echo "Verified repository-local SSH authentication to {{ha_ssh_target}}."

# Recreate compatibility links from owner-only state outside the checkout.
[group: 'setup']
checkout-prepare:
	@python3 tools/checkout/state.py prepare

[group: 'backup']
[positional-arguments]
checkout-state action="status" *args:
	@python3 tools/checkout/state.py "$1" "${@:2}"

[group: 'test']
checkout-test:
	@python3 -m unittest discover -s tools/checkout -p 'test_*.py'

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
	# Rebuild the pinned Python runtime when necessary after a clean.
	source "$REPO_ROOT/talos/scripts/python_use.sh"
	# Ensure pyenv is available
	if ! command -v pyenv >/dev/null 2>&1; then
		echo "pyenv is required but not available. Run 'just setup' first." >&2
		exit 1
	fi
	# Check Python version
	required_python=$(tr -d '[:space:]' < .python-version)
	# Consume all output so pipefail does not mistake pyenv's SIGPIPE for a missing version.
	if ! pyenv versions --bare | grep "^${required_python}$" >/dev/null; then
		echo "Python ${required_python} not installed via pyenv. Run 'just setup' first." >&2
		exit 1
	fi
	pyenv prefix "$required_python" >/dev/null
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
	required_python=$(tr -d '[:space:]' < .python-version)
	PYENV_VERSION="$required_python" ./talos/build.sh

# Build printer service container image
[group: 'build']
printer-image:
	#!/usr/bin/env bash
	set -euo pipefail
	REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
	just --justfile "${REPO_ROOT}/printer/Justfile" --working-directory "${REPO_ROOT}/printer" build

# Show the resolved, non-secret endpoint and auth configuration for PNG printing
[group: 'print']
printer-config:
	#!/usr/bin/env bash
	set -euo pipefail
	REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
	exec just --justfile "${REPO_ROOT}/printer/Justfile" \
		--working-directory "${REPO_ROOT}/printer" print-client-config

# Validate a PNG locally and against the printer service without printing
[group: 'print']
print-check file:
	#!/usr/bin/env bash
	set -euo pipefail
	REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
	FILE="$1"
	if [[ "${FILE}" != /* ]]; then FILE="${REPO_ROOT}/${FILE}"; fi
	exec just --justfile "${REPO_ROOT}/printer/Justfile" \
		--working-directory "${REPO_ROOT}/printer" print-file-check "${FILE}"

# Validate, preflight, and print one PNG (print requests are never retried)
[group: 'print']
print file:
	#!/usr/bin/env bash
	set -euo pipefail
	REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
	FILE="$1"
	if [[ "${FILE}" != /* ]]; then FILE="${REPO_ROOT}/${FILE}"; fi
	exec just --justfile "${REPO_ROOT}/printer/Justfile" \
		--working-directory "${REPO_ROOT}/printer" print-file "${FILE}"

# ============================================================================
# ADDON MANAGEMENT
# ============================================================================

# Create and verify a native Supervisor backup of all repository add-on state
[group: 'backup']
addon-state-backup *args="": talos-build
	@"{{talos_bin}}" backup addon-state \
		--ha-host "{{ha_host}}" \
		--ha-port "{{ha_port}}" \
		--ha-user "{{ha_user}}" {{args}}

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

[private]
talos-deploy mode addon *args:
	@set -e; \
	REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"; \
	export NVM_DIR="$$REPO_ROOT/build/nvm"; \
	{{nvm_use}} >/dev/null 2>&1; \
	talos_args=""; \
	if [ "{{mode}}" = "verbose" ]; then talos_args="${talos_args} --verbose"; fi; \
	if [ "{{mode}}" = "dry-run" ]; then talos_args="${talos_args} --dry-run"; fi; \
	if [ "{{mode}}" = "dry-run-verbose" ]; then talos_args="${talos_args} --dry-run --verbose"; fi; \
	if [ "{{addon}}" != "all" ]; then talos_args="${talos_args} {{addon}}"; fi; \
	"{{talos_bin}}" deploy ${talos_args} {{args}}

# ============================================================================
# DEPLOYMENT
# ============================================================================

# Deploy addons and Home Assistant configs
[group: 'deploy']
deploy addon="all" *args="": checkout-prepare
	@just deploy-preflight >/dev/null 2>&1
	@if [ ! -x "{{talos_bin}}" ]; then ./talos/build.sh >/dev/null 2>&1; fi
	@./wiki/run with-deployment --scope home-assistant -- just talos-deploy normal "{{addon}}" {{args}}
	@echo "✅ Deployment completed successfully!"

# Deploy with verbose output for troubleshooting
[group: 'deploy']
deploy-verbose addon="all" *args="": checkout-prepare
	@just deploy-preflight >/dev/null 2>&1
	@if [ ! -x "{{talos_bin}}" ]; then ./talos/build.sh >/dev/null 2>&1; fi
	@./wiki/run with-deployment --scope home-assistant -- just talos-deploy verbose "{{addon}}" {{args}}
	@echo "✅ Deployment completed successfully!"

# Dry run deployment to see what would be deployed
[group: 'deploy']
deploy-dry-run addon="all": checkout-prepare
	@just deploy-preflight >/dev/null 2>&1
	@if [ ! -x "{{talos_bin}}" ]; then ./talos/build.sh >/dev/null 2>&1; fi
	@echo "🔍 Dry run deployment preview..."
	@just talos-deploy dry-run "{{addon}}"
	@echo "📋 This was a dry run - no changes were made"

# Detailed dry run with verbose output for troubleshooting
[group: 'deploy']
deploy-dry-run-verbose addon="all": checkout-prepare
	@just deploy-preflight >/dev/null 2>&1
	@if [ ! -x "{{talos_bin}}" ]; then ./talos/build.sh >/dev/null 2>&1; fi
	@echo "🔍 Detailed dry run deployment preview..."
	@just talos-deploy dry-run-verbose "{{addon}}"
	@echo "📋 This was a detailed dry run - no changes were made"

# ============================================================================
# TESTING
# ============================================================================

# Run fast tests for addons (excludes slow integration tests)
[group: 'test']
identity-test:
	#!/usr/bin/env bash
	set -euo pipefail
	export UV_PROJECT_ENVIRONMENT="$PWD/build/wiki/venv"
	exec uv run --project wiki --python "$(cat .python-version)" --frozen python -m unittest discover -s identity-infra -p 'test_*.py'

[group: 'test']
test addon="all":
		@just wiki-check
		@just checkout-test
		@just identity-test
		@set -e; \
		if [ ! -x "{{talos_bin}}" ]; then ./talos/build.sh; fi; \
		echo "⚡ Running fast tests (excluding slow integration tests)..."; \
		( cd talos && ./build.sh >/dev/null && build/venv/bin/python -m pytest -m "not slow" tests ); \
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
		@just identity-test
		@set -e; \
		if [ ! -x "{{talos_bin}}" ]; then ./talos/build.sh; fi; \
		echo "🧪 Running all tests (including slow integration tests)..."; \
		( cd talos && ./build.sh >/dev/null && build/venv/bin/python -m pytest tests ); \
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
		( cd talos && ./build.sh >/dev/null && build/venv/bin/python -m pytest -m "slow or integration" tests )

# ============================================================================
# INFORMATION AND UTILITIES
# ============================================================================

# Diagnose Z-Wave-heavy scene slowness using live cache/log data
[group: 'info']
zwave-diagnose *args="":
	@cd new-hass-configs && just zwave-diagnose {{args}}

# Regenerate the shared dashboard/Sonos room definitions
[group: 'build']
rooms-generate:
	@{{nvm_use}} && node home-model/generate.cjs

# Check shared room definitions without changing files
[group: 'test']
rooms-check:
	@{{nvm_use}} && node home-model/generate.cjs --check

# Compare speaker-reported Sonos names with HA names and physical areas
[group: 'info']
rooms-verify *args="":
	@{{nvm_use}} && grid-dashboard/ExpressServer/node_modules/.bin/tsx home-model/verify-speaker-names.ts {{args}}

# Inspect room names, fixed-speaker assignments and legacy area references
[group: 'info']
rooms-audit:
	@{{nvm_use}} && grid-dashboard/ExpressServer/node_modules/.bin/tsx home-model/reconcile-areas.ts

# Align known area names; optionally remove audited, empty legacy areas
[group: 'deploy']
rooms-apply *args="":
	@{{nvm_use}} && grid-dashboard/ExpressServer/node_modules/.bin/tsx home-model/reconcile-areas.ts --apply {{args}}

# Compare reviewed device/entity locations with live Home Assistant registries
[group: 'info']
areas-audit *args="":
	@{{nvm_use}} && grid-dashboard/ExpressServer/node_modules/.bin/tsx home-model/reconcile-placements.ts {{args}}

# Apply reviewed area metadata only; save private before/after recovery evidence
[group: 'deploy']
areas-apply *args="":
	@{{nvm_use}} && grid-dashboard/ExpressServer/node_modules/.bin/tsx home-model/reconcile-placements.ts --apply {{args}}

# Capture the live Home Assistant device and entity registries
[group: 'info']
ha-inventory *args="":
	@cd new-hass-configs && just inventory {{args}}

# Read one live Home Assistant entity state
[group: 'info']
ha-state entity_id *args="":
	@cd new-hass-configs && just ha-state "{{entity_id}}" {{args}}

# Call a live Home Assistant service for one entity
[group: 'deploy']
ha-call service entity_id *args="":
	@cd new-hass-configs && just ha-call "{{service}}" "{{entity_id}}" {{args}}

# Capture a timestamped live Z-Wave scene inventory snapshot
[group: 'info']
zwave-inventory *args="":
	@cd new-hass-configs && just zwave-inventory {{args}}

# Apply instant/fast ramp settings across the live Z-Wave network
[group: 'deploy']
zwave-apply-instant-ramps *args="":
	@cd new-hass-configs && just zwave-apply-instant-ramps {{args}}

# Verify that instant/fast ramp settings are in effect
[group: 'validation']
zwave-verify-instant-ramps *args="":
	@cd new-hass-configs && just zwave-verify-instant-ramps {{args}}

# Install repo-owned priority device configs and restart only Z-Wave JS
[group: 'deploy']
zwave-deploy-device-configs:
	@cd new-hass-configs && just zwave-deploy-device-configs

# Install/remove the version-guarded Transport Service correction and restart Z-Wave JS
[group: 'deploy']
zwave-driver-hotfix action="install":
	@{{nvm_use}} && cd new-hass-configs && just zwave-driver-hotfix "{{action}}"

[group: 'deploy']
zwave-routes action="check":
	@{{nvm_use}} && cd new-hass-configs && just zwave-routes "{{action}}"

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
# CONFIGURATION SYNC
# ============================================================================

# Fetch live Home Assistant configuration changes into repository
[group: 'config']
fetch-config *args="":
	@cd new-hass-configs && just fetch-config {{args}}

# Detect configuration drift between repository and live system
[group: 'config']
detect-changes:
	@cd new-hass-configs && just detect-changes

# Show diff and reconciliation options for a config file
[group: 'config']
reconcile FILE:
	@cd new-hass-configs && just reconcile {{FILE}}

# Force deploy with optional backup (skips sync checks)
[group: 'deploy']
deploy-force *args="":
	@cd new-hass-configs && just deploy-force {{args}}

# ============================================================================
# USENET CATALOG
# ============================================================================

# Manage the isolated NAS Git host with the existing dedicated NAS environment.
[group: 'git-host']
git-host action='status':
	@if [ {{quote(action)}} = deploy ]; then ./wiki/run with-deployment --scope git-host -- just _git-host {{quote(action)}}; else just _git-host {{quote(action)}}; fi

[private]
_git-host action:
	@UV_CACHE_DIR="$PWD/build/wiki/uv-cache" UV_PROJECT_ENVIRONMENT="$PWD/build/wiki/venv" just --justfile usenet-infra/Justfile --working-directory usenet-infra --command uv run --project ../wiki --python "$(cat .python-version)" --frozen python ../git-host/manage.py {{quote(action)}}

[group: 'git-host']
git-host-test:
	@UV_CACHE_DIR="$PWD/build/wiki/uv-cache" UV_PROJECT_ENVIRONMENT="$PWD/build/wiki/venv" uv run --project wiki --python "$(cat .python-version)" --frozen python -m unittest discover -s git-host -p 'test_*.py' -v
	@shellcheck git-host/backup.sh

# Run any infrastructure recipe without maintaining a second command list.
# Use `just usenet --list`; offline recovery also requires root --no-dotenv.
[group: 'usenet']
usenet *args:
	@just --justfile usenet-infra/Justfile --working-directory usenet-infra "$@"

# Check repository-wide recovery inventory metadata without reading secrets.
[group: 'backup']
[positional-arguments]
secrets-check *args:
	#!/usr/bin/env bash
	set -euo pipefail
	exec python3 usenet-infra/scripts/secrets-check.py "$@"

# Cache reviewed recovery tools without loading infrastructure dotenv inputs.
[group: 'backup']
usenet-crypto-bootstrap:
	@just --no-dotenv --justfile usenet-infra/Justfile --working-directory usenet-infra crypto-bootstrap

# Record the public SOPS recipient from the one-process SOPS_AGE_KEY environment value.
[group: 'backup']
[positional-arguments]
usenet-recovery-master-init confirmation:
	#!/usr/bin/env bash
	set -euo pipefail
	exec just --no-dotenv --justfile usenet-infra/Justfile --working-directory usenet-infra recovery-master-init "$1"

# Restore ignored local secrets from the committed SOPS vault and a one-process identity.
[group: 'backup']
[positional-arguments]
setup-secrets *args:
	#!/usr/bin/env bash
	set -euo pipefail
	exec just --no-dotenv --justfile usenet-infra/Justfile --working-directory usenet-infra setup-secrets "$@"

# Encrypt the current allowlisted local inputs into the committed SOPS vault.
[group: 'backup']
[positional-arguments]
secrets-encrypt *args:
	#!/usr/bin/env bash
	set -euo pipefail
	exec just --no-dotenv --justfile usenet-infra/Justfile --working-directory usenet-infra secrets-encrypt "$@"

# Capture allowlisted states/archives into a new encrypted recovery package.
[group: 'backup']
[positional-arguments]
recovery-capture *args:
	#!/usr/bin/env bash
	set -euo pipefail
	exec ./usenet-infra/scripts/recovery-run bundle capture "$@"

# Authenticate all recovery content offline using the master and restored vault.
[group: 'backup']
[positional-arguments]
recovery-verify *args:
	#!/usr/bin/env bash
	set -euo pipefail
	exec ./usenet-infra/scripts/recovery-run bundle verify "$@"

# Restore authenticated state/archive files; existing different files are refused.
[group: 'backup']
[positional-arguments]
recovery-restore *args:
	#!/usr/bin/env bash
	set -euo pipefail
	exec ./usenet-infra/scripts/recovery-run bundle restore "$@"

# Store or retrieve ciphertext through the dedicated, pinned NAS connection.
[group: 'backup']
[positional-arguments]
recovery-store *args:
	#!/usr/bin/env bash
	set -euo pipefail
	exec ./usenet-infra/scripts/recovery-run store "$@"

# Clone published source, restore the vault, retrieve NAS ciphertext and verify recovery.
[group: 'backup']
[positional-arguments]
recovery-drill *args:
	#!/usr/bin/env bash
	set -euo pipefail
	exec ./usenet-infra/scripts/recovery-run drill "$@"

# List canonical items and whether each is cached on the QNAP
[group: 'usenet']
catalog-list:
	@just --justfile usenet-infra/Justfile --working-directory usenet-infra catalog-list

# Summarize canonical and QNAP cache state
[group: 'usenet']
catalog-status:
	@just --justfile usenet-infra/Justfile --working-directory usenet-infra catalog-status

# Pull and verify one canonical item into the QNAP cache
[group: 'usenet']
catalog-pull item:
	#!/usr/bin/env bash
	set -euo pipefail
	exec just --justfile usenet-infra/Justfile --working-directory usenet-infra catalog-pull "$1"

# Delete only one QNAP cached copy
[group: 'usenet']
catalog-evict item:
	#!/usr/bin/env bash
	set -euo pipefail
	exec just --justfile usenet-infra/Justfile --working-directory usenet-infra catalog-evict "$1"

# List or inspect native Movies/TV titles available for selective NAS copying
[group: 'usenet']
native-list:
	@just --justfile usenet-infra/Justfile --working-directory usenet-infra native-list

[group: 'usenet']
native-status:
	@just --justfile usenet-infra/Justfile --working-directory usenet-infra native-status

[group: 'usenet']
[positional-arguments]
native-pull item:
	#!/usr/bin/env bash
	set -euo pipefail
	exec just --justfile usenet-infra/Justfile --working-directory usenet-infra native-pull "$1"

[group: 'usenet']
[positional-arguments]
native-evict item:
	#!/usr/bin/env bash
	set -euo pipefail
	exec just --justfile usenet-infra/Justfile --working-directory usenet-infra native-evict "$1"

# Run local validation for the Usenet infrastructure project
[group: 'usenet']
usenet-test:
	@just --justfile usenet-infra/Justfile --working-directory usenet-infra test

[group: 'usenet']
usenet-discovery-health:
	@just --justfile usenet-infra/Justfile --working-directory usenet-infra discovery-health

# Deploy only the private, static NAS Usenet wiki.
[group: 'usenet']
usenet-wiki-deploy:
	@just wiki-deploy

# Build and validate the private smarthome field guide.
[group: 'wiki']
wiki-build:
	@./wiki/run build

[group: 'wiki']
wiki-check:
	@./wiki/run check

[group: 'wiki']
wiki-preview:
	@./wiki/run preview

[group: 'wiki']
wiki-deploy:
	@./wiki/run deploy

[group: 'wiki']
wiki-rollback:
	@./wiki/run rollback

[group: 'wiki']
[positional-arguments]
wiki-review component reason:
	@./wiki/run review "$1" "$2"

[private]
wiki-model-export:
	#!/usr/bin/env bash
	set -euo pipefail
	export NVM_DIR="{{repo_root}}/build/nvm"
	{{nvm_use}}
	mkdir -p "{{repo_root}}/build/wiki"
	cd "{{repo_root}}/new-hass-configs/config-generator"
	if [ ! -f node_modules/.package-lock.json ] || [ package-lock.json -nt node_modules/.package-lock.json ]; then npm ci >&2; fi
	npm run build >&2
	node dist/wiki-export.js > "{{repo_root}}/build/wiki/model.json"

# Check cloud applications, Storage Box access, failures, and scratch space
[group: 'usenet']
usenet-cloud-health:
	@just --justfile usenet-infra/Justfile --working-directory usenet-infra cloud-health

# Check Storage Box access, transfer failures, and QNAP cache capacity
[group: 'usenet']
usenet-qnap-health:
	@just --justfile usenet-infra/Justfile --working-directory usenet-infra qnap-health

# Open the configured Storage Box SMB share URLs as Finder volumes on macOS.
# Copy mounts.local.env.example to mounts.local.env and set STORAGEBOX_SMB_VOLUMES.
[group: 'storage']
mount-storage-box:
	#!/usr/bin/env bash
	set -euo pipefail
	REPO_ROOT="$(git rev-parse --show-toplevel)"
	CONFIG_FILE="${MOUNT_CONFIG_FILE:-${REPO_ROOT}/mounts.local.env}"
	explicit_urls="${STORAGEBOX_SMB_VOLUMES:-}"
	if [[ -f "${CONFIG_FILE}" ]]; then
		# This local file contains only SMB URLs; Finder/Keychain retains passwords.
		source "${CONFIG_FILE}"
	fi
	VOLUME_URLS="${explicit_urls:-${STORAGEBOX_SMB_VOLUMES:-}}"
	if [[ "${MOUNT_DRY_RUN:-0}" != "1" && "$(uname)" != "Darwin" ]]; then
		echo "This recipe mounts macOS Finder volumes; run it on your Mac." >&2
		exit 1
	fi
	: "${VOLUME_URLS:?Set STORAGEBOX_SMB_VOLUMES in mounts.local.env (see mounts.local.env.example).}"
	IFS=',' read -r -a urls <<< "${VOLUME_URLS}"
	for url in "${urls[@]}"; do
		url="${url#"${url%%[![:space:]]*}"}"
		url="${url%"${url##*[![:space:]]}"}"
		[[ -n "${url}" ]] || continue
		[[ "${url}" =~ ^smb://[^/]+/.+$ ]] || { echo "Invalid SMB URL: ${url}" >&2; exit 1; }
		authority="${url#smb://}"; authority="${authority%%/*}"
		[[ "${authority}" != *:*@* ]] || { echo "Do not put an SMB password in mounts.local.env." >&2; exit 1; }
		if [[ "${MOUNT_DRY_RUN:-0}" == "1" ]]; then
			echo "Would open ${url}"
		else
			open "${url}"
		fi
	done

# Open the configured Usenet NAS SMB share URLs as Finder volumes on macOS.
# The example configuration covers the current Usenet and Container NAS shares.
[group: 'storage']
mount-usenet-nas:
	#!/usr/bin/env bash
	set -euo pipefail
	REPO_ROOT="$(git rev-parse --show-toplevel)"
	CONFIG_FILE="${MOUNT_CONFIG_FILE:-${REPO_ROOT}/mounts.local.env}"
	explicit_urls="${USENET_NAS_SMB_VOLUMES:-}"
	if [[ -f "${CONFIG_FILE}" ]]; then
		# This local file contains only SMB URLs; Finder/Keychain retains passwords.
		source "${CONFIG_FILE}"
	fi
	VOLUME_URLS="${explicit_urls:-${USENET_NAS_SMB_VOLUMES:-}}"
	if [[ "${MOUNT_DRY_RUN:-0}" != "1" && "$(uname)" != "Darwin" ]]; then
		echo "This recipe mounts macOS Finder volumes; run it on your Mac." >&2
		exit 1
	fi
	: "${VOLUME_URLS:?Set USENET_NAS_SMB_VOLUMES in mounts.local.env (see mounts.local.env.example).}"
	IFS=',' read -r -a urls <<< "${VOLUME_URLS}"
	for url in "${urls[@]}"; do
		url="${url#"${url%%[![:space:]]*}"}"
		url="${url%"${url##*[![:space:]]}"}"
		[[ -n "${url}" ]] || continue
		[[ "${url}" =~ ^smb://[^/]+/.+$ ]] || { echo "Invalid SMB URL: ${url}" >&2; exit 1; }
		authority="${url#smb://}"; authority="${authority%%/*}"
		[[ "${authority}" != *:*@* ]] || { echo "Do not put an SMB password in mounts.local.env." >&2; exit 1; }
		if [[ "${MOUNT_DRY_RUN:-0}" == "1" ]]; then
			echo "Would open ${url}"
		else
			open "${url}"
		fi
	done

# ============================================================================
# ALIASES FOR COMMON COMMANDS
# ============================================================================

# Aliases for deployment
alias d := deploy
alias dd := deploy-dry-run
alias dv := deploy-verbose
alias df := deploy-force

# Aliases for configuration sync
alias fc := fetch-config
alias dc := detect-changes

# Aliases for testing
alias t := test

# Aliases for development
alias s := setup
alias k := kill

# Aliases for information
alias ls := addons

# Open Filex through a loopback-only encrypted SSH tunnel.
[group: 'usenet']
usenet-filex-ui:
	just --justfile usenet-infra/Justfile --working-directory usenet-infra filex-ui

[group: 'network']
[positional-arguments]
dns-check *args:
    @just --justfile usenet-infra/Justfile --working-directory usenet-infra dns check "$@"

# Discover Bonjour hostnames; preview by default, --apply deploys to both resolvers.
[group: 'network']
[positional-arguments]
dns-discover *args:
    @just --justfile usenet-infra/Justfile --working-directory usenet-infra dns discover "$@"

[group: 'network']
dns-auto-deploy:
    @just --justfile usenet-infra/Justfile --working-directory usenet-infra dns auto-deploy

[group: 'network']
dns-auto-status:
    @just --justfile usenet-infra/Justfile --working-directory usenet-infra dns auto-status

[group: 'network']
dns-auto-stop:
    @just --justfile usenet-infra/Justfile --working-directory usenet-infra dns auto-stop

[group: 'network']
dns-test:
    @UV_CACHE_DIR="$PWD/build/wiki/uv-cache" UV_PROJECT_ENVIRONMENT="$PWD/build/wiki/venv" uv run --project wiki --python "$(cat .python-version)" --frozen python -m unittest discover -s network-infra/dns -v

[group: 'network']
unifi-mcp:
    @./network-infra/unifi-mcp/run.sh

# Check the same credential lookup and pinned package import without a gateway read.
[group: 'network']
unifi-mcp-check:
    @./network-infra/unifi-mcp/run.sh --check

[group: 'network']
dns-deploy:
	@just --justfile usenet-infra/Justfile --working-directory usenet-infra dns deploy

[group: 'network']
[positional-arguments]
dns-rollback-primary snapshot:
	@just --justfile usenet-infra/Justfile --working-directory usenet-infra dns rollback-primary --snapshot "$1"
