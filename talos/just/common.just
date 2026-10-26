# Common Justfile library for smarthome project
# Provides shared variables and helper functions for all addon Justfiles

# ============================================================================
# SETTINGS
# ============================================================================

# Use bash for better error handling and cross-platform compatibility
set shell := ["bash", "-lc"]

# Allow positional arguments for flexibility
set positional-arguments := true

# ============================================================================
# VARIABLES
# ============================================================================

# Workspace root comes from this shared file, including inside nested repositories.
repo_root := clean(source_directory() / "../..")

# Talos binary path
talos_bin := repo_root + "/talos/build/bin/talos"

# Build directory
build_dir := repo_root + "/build"

# Home Assistant connection settings
ha_host := env_var_or_default("HA_HOST", "homeassistant.local")
ha_port := env_var_or_default("HA_PORT", "22")
ha_user := env_var_or_default("HA_USER", "root")

# ============================================================================
# HELPER FUNCTIONS (Private recipes for use by addon Justfiles)
# ============================================================================

# Check if talos binary exists and build if needed
[private]
ensure-talos:
    @if [ ! -x "{{talos_bin}}" ]; then \
        echo "🔨 Building talos..."; \
        {{repo_root}}/talos/build.sh; \
    fi

# Get the current addon name from directory
[private]
addon-name:
    @basename "$(pwd)"

# Validate addon directory structure
[private]
validate-addon:
    @if [ ! -f "config.yaml" ] && [ ! -f "addon.yaml" ]; then \
        echo "❌ Error: config.yaml or addon.yaml not found. Are you in an addon directory?"; \
        exit 1; \
    fi

# Show addon information
[private]
show-addon-info:
    @echo "📦 Addon: $(just addon-name)"
    @echo "📁 Directory: $(pwd)"
    @echo "🏠 HA Host: {{ha_host}}:{{ha_port}}"
    @echo "🔧 Talos: {{talos_bin}}"
    @if [ -f "config.yaml" ]; then \
        echo "📋 Config:"; \
        grep -E "^(name|version|description):" config.yaml | sed 's/^/  /'; \
    elif [ -f "addon.yaml" ]; then \
        echo "📋 Config:"; \
        grep -E "^(name|version|description):" addon.yaml | sed 's/^/  /'; \
    fi
