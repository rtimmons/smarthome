#!/usr/bin/env bash
# Bidirectional sync change detection for Home Assistant configurations
# Detects when scenes/automations have been modified in the live HA system

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_DIR="${SYNC_CONFIG_DIR:-$(cd "${SCRIPT_DIR}/.." && pwd)}"
source "${SCRIPT_DIR}/ha-ssh.sh"
TEMP_DIR="${SYNC_TEMP_DIR:-/tmp/ha-sync-$$}"
LIVE_CONFIG_DIR="${SYNC_LIVE_CONFIG_DIR:-}"
REMOTE_HOST="root@homeassistant.local"
REMOTE_CONFIG="/config"
SHOW_DIFFS="${SHOW_DIFFS:-true}"
DIFF_CONTEXT="${DIFF_CONTEXT:-3}"
DIFF_MAX_LINES="${DIFF_MAX_LINES:-120}"

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

info() {
    echo -e "${BLUE}[INFO]${NC} $*" >&2
}

cleanup() {
    rm -rf "${TEMP_DIR}"
}
trap cleanup EXIT

# Create temp directory
mkdir -p "${TEMP_DIR}"

# Function to fetch live config files
fetch_live_configs() {
    if [[ -n "$LIVE_CONFIG_DIR" ]]; then
        log "Reading live configuration fixture from ${LIVE_CONFIG_DIR}..."
        mkdir -p "${TEMP_DIR}/live"
        cp -R "${LIVE_CONFIG_DIR}/." "${TEMP_DIR}/live/"
        return 0
    fi

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
        -e "${HA_RSYNC_SHELL}" \
        "${REMOTE_HOST}:${REMOTE_CONFIG}/" "${TEMP_DIR}/live/"
    
    # Also fetch any UI-created configs if they exist
    ssh "${HA_SSH_ARGS[@]}" "${REMOTE_HOST}" "find ${REMOTE_CONFIG} -name '*.yaml' -path '*/ui_*' 2>/dev/null || true" | \
    while read -r file; do
        if [[ -n "$file" ]]; then
            rel_path="${file#"${REMOTE_CONFIG}"/}"
            mkdir -p "${TEMP_DIR}/live/$(dirname "$rel_path")"
            scp "${HA_SCP_ARGS[@]}" "${REMOTE_HOST}:${file}" "${TEMP_DIR}/live/${rel_path}"
        fi
    done
}

files_match() {
    local first_file="$1"
    local second_file="$2"
    local first_checksum
    local second_checksum

    first_checksum=$(sed 's/[[:space:]]//g' "$first_file" | sha256sum | cut -d' ' -f1)
    second_checksum=$(sed 's/[[:space:]]//g' "$second_file" | sha256sum | cut -d' ' -f1)
    [[ "$first_checksum" == "$second_checksum" ]]
}

# Function to print an actionable repo-to-live diff for a changed file
print_file_diff() {
    local repo_file="$1"
    local live_file="$2"
    local file_type="$3"

    if [[ "$SHOW_DIFFS" != "true" ]]; then
        return 0
    fi

    local diff_output
    local rel_file="${repo_file#"${CONFIG_DIR}"/}"
    diff_output=$(diff -u -U "$DIFF_CONTEXT" \
        --label "repository/${rel_file}" \
        --label "live-homeassistant/${rel_file}" \
        "$repo_file" "$live_file" || true)

    if [[ -z "$diff_output" ]]; then
        return 0
    fi

    local total_lines
    total_lines=$(printf '%s\n' "$diff_output" | wc -l | tr -d ' ')

    warn "Diff for $file_type (repository -> live Home Assistant):"
    printf '%s\n' "$diff_output" | sed -n "1,${DIFF_MAX_LINES}p" >&2

    if [[ "$total_lines" -gt "$DIFF_MAX_LINES" ]]; then
        info "Diff truncated after ${DIFF_MAX_LINES}/${total_lines} lines."
        info "Run: just reconcile ${rel_file}"
    fi
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
    
    if ! files_match "$repo_file" "$live_file"; then
        warn "Detected changes in $file_type: $(basename "$repo_file")"
        print_file_diff "$repo_file" "$live_file" "$file_type"
        echo "CHANGED:$file_type:$repo_file:$live_file"
        return 1
    fi
    
    return 0
}

# Repository-owned files are expected to differ before a deployment. Treating
# those differences as live drift makes every legitimate repository change
# require FORCE_DEPLOY, defeating the pre-deploy guard. UI-owned files are
# still checked strictly with compare_files above.
compare_repo_owned_file() {
    local repo_file="$1"
    local live_file="$2"
    local file_type="$3"

    if [[ ! -f "$repo_file" ]]; then
        warn "Repository-owned file missing: $repo_file"
        return 1
    fi

    if [[ ! -f "$live_file" ]]; then
        info "Pending deployment: $file_type is not present on Home Assistant"
        return 0
    fi

    if ! files_match "$repo_file" "$live_file"; then
        info "Pending deployment: repository-owned $file_type differs from Home Assistant"
    fi

    return 0
}

numeric_ids() {
    local file="$1"

    if [[ ! -f "$file" ]]; then
        return 0
    fi

    sed -nE "s/^[[:space:]-]*id:[[:space:]]*['\"]?([0-9]{10,})['\"]?[[:space:]]*$/\1/p" "$file" | sort -u
}

detect_new_ui_ids() {
    local repo_file="$1"
    local live_file="$2"
    local file_type="$3"
    local repo_ids="${TEMP_DIR}/repo-ids-$$"
    local live_ids="${TEMP_DIR}/live-ids-$$"
    local new_ids

    numeric_ids "$repo_file" > "$repo_ids"
    numeric_ids "$live_file" > "$live_ids"
    new_ids=$(comm -13 "$repo_ids" "$live_ids")

    if [[ -n "$new_ids" ]]; then
        warn "Detected new UI-created IDs in $file_type: $(printf '%s' "$new_ids" | paste -sd, -)"
        echo "UI_CREATED:$file_type:$live_file"
        return 1
    fi

    return 0
}

# Function to detect UI-created content
detect_ui_created() {
    log "Checking for UI-created scenes and automations..."

    local ui_changes_detected=false

    if ! detect_new_ui_ids "${CONFIG_DIR}/scenes.yaml" "${TEMP_DIR}/live/scenes.yaml" "scenes"; then
        ui_changes_detected=true
    fi
    if ! detect_new_ui_ids "${CONFIG_DIR}/automations.yaml" "${TEMP_DIR}/live/automations.yaml" "automations"; then
        ui_changes_detected=true
    fi
    if ! detect_new_ui_ids "${CONFIG_DIR}/manual/automations.yaml" "${TEMP_DIR}/live/manual/automations.yaml" "manual_automations"; then
        ui_changes_detected=true
    fi

    [[ "$ui_changes_detected" == "false" ]]
}

# Main detection logic
main() {
    log "Starting change detection..."
    
    # Fetch live configs
    fetch_live_configs
    
    local changes_detected=false
    
    # Repository-owned generated/merged files are deployment inputs. A local
    # difference is pending work to deploy, not evidence of a live UI edit.
    for config_file in scenes.yaml scripts.yaml; do
        repo_file="${CONFIG_DIR}/${config_file}"
        live_file="${TEMP_DIR}/live/${config_file}"

        if ! compare_repo_owned_file "$repo_file" "$live_file" "$config_file"; then
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

    # 2. Manual automations are repository-owned.
    repo_file="${CONFIG_DIR}/manual/automations.yaml"
    live_file="${TEMP_DIR}/live/manual/automations.yaml"
    if ! compare_repo_owned_file "$repo_file" "$live_file" "manual/automations.yaml"; then
        changes_detected=true
    fi

    # 3. Generated automations are repository-owned deployment output.
    repo_file="${CONFIG_DIR}/generated/automations.yaml"
    live_file="${TEMP_DIR}/live/generated/automations.yaml"
    if ! compare_repo_owned_file "$repo_file" "$live_file" "generated/automations.yaml"; then
        changes_detected=true
    fi
    
    # Check for UI-created content
    if ! detect_ui_created; then
        changes_detected=true
    fi
    
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
