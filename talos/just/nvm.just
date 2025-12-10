# NVM (Node Version Manager) library for smarthome project
# Provides Node.js version management functionality

# ============================================================================
# NVM VARIABLES
# ============================================================================

# NVM initialization command (uses repo_root from common.just if imported)
nvm_use := "source \"$(git rev-parse --show-toplevel 2>/dev/null || pwd)/talos/scripts/nvm_use.sh\""

# Node.js version file
nvmrc_file := `git rev-parse --show-toplevel 2>/dev/null || pwd` + "/.nvmrc"

# NVM directory
nvm_dir := `git rev-parse --show-toplevel 2>/dev/null || pwd` + "/build/nvm"

# ============================================================================
# NVM RECIPES
# ============================================================================

# Initialize NVM and use project Node.js version
[group: 'node']
nvm-init:
    @echo "🔧 Initializing NVM..."
    @{{nvm_use}}
    @echo "✅ NVM initialized"

# Show current Node.js version
[group: 'node']
node-version:
    @echo "📋 Node.js version information:"
    @{{nvm_use}} && node --version
    @{{nvm_use}} && npm --version

# Show available Node.js versions
[group: 'node']
node-versions:
    @echo "📋 Available Node.js versions:"
    @{{nvm_use}} && nvm list

# Install Node.js version from .nvmrc
[group: 'node']
node-install:
    @echo "📦 Installing Node.js version from .nvmrc..."
    @{{nvm_use}} && nvm install
    @echo "✅ Node.js installation complete"

# Update to latest LTS Node.js version
[group: 'node']
node-update-lts:
    @echo "⬆️  Updating to latest LTS Node.js..."
    @{{nvm_use}} && nvm install --lts
    @{{nvm_use}} && nvm use --lts
    @echo "✅ Updated to latest LTS Node.js"

# Clean NVM cache
[group: 'clean']
clean-nvm:
    @echo "🧹 Cleaning NVM cache..."
    @{{nvm_use}} && nvm cache clear
    @echo "✅ NVM cache cleaned"
