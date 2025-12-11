#!/usr/bin/env bash
# Fetch remote Home Assistant configuration and update local repository
# Includes git diff protection to prevent overwriting uncommitted changes

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
TEMP_DIR="/tmp/ha-fetch-config-$$"
REMOTE_HOST="root@homeassistant.local"
FORCE_FLAG="${FORCE_FLAG:-false}"

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

# Function to check git status
check_git_status() {
    log "Checking git status for uncommitted changes..."
    
    cd "$REPO_ROOT"
    
    # Check if we're in a git repository
    if ! git rev-parse --git-dir >/dev/null 2>&1; then
        warn "Not in a git repository, skipping git checks"
        return 0
    fi
    
    # Check for uncommitted changes in config files
    local config_files=(
        "new-hass-configs/scenes.yaml"
        "new-hass-configs/automations.yaml"
        "new-hass-configs/scripts.yaml"
        "new-hass-configs/configuration.yaml"
    )
    
    local has_changes=false
    for file in "${config_files[@]}"; do
        if [[ -f "$file" ]] && ! git diff --quiet "$file" 2>/dev/null; then
            warn "Uncommitted changes detected in: $file"
            has_changes=true
        fi
    done
    
    if [[ "$has_changes" == "true" && "$FORCE_FLAG" != "true" ]]; then
        error "Uncommitted changes detected in configuration files!"
        error "This operation would overwrite your local changes."
        error ""
        error "Options:"
        error "1. Commit your changes first: git add . && git commit -m 'Save local changes'"
        error "2. Use --force flag to proceed anyway: FORCE_FLAG=true $0"
        error "3. Stash your changes: git stash"
        exit 1
    fi
    
    if [[ "$has_changes" == "true" ]]; then
        warn "Proceeding with --force flag despite uncommitted changes"
    fi
}

# Function to create backup before fetch
create_backup() {
    log "Creating backup of current configuration..."
    
    local timestamp=$(date +"%Y%m%d-%H%M%S")
    local backup_dir="${CONFIG_DIR}/backups/pre-fetch-${timestamp}"
    
    mkdir -p "$backup_dir"
    
    # Backup current config files
    for file in scenes.yaml scripts.yaml configuration.yaml; do
        if [[ -f "${CONFIG_DIR}/${file}" ]]; then
            cp "${CONFIG_DIR}/${file}" "${backup_dir}/"
        fi
    done

    # Backup automation files (multiple blocks structure)
    if [[ -f "${CONFIG_DIR}/automations.yaml" ]]; then
        cp "${CONFIG_DIR}/automations.yaml" "${backup_dir}/"
    fi
    if [[ -f "${CONFIG_DIR}/manual/automations.yaml" ]]; then
        mkdir -p "${backup_dir}/manual"
        cp "${CONFIG_DIR}/manual/automations.yaml" "${backup_dir}/manual/"
    fi
    if [[ -f "${CONFIG_DIR}/generated/automations.yaml" ]]; then
        mkdir -p "${backup_dir}/generated"
        cp "${CONFIG_DIR}/generated/automations.yaml" "${backup_dir}/generated/"
    fi
    
    echo "pre-fetch-${timestamp}" > "${CONFIG_DIR}/.last-backup"
    success "Backup created: $backup_dir"
}

# Function to fetch live configuration
fetch_live_config() {
    log "Fetching live configuration from ${REMOTE_HOST}..."
    
    # Use the existing fetch logic from the Justfile but with modifications
    rsync -av \
        --delete \
        --filter='protect .storage/***' \
        --filter='protect .cloud/***' \
        --filter='protect .ssh/***' \
        --filter='protect ssh/***' \
        --filter='protect ssl/***' \
        --filter='protect addons/***' \
        --filter='protect addon_configs/***' \
        --filter='protect share/***' \
        --filter='protect media/***' \
        --filter='protect www/***' \
        --filter='protect custom_components/***' \
        --filter='protect deps/***' \
        --filter='protect tts/***' \
        --filter='protect esphome/***' \
        --prune-empty-dirs \
        --filter='protect config-generator/' \
        --filter='protect generated/' \
        --filter='protect manual/' \
        --filter='protect backups/' \
        --filter='protect sync-tools/' \
        --filter='protect .git/***' \
        --include '*/' \
        --include '*.yaml' \
        --include '*.yml' \
        --include '*.json' \
        --include '*.sh' \
        --exclude '.cloud/' \
        --exclude '.storage/' \
        --exclude 'deps/' \
        --exclude 'tts/' \
        --exclude 'secrets.yaml' \
        --exclude '*.db*' \
        --exclude '*.log' \
        --exclude '*.pickle' \
        --exclude '*.uuid' \
        --exclude '*~' \
        --exclude '*.pyc' \
        --exclude '__pycache__/' \
        --exclude '*' \
        -e "ssh -p 22" \
        "${REMOTE_HOST}:/config/" "${TEMP_DIR}/fetched/"
}

# Function to analyze what changed
analyze_changes() {
    log "Analyzing changes between live system and repository..."
    
    local changes_found=false
    
    # Check main configuration files
    for file in scenes.yaml scripts.yaml configuration.yaml; do
        local repo_file="${CONFIG_DIR}/${file}"
        local live_file="${TEMP_DIR}/fetched/${file}"

        if [[ -f "$live_file" ]]; then
            if [[ ! -f "$repo_file" ]] || ! cmp -s "$repo_file" "$live_file"; then
                warn "Changes detected in: $file"
                changes_found=true

                # Show brief summary of changes
                if [[ -f "$repo_file" ]]; then
                    local additions=$(diff -u "$repo_file" "$live_file" 2>/dev/null | grep -c "^+" || echo "0")
                    local deletions=$(diff -u "$repo_file" "$live_file" 2>/dev/null | grep -c "^-" || echo "0")
                    echo "  Lines added: $additions, Lines removed: $deletions"
                else
                    echo "  New file from live system"
                fi
            fi
        fi
    done

    # Check automation files (multiple blocks structure)
    # 1. UI-created automations (root automations.yaml)
    local repo_file="${CONFIG_DIR}/automations.yaml"
    local live_file="${TEMP_DIR}/fetched/automations.yaml"
    if [[ -f "$live_file" ]]; then
        if [[ ! -f "$repo_file" ]] || ! cmp -s "$repo_file" "$live_file"; then
            warn "Changes detected in: automations.yaml (UI automations)"
            changes_found=true

            if [[ -f "$repo_file" ]]; then
                local additions=$(diff -u "$repo_file" "$live_file" 2>/dev/null | grep -c "^+" || echo "0")
                local deletions=$(diff -u "$repo_file" "$live_file" 2>/dev/null | grep -c "^-" || echo "0")
                echo "  Lines added: $additions, Lines removed: $deletions"
            else
                echo "  New file from live system"
            fi
        fi
    fi

    # 2. Manual automations (manual/automations.yaml)
    repo_file="${CONFIG_DIR}/manual/automations.yaml"
    live_file="${TEMP_DIR}/fetched/manual/automations.yaml"
    if [[ -f "$live_file" ]]; then
        if [[ ! -f "$repo_file" ]] || ! cmp -s "$repo_file" "$live_file"; then
            warn "Changes detected in: manual/automations.yaml"
            changes_found=true

            if [[ -f "$repo_file" ]]; then
                local additions=$(diff -u "$repo_file" "$live_file" 2>/dev/null | grep -c "^+" || echo "0")
                local deletions=$(diff -u "$repo_file" "$live_file" 2>/dev/null | grep -c "^-" || echo "0")
                echo "  Lines added: $additions, Lines removed: $deletions"
            else
                echo "  New file from live system"
            fi
        fi
    fi
    
    if [[ "$changes_found" == "false" ]]; then
        success "No changes detected between live system and repository"
        return 1
    fi
    
    return 0
}

# Function to apply fetched changes - simple synchronization
apply_changes() {
    log "Synchronizing local files with live Home Assistant system..."

    # Copy main configuration files to local repository
    for file in scenes.yaml scripts.yaml configuration.yaml; do
        local live_file="${TEMP_DIR}/fetched/${file}"
        local repo_file="${CONFIG_DIR}/${file}"

        if [[ -f "$live_file" ]]; then
            cp "$live_file" "$repo_file"
            success "Synchronized: $file"
        fi
    done

    # Synchronize automation files (multiple blocks structure)
    # 1. UI-created automations (root automations.yaml)
    local live_file="${TEMP_DIR}/fetched/automations.yaml"
    local repo_file="${CONFIG_DIR}/automations.yaml"
    if [[ -f "$live_file" ]]; then
        cp "$live_file" "$repo_file"
        success "Synchronized: automations.yaml (UI automations)"
    fi

    # 2. Manual automations (manual/automations.yaml)
    live_file="${TEMP_DIR}/fetched/manual/automations.yaml"
    repo_file="${CONFIG_DIR}/manual/automations.yaml"
    if [[ -f "$live_file" ]]; then
        # Ensure manual directory exists
        mkdir -p "${CONFIG_DIR}/manual"
        cp "$live_file" "$repo_file"
        success "Synchronized: manual/automations.yaml"
    fi

    log "Synchronization complete - local files now match live system"
}

# Function to check for UI changes and update manual files
# Synchronize UI-created automations with the local automations.yaml file
sync_ui_automations() {
    log "🔄 Synchronizing UI-created automations..."

    # Fetch the live UI automations file directly
    local live_ui_automations="${TEMP_DIR}/fetched_ui_automations.yaml"
    local ui_automations="${CONFIG_DIR}/automations.yaml"

    # Fetch the live UI automations file
    if ! rsync -avz --timeout=30 "root@homeassistant.local:/config/automations.yaml" "$live_ui_automations" >/dev/null 2>&1; then
        warning "Could not fetch live UI automations - keeping existing UI automations"
        return 0
    fi

    # Simply copy the live UI automations file
    if ! cmp -s "$ui_automations" "$live_ui_automations"; then
        cp "$live_ui_automations" "$ui_automations"
        success "✅ Updated UI automations with changes from live system"
    else
        log "✅ No changes detected in UI automations"
    fi
}

# Update manual automations with UI changes
update_manual_automations() {
    log "🔄 Checking for UI changes to manual automations..."

    # Fetch the live manual automations file directly
    local live_manual_automations="${TEMP_DIR}/fetched_manual_automations.yaml"
    local manual_automations="${CONFIG_DIR}/manual/automations.yaml"

    # Fetch the live manual automations file
    if ! rsync -avz --timeout=30 "root@homeassistant.local:/config/manual/automations.yaml" "$live_manual_automations" >/dev/null 2>&1; then
        log "Could not fetch live manual automations - skipping updates"
        return 0
    fi

    if [[ ! -f "$manual_automations" ]]; then
        log "Local manual automations file not found - skipping updates"
        return 0
    fi

    # Check if the manual file has changed
    if ! cmp -s "$manual_automations" "$live_manual_automations"; then
        cp "$live_manual_automations" "$manual_automations"
        success "✅ Updated manual automations with UI changes"
        log "💡 UI changes will now show up in 'git diff' and be preserved in deployments"
    else
        log "✅ No UI changes detected in manual automations"
    fi
}



# Main function
main() {
    local force_flag="${1:-}"
    
    if [[ "$force_flag" == "--force" ]]; then
        FORCE_FLAG="true"
    fi
    
    log "Starting configuration fetch from live Home Assistant system..."
    
    # Check git status unless forced
    check_git_status
    
    # Create backup
    create_backup
    
    # Fetch live configuration
    fetch_live_config
    
    # Analyze changes
    if ! analyze_changes; then
        success "No changes detected between live system and repository"
        # Even if no changes, sync UI automations and update manual files
        sync_ui_automations
        update_manual_automations
        success "Configuration fetch completed successfully!"
        exit 0
    fi

    # Apply changes
    apply_changes

    # Synchronize UI automations and update manual files
    sync_ui_automations
    update_manual_automations

    success "Configuration fetch completed successfully!"
    success "Review changes with: git diff"
    success "Commit changes with: git add . && git commit -m 'Fetch live HA config changes'"
}

# Run main function
main "$@"
