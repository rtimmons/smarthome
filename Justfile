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
	# Check Python version
	required_python=$(tr -d '[:space:]' < .python-version)
	if ! pyenv versions --bare | grep -q "^${required_python}$"; then
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
deploy addon="all" *args="":
	@just deploy-preflight >/dev/null 2>&1
	@if [ ! -x "{{talos_bin}}" ]; then ./talos/build.sh >/dev/null 2>&1; fi
	@just talos-deploy normal "{{addon}}" {{args}}
	@echo "✅ Deployment completed successfully!"

# Deploy with verbose output for troubleshooting
[group: 'deploy']
deploy-verbose addon="all" *args="":
	@just deploy-preflight >/dev/null 2>&1
	@if [ ! -x "{{talos_bin}}" ]; then ./talos/build.sh >/dev/null 2>&1; fi
	@just talos-deploy verbose "{{addon}}" {{args}}
	@echo "✅ Deployment completed successfully!"

# Dry run deployment to see what would be deployed
[group: 'deploy']
deploy-dry-run addon="all":
	@just deploy-preflight >/dev/null 2>&1
	@if [ ! -x "{{talos_bin}}" ]; then ./talos/build.sh >/dev/null 2>&1; fi
	@echo "🔍 Dry run deployment preview..."
	@just talos-deploy dry-run "{{addon}}"
	@echo "📋 This was a dry run - no changes were made"

# Detailed dry run with verbose output for troubleshooting
[group: 'deploy']
deploy-dry-run-verbose addon="all":
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
test addon="all":
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

# Check repository-wide recovery inventory metadata without reading secrets.
[group: 'backup']
[positional-arguments]
secrets-check *args:
	#!/usr/bin/env bash
	set -euo pipefail
	exec python3 usenet-infra/scripts/secrets-check.py "$@"

# Cache reviewed recovery tools; does not create a recovery identity or vault.
[group: 'backup']
usenet-crypto-bootstrap:
	@just --justfile usenet-infra/Justfile --working-directory usenet-infra crypto-bootstrap

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

# Run local validation for the Usenet infrastructure project
[group: 'usenet']
usenet-test:
	@just --justfile usenet-infra/Justfile --working-directory usenet-infra test

# Securely store a Hetzner API token without putting it in chat or shell history
[group: 'usenet']
usenet-store-hcloud-token:
	@just --justfile usenet-infra/Justfile --working-directory usenet-infra store-hcloud-token

# Create or validate the purpose-specific Usenet infrastructure SSH keys
[group: 'usenet']
usenet-generate-ssh-keys:
	@just --justfile usenet-infra/Justfile --working-directory usenet-infra generate-ssh-keys

# Generate ignored Terraform inputs using the dedicated keys and current public IP
[group: 'usenet']
usenet-prepare-terraform-vars:
	@just --justfile usenet-infra/Justfile --working-directory usenet-infra prepare-terraform-vars

# Produce read-only Terraform plans for cloud and canonical storage
[group: 'usenet']
usenet-terraform-plan:
	@just --justfile usenet-infra/Justfile --working-directory usenet-infra terraform-plan

# Configure or converge the Usenet cloud host
[group: 'usenet']
usenet-configure-cloud:
	@just --justfile usenet-infra/Justfile --working-directory usenet-infra configure-cloud

# Configure the private UniFi-to-cloud UI connection.
[group: 'usenet']
usenet-configure-cloud-lan-ui:
	@just --justfile usenet-infra/Justfile --working-directory usenet-infra configure-cloud-lan-ui

# Reconnoiter, configure, and converge the QNAP after its dedicated SSH account is ready
[group: 'usenet']
usenet-configure-qnap:
	@just --justfile usenet-infra/Justfile --working-directory usenet-infra configure-qnap

# Verify the NAS reader cannot alter a disposable remote test file.
[group: 'usenet']
usenet-verify-reader-access:
	@just --justfile usenet-infra/Justfile --working-directory usenet-infra verify-reader-access

# Check cloud applications, Storage Box access, failures, and scratch space
[group: 'usenet']
usenet-cloud-health:
	@just --justfile usenet-infra/Justfile --working-directory usenet-infra cloud-health

# Read NAS versions, resource headroom, and share metadata through dedicated SSH.
[group: 'usenet']
usenet-qnap-recon:
	@just --justfile usenet-infra/Justfile --working-directory usenet-infra qnap-recon

# Open private SABnzbd and Prowlarr access through the dedicated SSH identity.
[group: 'usenet']
usenet-cloud-ui:
	@just --justfile usenet-infra/Justfile --working-directory usenet-infra cloud-ui

# Inspect, prepare, enable, or test NZBGeek without returning its saved API key.
[group: 'usenet']
[positional-arguments]
usenet-prowlarr-indexer command='inspect' indexer='nzbgeek':
	#!/usr/bin/env bash
	set -euo pipefail
	exec just --justfile usenet-infra/Justfile --working-directory usenet-infra prowlarr-indexer "$1" "$2"

# Inspect, configure, or test Prowlarr's internal SABnzbd connection.
[group: 'usenet']
[positional-arguments]
usenet-prowlarr-download-client command='inspect':
	#!/usr/bin/env bash
	set -euo pipefail
	exec just --justfile usenet-infra/Justfile --working-directory usenet-infra prowlarr-download-client "$1"

# Inspect, configure, or test Eweka using only saved credentials on the cloud host.
[group: 'usenet']
[positional-arguments]
usenet-sab-provider command='inspect':
	#!/usr/bin/env bash
	set -euo pipefail
	exec just --justfile usenet-infra/Justfile --working-directory usenet-infra sab-provider "$1"

# Inspect or apply conservative SAB storage and processing settings while idle.
[group: 'usenet']
[positional-arguments]
usenet-sab-settings command='inspect':
	#!/usr/bin/env bash
	set -euo pipefail
	exec just --justfile usenet-infra/Justfile --working-directory usenet-infra sab-settings "$1"

# Start once, or inspect, the official authorized 100 MB SAB download test.
[group: 'usenet']
[positional-arguments]
usenet-sab-smoke-test command='status':
	#!/usr/bin/env bash
	set -euo pipefail
	exec just --justfile usenet-infra/Justfile --working-directory usenet-infra sab-smoke-test "$1"

# Encrypt cloud application configuration and verify its off-VM backup.
[group: 'usenet']
usenet-backup-cloud:
	@just --justfile usenet-infra/Justfile --working-directory usenet-infra backup-cloud

# Back up the root-owned VPN and private cloud UI settings.
[group: 'usenet']
usenet-backup-vpn:
	@just --justfile usenet-infra/Justfile --working-directory usenet-infra backup-vpn

[group: 'usenet']
[positional-arguments]
usenet-backup-vpn-verify archive:
	#!/usr/bin/env bash
	set -euo pipefail
	exec just --justfile usenet-infra/Justfile --working-directory usenet-infra backup-vpn-verify "$1"

# Encrypt the NAS dashboard, catalog state, and private configuration.
[group: 'usenet']
usenet-backup-qnap:
	@just --justfile usenet-infra/Justfile --working-directory usenet-infra backup-qnap

[group: 'usenet']
[positional-arguments]
usenet-backup-qnap-verify archive:
	#!/usr/bin/env bash
	set -euo pipefail
	exec just --justfile usenet-infra/Justfile --working-directory usenet-infra backup-qnap-verify "$1"

[group: 'usenet']
[positional-arguments]
usenet-backup-qnap-restore archive destination:
	#!/usr/bin/env bash
	set -euo pipefail
	exec just --justfile usenet-infra/Justfile --working-directory usenet-infra backup-qnap-restore "$1" "$2"

# Decrypt and validate a backup without retaining plaintext.
[group: 'usenet']
[positional-arguments]
usenet-backup-verify archive:
	#!/usr/bin/env bash
	set -euo pipefail
	exec just --justfile usenet-infra/Justfile --working-directory usenet-infra backup-verify "$1"

# Restore verified configuration into a new private directory for recovery.
[group: 'usenet']
[positional-arguments]
usenet-backup-restore archive destination:
	#!/usr/bin/env bash
	set -euo pipefail
	exec just --justfile usenet-infra/Justfile --working-directory usenet-infra backup-restore "$1" "$2"

# Check Storage Box access, transfer failures, and QNAP cache capacity
[group: 'usenet']
usenet-qnap-health:
	@just --justfile usenet-infra/Justfile --working-directory usenet-infra qnap-health

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
