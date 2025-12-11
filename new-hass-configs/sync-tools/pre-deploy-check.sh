#!/usr/bin/env bash
# Pre-deployment protection check
# Prevents accidental overwrites of UI-modified configurations

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
FORCE_DEPLOY="${FORCE_DEPLOY:-false}"
BACKUP_BEFORE_DEPLOY="${BACKUP_BEFORE_DEPLOY:-false}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

log() {
    echo -e "${BLUE}[PRE-DEPLOY]${NC} $*" >&2
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
    echo -e "${CYAN}[INFO]${NC} $*" >&2
}

# Function to run change detection
run_change_detection() {
    log "Running change detection before deployment..."
    
    local detect_script="${SCRIPT_DIR}/detect-changes.sh"
    local changes_output
    
    if ! changes_output=$("$detect_script" 2>&1); then
        # Changes detected
        return 1
    else
        # No changes detected
        return 0
    fi
}

# Function to handle detected changes
handle_detected_changes() {
    error "🚨 DEPLOYMENT BLOCKED: Configuration drift detected!"
    error ""
    error "The live Home Assistant system has configuration changes that differ"
    error "from this repository. Proceeding would overwrite these changes."
    error ""
    
    # Run detection again to show details
    "${SCRIPT_DIR}/detect-changes.sh" || true
    
    echo
    error "=========================================="
    error "RESOLUTION OPTIONS:"
    error "=========================================="
    error ""
    error "1. FETCH LIVE CHANGES FIRST (Recommended)"
    error "   just fetch-config"
    error "   # Review and commit the changes"
    error "   git add . && git commit -m 'Sync live HA changes'"
    error "   just deploy"
    error ""
    error "2. FORCE DEPLOY (⚠️  Will lose live changes)"
    error "   FORCE_DEPLOY=true just deploy"
    error ""
    error "3. BACKUP AND DEPLOY"
    error "   BACKUP_BEFORE_DEPLOY=true just deploy"
    error ""
    error "4. MANUAL RECONCILIATION"
    error "   just reconcile scenes.yaml"
    error "   just reconcile automations.yaml"
    error ""
    
    return 1
}

# Function to create backup if requested
create_backup_if_requested() {
    if [[ "$BACKUP_BEFORE_DEPLOY" == "true" ]]; then
        log "Creating backup before forced deployment..."
        cd "$CONFIG_DIR"
        just backup "Pre-deploy backup (forced deployment)" >/dev/null 2>&1
        success "Backup created before deployment"
    fi
}

# Function to show deployment summary
show_deployment_summary() {
    info "=========================================="
    info "DEPLOYMENT SUMMARY"
    info "=========================================="
    info ""
    info "Repository: $(cd "$CONFIG_DIR/.." && pwd)"
    info "Target: Home Assistant at homeassistant.local"
    info "Force mode: $FORCE_DEPLOY"
    info "Backup mode: $BACKUP_BEFORE_DEPLOY"
    info ""
    
    # Show what will be deployed
    info "Files to be deployed:"
    for file in scenes.yaml scripts.yaml configuration.yaml; do
        if [[ -f "${CONFIG_DIR}/${file}" ]]; then
            local size=$(wc -l < "${CONFIG_DIR}/${file}")
            info "  ✓ $file ($size lines)"
        fi
    done

    # Show automation files (multiple blocks)
    if [[ -f "${CONFIG_DIR}/automations.yaml" ]]; then
        local size=$(wc -l < "${CONFIG_DIR}/automations.yaml")
        info "  ✓ automations.yaml (UI automations, $size lines)"
    fi
    if [[ -f "${CONFIG_DIR}/manual/automations.yaml" ]]; then
        local size=$(wc -l < "${CONFIG_DIR}/manual/automations.yaml")
        info "  ✓ manual/automations.yaml (manual automations, $size lines)"
    fi
    if [[ -f "${CONFIG_DIR}/generated/automations.yaml" ]]; then
        local size=$(wc -l < "${CONFIG_DIR}/generated/automations.yaml")
        info "  ✓ generated/automations.yaml (generated automations, $size lines)"
    fi
    info ""
}

# Main pre-deployment check
main() {
    log "Starting pre-deployment protection check..."
    
    # Show deployment summary
    show_deployment_summary
    
    # Skip checks if force mode is enabled
    if [[ "$FORCE_DEPLOY" == "true" ]]; then
        warn "Force deployment mode enabled - skipping change detection"
        create_backup_if_requested
        success "Pre-deployment check completed (forced)"
        return 0
    fi
    
    # Run change detection
    if ! run_change_detection; then
        handle_detected_changes
        return 1
    fi
    
    # Create backup if requested
    create_backup_if_requested
    
    success "Pre-deployment check passed - no conflicts detected"
    return 0
}

# Run main function
main "$@"
