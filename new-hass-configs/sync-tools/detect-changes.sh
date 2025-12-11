#!/usr/bin/env bash
# Bidirectional sync change detection for Home Assistant configurations
# Detects when scenes/automations have been modified in the live HA system

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
CONFIG_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
TEMP_DIR="/tmp/ha-sync-$$"
REMOTE_HOST="root@homeassistant.local"
REMOTE_CONFIG="/config"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log() {
    echo -e "${BLUE}[$(date '+%H:%M:%S')]${NC} $*" >&2
}

warn() {
    echo -e "${YELLOW}[WARNING]${NC} $*" >&2
}

error() {
    echo -e "${RED}[ERROR]${NC} $*" >&2
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $*" >&2
}

cleanup() {
    rm -rf "${TEMP_DIR}"
}
trap cleanup EXIT

# Create temp directory
mkdir -p "${TEMP_DIR}"

# Function to fetch live config files
fetch_live_configs() {
    log "Fetching live configuration files from ${REMOTE_HOST}..."
    
    # Fetch the main config files we care about
    rsync -av \
        --include='scenes.yaml' \
        --include='automations.yaml' \
        --include='scripts.yaml' \
        --include='configuration.yaml' \
        --include='manual/' \
        --include='manual/automations.yaml' \
        --include='generated/' \
        --include='generated/automations.yaml' \
        --exclude='*' \
        -e "ssh -p 22" \
        "${REMOTE_HOST}:${REMOTE_CONFIG}/" "${TEMP_DIR}/live/"
    
    # Also fetch any UI-created configs if they exist
    ssh -p 22 "${REMOTE_HOST}" "find ${REMOTE_CONFIG} -name '*.yaml' -path '*/ui_*' 2>/dev/null || true" | \
    while read -r file; do
        if [[ -n "$file" ]]; then
            rel_path="${file#${REMOTE_CONFIG}/}"
            mkdir -p "${TEMP_DIR}/live/$(dirname "$rel_path")"
            scp "${REMOTE_HOST}:${file}" "${TEMP_DIR}/live/${rel_path}"
        fi
    done
}

# Function to compare file checksums
compare_files() {
    local repo_file="$1"
    local live_file="$2"
    local file_type="$3"
    
    if [[ ! -f "$repo_file" ]]; then
        warn "Repository file missing: $repo_file"
        return 1
    fi
    
    if [[ ! -f "$live_file" ]]; then
        warn "Live file missing: $live_file"
        return 1
    fi
    
    # Calculate checksums (ignoring whitespace differences)
    repo_checksum=$(sed 's/[[:space:]]//g' "$repo_file" | sha256sum | cut -d' ' -f1)
    live_checksum=$(sed 's/[[:space:]]//g' "$live_file" | sha256sum | cut -d' ' -f1)
    
    if [[ "$repo_checksum" != "$live_checksum" ]]; then
        warn "Detected changes in $file_type: $(basename "$repo_file")"
        echo "CHANGED:$file_type:$repo_file:$live_file"
        return 1
    fi
    
    return 0
}

# Function to detect UI-created content
detect_ui_created() {
    log "Checking for UI-created scenes and automations..."
    
    # Check for scenes with UI-generated IDs (typically numeric)
    if [[ -f "${TEMP_DIR}/live/scenes.yaml" ]]; then
        if grep -q "id: [0-9]\{10,\}" "${TEMP_DIR}/live/scenes.yaml" 2>/dev/null; then
            warn "Detected UI-created scenes with numeric IDs"
            echo "UI_CREATED:scenes:${TEMP_DIR}/live/scenes.yaml"
        fi
    fi
    
    # Check for automations with UI-generated IDs in the UI automations file
    if [[ -f "${TEMP_DIR}/live/automations.yaml" ]]; then
        if grep -q "id: [0-9]\{10,\}" "${TEMP_DIR}/live/automations.yaml" 2>/dev/null; then
            warn "Detected UI-created automations with numeric IDs in automations.yaml"
            echo "UI_CREATED:automations:${TEMP_DIR}/live/automations.yaml"
        fi
    fi

    # Check for UI modifications to manual automations
    if [[ -f "${TEMP_DIR}/live/manual/automations.yaml" ]]; then
        if grep -q "id: [0-9]\{10,\}" "${TEMP_DIR}/live/manual/automations.yaml" 2>/dev/null; then
            warn "Detected UI-created automations with numeric IDs in manual/automations.yaml"
            echo "UI_CREATED:manual_automations:${TEMP_DIR}/live/manual/automations.yaml"
        fi
    fi
}

# Main detection logic
main() {
    log "Starting change detection..."
    
    # Fetch live configs
    fetch_live_configs
    
    local changes_detected=false
    
    # Compare main configuration files
    for config_file in scenes.yaml scripts.yaml; do
        repo_file="${CONFIG_DIR}/${config_file}"
        live_file="${TEMP_DIR}/live/${config_file}"

        if ! compare_files "$repo_file" "$live_file" "$config_file"; then
            changes_detected=true
        fi
    done

    # Compare automation files (multiple blocks structure)
    # 1. UI-created automations (root automations.yaml)
    repo_file="${CONFIG_DIR}/automations.yaml"
    live_file="${TEMP_DIR}/live/automations.yaml"
    if ! compare_files "$repo_file" "$live_file" "automations.yaml (UI)"; then
        changes_detected=true
    fi

    # 2. Manual automations (manual/automations.yaml)
    repo_file="${CONFIG_DIR}/manual/automations.yaml"
    live_file="${TEMP_DIR}/live/manual/automations.yaml"
    if ! compare_files "$repo_file" "$live_file" "manual/automations.yaml"; then
        changes_detected=true
    fi

    # 3. Generated automations (generated/automations.yaml) - read-only, should not change
    repo_file="${CONFIG_DIR}/generated/automations.yaml"
    live_file="${TEMP_DIR}/live/generated/automations.yaml"
    if [[ -f "$repo_file" && -f "$live_file" ]]; then
        if ! compare_files "$repo_file" "$live_file" "generated/automations.yaml"; then
            warn "Generated automations differ from live system - this should not happen!"
            changes_detected=true
        fi
    fi
    
    # Check for UI-created content
    detect_ui_created
    
    if [[ "$changes_detected" == "true" ]]; then
        error "Configuration drift detected! Live system differs from repository."
        return 1
    else
        success "No configuration drift detected."
        return 0
    fi
}

# Run main function
main "$@"
