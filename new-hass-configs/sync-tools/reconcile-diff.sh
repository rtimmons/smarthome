#!/usr/bin/env bash
# Diff reconciliation tool for Home Assistant configuration conflicts
# Provides intelligent merging using auggie CLI or fallback diff mechanisms

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
TEMP_DIR="/tmp/ha-reconcile-$$"
REMOTE_HOST="root@homeassistant.local"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
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
    echo -e "${CYAN}[INFO]${NC} $*" >&2
}

cleanup() {
    rm -rf "${TEMP_DIR}"
}
trap cleanup EXIT

# Create temp directory
mkdir -p "${TEMP_DIR}"

# Function to show diff with context
show_diff() {
    local repo_file="$1"
    local live_file="$2"
    local file_type="$3"
    
    echo
    echo "=========================================="
    echo "CONFLICT DETECTED: $file_type"
    echo "=========================================="
    echo
    echo "Repository version: $repo_file"
    echo "Live system version: $live_file"
    echo
    
    # Try auggie first for intelligent diff
    if command -v auggie >/dev/null 2>&1; then
        info "Using auggie for intelligent diff analysis..."
        echo "--- AUGGIE ANALYSIS ---"
        auggie diff "$repo_file" "$live_file" || {
            warn "Auggie analysis failed, falling back to standard diff"
            show_standard_diff "$repo_file" "$live_file"
        }
    else
        warn "auggie CLI not available, using standard diff"
        show_standard_diff "$repo_file" "$live_file"
    fi
}

# Function to show standard diff with helpful context
show_standard_diff() {
    local repo_file="$1"
    local live_file="$2"
    
    echo "--- STANDARD DIFF (Repository <- -> Live System) ---"
    
    # Show side-by-side diff if available
    if command -v diff >/dev/null 2>&1; then
        diff -u "$repo_file" "$live_file" | head -50 || true
        echo
        echo "--- SUMMARY ---"
        
        # Count additions and deletions
        local additions=$(diff -u "$repo_file" "$live_file" | grep -c "^+" || echo "0")
        local deletions=$(diff -u "$repo_file" "$live_file" | grep -c "^-" || echo "0")
        
        echo "Lines added in live system: $additions"
        echo "Lines removed from live system: $deletions"
        
        # Try to identify what changed
        echo
        echo "--- CHANGE ANALYSIS ---"
        if grep -q "id:" "$live_file" 2>/dev/null; then
            echo "Detected scene/automation IDs in live system:"
            grep "id:" "$live_file" | head -5 | sed 's/^/  /'
        fi
        
        if grep -q "alias:" "$live_file" 2>/dev/null; then
            echo "Detected automation aliases in live system:"
            grep "alias:" "$live_file" | head -5 | sed 's/^/  /'
        fi
        
        if grep -q "name:" "$live_file" 2>/dev/null; then
            echo "Detected scene names in live system:"
            grep "name:" "$live_file" | head -5 | sed 's/^/  /'
        fi
    fi
}

# Function to provide resolution options
show_resolution_options() {
    local repo_file="$1"
    local live_file="$2"
    local file_type="$3"
    
    echo
    echo "=========================================="
    echo "RESOLUTION OPTIONS"
    echo "=========================================="
    echo
    echo "1. ACCEPT REPOSITORY VERSION (default for 'just deploy')"
    echo "   - Overwrites live system with repository version"
    echo "   - ⚠️  WILL LOSE any UI-created changes"
    echo "   - Use: just deploy --force"
    echo
    echo "2. KEEP LIVE SYSTEM CHANGES"
    echo "   - Fetches live system changes into repository"
    echo "   - Preserves UI-created content"
    echo "   - Use: just fetch-config"
    echo
    echo "3. MANUAL MERGE"
    echo "   - Opens files for manual editing"
    echo "   - Allows selective integration of changes"
    echo "   - Use: just reconcile-manual $file_type"
    echo
    echo "4. BACKUP AND PROCEED"
    echo "   - Creates backup of live system first"
    echo "   - Then proceeds with repository deployment"
    echo "   - Use: just deploy --backup"
    echo
}

# Function to suggest intelligent merge using auggie
suggest_auggie_merge() {
    local repo_file="$1"
    local live_file="$2"
    local file_type="$3"
    
    if command -v auggie >/dev/null 2>&1; then
        echo
        echo "=========================================="
        echo "INTELLIGENT MERGE SUGGESTION (via auggie)"
        echo "=========================================="
        echo
        
        # Try auggie merge suggestion
        info "Analyzing merge possibilities with auggie..."
        
        local merge_output="${TEMP_DIR}/auggie_merge_${file_type}"
        if auggie merge "$repo_file" "$live_file" > "$merge_output" 2>/dev/null; then
            success "Auggie suggests the following merge:"
            echo "--- SUGGESTED MERGE ---"
            head -30 "$merge_output"
            echo
            echo "Full merge saved to: $merge_output"
            echo "To apply: cp '$merge_output' '$repo_file'"
        else
            warn "Auggie could not automatically merge these files"
            echo "Manual intervention required"
        fi
    fi
}

# Main reconciliation function
reconcile_file() {
    local repo_file="$1"
    local live_file="$2"
    local file_type="$3"
    
    log "Reconciling $file_type..."

    # Fetch the live file (handle different paths for automation files)
    if [[ "$file_type" == "manual/automations.yaml" ]]; then
        scp "${REMOTE_HOST}:/config/manual/automations.yaml" "$live_file"
    elif [[ "$file_type" == "generated/automations.yaml" ]]; then
        scp "${REMOTE_HOST}:/config/generated/automations.yaml" "$live_file"
    else
        scp "${REMOTE_HOST}:/config/${file_type}" "$live_file"
    fi
    
    # Show the diff
    show_diff "$repo_file" "$live_file" "$file_type"
    
    # Show resolution options
    show_resolution_options "$repo_file" "$live_file" "$file_type"
    
    # Suggest intelligent merge if possible
    suggest_auggie_merge "$repo_file" "$live_file" "$file_type"
}

# Main function
main() {
    local file_type="${1:-}"
    
    if [[ -z "$file_type" ]]; then
        error "Usage: $0 <file_type>"
        error "Examples:"
        error "  $0 scenes.yaml"
        error "  $0 automations.yaml (UI automations)"
        error "  $0 manual/automations.yaml"
        error "  $0 generated/automations.yaml"
        exit 1
    fi
    
    local repo_file="${CONFIG_DIR}/${file_type}"
    local live_file="${TEMP_DIR}/${file_type}"
    
    if [[ ! -f "$repo_file" ]]; then
        error "Repository file not found: $repo_file"
        exit 1
    fi
    
    reconcile_file "$repo_file" "$live_file" "$file_type"
}

# Run main function
main "$@"
