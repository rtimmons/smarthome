# [ADDON_NAME] Addon Justfile
# [ADDON_DESCRIPTION]

# Import shared libraries
import "./common.just"
# import "../talos/just/nvm.just"     # For Node.js addons
# import "../talos/just/python.just"  # For Python addons (careful of conflicts)

# ============================================================================
# ADDON-SPECIFIC VARIABLES
# ============================================================================

# Add addon-specific variables here
# example_var := "value"

# ============================================================================
# ADDON-SPECIFIC RECIPES
# ============================================================================

# Set up the addon development environment
[group: 'setup']
setup:
    @echo "🔧 Setting up [ADDON_NAME]..."
    # Add setup logic here
    @echo "✅ [ADDON_NAME] setup complete"

# Run tests
[group: 'test']
test:
    @echo "🧪 Running [ADDON_NAME] tests..."
    # Add test logic here
    @echo "✅ Tests passed"

# Run development server
[group: 'dev']
dev: setup
    @echo "🚀 Starting [ADDON_NAME] development server..."
    # Add dev server logic here

# Generate diagnostic report (if applicable)
[group: 'debug']
report:
    @echo "📊 Generating [ADDON_NAME] diagnostic report..."
    # Add report generation logic here
    @echo "✅ Report generated"

# ============================================================================
# COMMON ADDON RECIPES (using shared functions)
# ============================================================================

# Build addon using talos
[group: 'build']
ha-addon: ensure-talos validate-addon
    @{{talos_bin}} addon build $(just addon-name)

# Deploy addon using talos
[group: 'deploy']
deploy: ensure-talos validate-addon
    @{{talos_bin}} addon deploy $(just addon-name)

# Deploy addon with verbose output
[group: 'deploy']
deploy-verbose: ensure-talos validate-addon
    @{{talos_bin}} addon deploy $(just addon-name) --verbose

# Deploy addon in dry-run mode
[group: 'deploy']
deploy-dry-run: ensure-talos validate-addon
    @{{talos_bin}} addon deploy $(just addon-name) --dry-run

# Test addon container build
[group: 'test']
container-test: ensure-talos validate-addon
    @echo "==> Container test: $(just addon-name) uses Home Assistant's container build system"
    @echo "==> Verifying add-on build completes successfully..."
    @{{talos_bin}} addon build $(just addon-name)
    @echo "==> Add-on build test passed - ready for deployment"

# Show addon information
[group: 'info']
info: validate-addon show-addon-info

# Clean build artifacts
[group: 'clean']
clean:
    @echo "🧹 Cleaning build artifacts for $(just addon-name)..."
    @rm -rf "{{build_dir}}/home-assistant-addon/$(just addon-name | tr '-' '_')"
    @echo "✅ Clean complete"

# ============================================================================
# ALIASES (optional)
# ============================================================================

# Add common aliases
alias d := deploy
alias t := test
alias s := setup
