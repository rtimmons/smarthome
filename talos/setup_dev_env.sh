#!/usr/bin/env bash
set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Keep npm installs quiet about audits/funding during setup runs
export NPM_CONFIG_AUDIT=false
export NPM_CONFIG_FUND=false
export NPM_CONFIG_LOGLEVEL=error
export NPM_CONFIG_PROGRESS=false

# Helper functions
info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

success() {
    echo -e "${GREEN}✓${NC} $1"
}

warn() {
    echo -e "${YELLOW}⚠${NC} $1"
}

error() {
    echo -e "${RED}✗${NC} $1"
}

brew_formula_installed() {
    local formula="$1"
    command -v brew >/dev/null 2>&1 && HOMEBREW_NO_AUTO_UPDATE=1 brew list --formula "$formula" >/dev/null 2>&1
}

print_brew_post_install_notes() {
    local formula="$1"
    if ! brew_formula_installed "$formula"; then
        return
    fi

    local parser=""
    if command -v python3 >/dev/null 2>&1; then
        parser="python3"
    elif command -v python >/dev/null 2>&1; then
        parser="python"
    fi

    local caveats=""
    if [ -n "$parser" ]; then
        caveats=$(HOMEBREW_NO_AUTO_UPDATE=1 brew info --json=v2 "$formula" 2>/dev/null | "$parser" - <<'PY'
import json
import sys

try:
    data = json.load(sys.stdin)
    formula = data.get("formulae", [{}])[0]
    caveats = formula.get("caveats", "").strip()
    if caveats:
        print(caveats)
except Exception:
    pass
PY
)
    fi

    if [ -n "$caveats" ]; then
        warn "Homebrew post-install notes for $formula:"
        echo "$caveats"
    else
        warn "Homebrew info for $formula:"
        HOMEBREW_NO_AUTO_UPDATE=1 brew info "$formula"
    fi
}

# Banner
echo ""
echo "╭────────────────────────────────────────────────────╮"
echo "│  🔧 Smart Home Development Environment Setup       │"
echo "╰────────────────────────────────────────────────────╯"
echo ""

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# Track if any errors occurred
ERRORS=0

# 1. Check and setup Homebrew dependencies
info "Checking system dependencies..."

if command -v brew &> /dev/null; then
    success "Homebrew is installed"

    # Check for cairo (needed by printer service)
    if brew list cairo &> /dev/null; then
        success "cairo is installed"
    else
        warn "cairo not found - installing via Homebrew..."
        if brew install cairo; then
            success "cairo installed successfully"
        else
            error "Failed to install cairo"
            ERRORS=$((ERRORS + 1))
        fi
    fi

    # Check for xz (needed for Python _lzma during pyenv builds)
    if brew list xz &> /dev/null; then
        success "xz is installed"
    else
        warn "xz not found - installing via Homebrew (needed for Python _lzma)..."
        if brew install xz; then
            success "xz installed successfully"
        else
            error "Failed to install xz"
            ERRORS=$((ERRORS + 1))
        fi
    fi
else
    warn "Homebrew not found. Please install from https://brew.sh"
    warn "Then run: brew install cairo xz"
    ERRORS=$((ERRORS + 1))
fi

echo ""

# 2. Check and setup nvm + Node.js
info "Checking Node.js version management..."

NVM_VERSION_FILE="$REPO_ROOT/.nvmrc"
NVM_USE_SCRIPT="$REPO_ROOT/talos/scripts/nvm_use.sh"
export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
mkdir -p "$NVM_DIR"
REQUIRED_NODE_VERSION="v20.18.2"
if [ -f "$NVM_VERSION_FILE" ]; then
    REQUIRED_NODE_VERSION=$(tr -d '[:space:]' < "$NVM_VERSION_FILE")
fi

if [ ! -f "$NVM_VERSION_FILE" ]; then
    error "Missing $NVM_VERSION_FILE; cannot select Node runtime."
    ERRORS=$((ERRORS + 1))
elif [ ! -x "$NVM_USE_SCRIPT" ]; then
    error "Missing helper script: $NVM_USE_SCRIPT"
    ERRORS=$((ERRORS + 1))
else
    NODE_SETUP_LOG=$(mktemp)
    nvm_attempt() {
        NVM_VERSION_FILE="$NVM_VERSION_FILE" NVM_DIR="$NVM_DIR" bash "$NVM_USE_SCRIPT" >"$NODE_SETUP_LOG" 2>&1
    }

    if ! nvm_attempt; then
        warn "Retrying nvm initialization after ensuring Homebrew nvm is installed..."
        if command -v brew >/dev/null 2>&1; then
            HOMEBREW_NO_AUTO_UPDATE=1 brew install nvm >/dev/null 2>&1 || true
        fi
    fi

    if nvm_attempt; then
        NODE_BIN_DIR="$NVM_DIR/versions/node/$REQUIRED_NODE_VERSION/bin"
        if [ -x "$NODE_BIN_DIR/node" ]; then
            PATH="$NODE_BIN_DIR:$PATH"
            export PATH
        fi
        ACTIVE_NODE_VERSION=$(node --version 2>/dev/null || true)
        if [ -n "$ACTIVE_NODE_VERSION" ]; then
            success "Node.js $ACTIVE_NODE_VERSION is active via nvm"
        else
            success "Node.js is active via nvm"
        fi
    else
        warn "Failed to initialize Node.js via nvm; attempting Homebrew node fallback..."
        if command -v brew >/dev/null 2>&1; then
            NODE_MAJOR=$(echo "$REQUIRED_NODE_VERSION" | sed 's/^v//' | cut -d. -f1)
            BREW_NODE_FORMULA="node@${NODE_MAJOR}"
            if ! brew list --formula "$BREW_NODE_FORMULA" >/dev/null 2>&1; then
                HOMEBREW_NO_AUTO_UPDATE=1 brew install "$BREW_NODE_FORMULA" || true
            fi
            BREW_NODE_PREFIX=$(brew --prefix "$BREW_NODE_FORMULA" 2>/dev/null || echo "")
            if [ -n "$BREW_NODE_PREFIX" ] && [ -x "$BREW_NODE_PREFIX/bin/node" ]; then
                PATH="$BREW_NODE_PREFIX/bin:$PATH"
                export PATH
                ACTIVE_NODE_VERSION=$(node --version 2>/dev/null || true)
                if [ -n "$ACTIVE_NODE_VERSION" ]; then
                    warn "Using Homebrew $BREW_NODE_FORMULA (Node $ACTIVE_NODE_VERSION) as fallback; nvm did not initialize."
                fi
            fi
        fi

        if [ -n "${ACTIVE_NODE_VERSION:-}" ]; then
            success "Node.js is available via Homebrew fallback"
        else
            error "Failed to initialize Node.js via nvm; see logs below"
            if [ -s "$NODE_SETUP_LOG" ]; then
                while IFS= read -r line; do
                    warn "nvm: $line"
                done < "$NODE_SETUP_LOG"
            else
                warn "nvm: no output captured from $NVM_USE_SCRIPT"
            fi
            ERRORS=$((ERRORS + 1))
        fi
    fi
    rm -f "$NODE_SETUP_LOG"
fi

echo ""

# 3. Check and setup pyenv + Python
info "Checking Python version management..."

# Determine required Python version
REQUIRED_PYTHON_VERSION="3.12.12"
if [ -f ".python-version" ]; then
    REQUIRED_PYTHON_VERSION=$(cat .python-version)
fi

# Ensure Homebrew bin directories are in PATH
if command -v brew &> /dev/null; then
    BREW_PREFIX=$(brew --prefix 2>/dev/null || echo "/usr/local")
    export PATH="$BREW_PREFIX/bin:$PATH"
fi

# Install pyenv via Homebrew if needed
if ! command -v pyenv &> /dev/null; then
    if command -v brew &> /dev/null; then
        warn "pyenv not found - installing via Homebrew..."
        if HOMEBREW_NO_AUTO_UPDATE=1 brew install pyenv; then
            success "pyenv installed via Homebrew"
            # After fresh install, ensure it's in PATH
            export PATH="$BREW_PREFIX/bin:$PATH"
        else
            error "Failed to install pyenv via Homebrew"
            ERRORS=$((ERRORS + 1))
        fi
    else
        error "pyenv is required but Homebrew is not available. Install pyenv from https://github.com/pyenv/pyenv"
        ERRORS=$((ERRORS + 1))
    fi
fi

# Initialize pyenv (no shell profile modifications needed)
if command -v pyenv &> /dev/null; then
    export PYENV_ROOT="${PYENV_ROOT:-$HOME/.pyenv}"
    eval "$(pyenv init -)"
    success "pyenv is available"
else
    error "pyenv is required but not available"
    ERRORS=$((ERRORS + 1))
fi

# Install required Python version if needed
if command -v pyenv &> /dev/null; then
    if pyenv versions --bare | grep -q "^${REQUIRED_PYTHON_VERSION}$"; then
        success "Python $REQUIRED_PYTHON_VERSION is already installed via pyenv"
    else
        info "Installing Python $REQUIRED_PYTHON_VERSION via pyenv..."
        # Use all CPU cores for parallel compilation
        NCPU=$(sysctl -n hw.ncpu 2>/dev/null || echo 4)
        info "Using $NCPU CPU cores for parallel compilation..."
        xz_prefix=$(brew --prefix xz 2>/dev/null || echo "${BREW_PREFIX:-/usr/local}")
        zlib_prefix=$(brew --prefix zlib 2>/dev/null || echo "${BREW_PREFIX:-/usr/local}")
        export LDFLAGS="${LDFLAGS:-} -L${xz_prefix}/lib -L${zlib_prefix}/lib"
        export CPPFLAGS="${CPPFLAGS:-} -I${xz_prefix}/include -I${zlib_prefix}/include"
        export PKG_CONFIG_PATH="${PKG_CONFIG_PATH:-}${PKG_CONFIG_PATH:+:}${xz_prefix}/lib/pkgconfig:${zlib_prefix}/lib/pkgconfig"
        if MAKE_OPTS="-j$NCPU" pyenv install "$REQUIRED_PYTHON_VERSION"; then
            success "Python $REQUIRED_PYTHON_VERSION installed"
        else
            error "Failed to install Python $REQUIRED_PYTHON_VERSION via pyenv"
            ERRORS=$((ERRORS + 1))
        fi
    fi

    # Set local Python version and verify it's active
    if pyenv versions --bare | grep -q "^${REQUIRED_PYTHON_VERSION}$"; then
        pyenv local "$REQUIRED_PYTHON_VERSION"
        # Re-initialize pyenv after setting local version to ensure PATH is updated
        eval "$(pyenv init -)"
        PYTHON_BIN=$(pyenv which python3 2>/dev/null || pyenv which python 2>/dev/null || true)
        if [ -n "$PYTHON_BIN" ]; then
            PYTHON_VERSION=$("$PYTHON_BIN" --version | awk '{print $2}')
            success "Python $PYTHON_VERSION is active via pyenv"
        else
            error "Failed to locate Python binary from pyenv"
            ERRORS=$((ERRORS + 1))
        fi
    fi
else
    error "Cannot manage Python version without pyenv"
    ERRORS=$((ERRORS + 1))
fi

if command -v uv &> /dev/null; then
    success "uv is installed"
else
    if command -v brew &> /dev/null; then
        warn "uv not found - installing via Homebrew..."
        if brew install uv; then
            success "uv installed successfully"
        else
            warn "Failed to install uv via Homebrew, trying pip..."
            if pip3 install uv; then
                success "uv installed via pip"
            else
                error "Failed to install uv"
                ERRORS=$((ERRORS + 1))
            fi
        fi
    else
        warn "uv not found - installing via pip..."
        if pip3 install uv; then
            success "uv installed successfully"
        else
            error "Failed to install uv"
            ERRORS=$((ERRORS + 1))
        fi
    fi
fi

echo ""

info "Ensuring talos CLI is available..."

# Verify Python version before building talos
if [ -z "$PYTHON_BIN" ]; then
    error "PYTHON_BIN is not set - cannot build talos"
    ERRORS=$((ERRORS + 1))
else
    ACTIVE_PYTHON_VERSION=$("$PYTHON_BIN" --version 2>&1 | awk '{print $2}')
    info "Building talos with Python $ACTIVE_PYTHON_VERSION at $PYTHON_BIN"

    # Check if Python meets minimum version requirement (>= 3.10)
    PYTHON_MAJOR=$(echo "$ACTIVE_PYTHON_VERSION" | cut -d. -f1)
    PYTHON_MINOR=$(echo "$ACTIVE_PYTHON_VERSION" | cut -d. -f2)
    if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 10 ]); then
        error "Python $ACTIVE_PYTHON_VERSION does not meet talos requirement (>= 3.10)"
        error "Expected to use $REQUIRED_PYTHON_VERSION but found $ACTIVE_PYTHON_VERSION"
        ERRORS=$((ERRORS + 1))
    fi
fi

if [ $ERRORS -eq 0 ]; then
    TALOS_BIN="$REPO_ROOT/talos/build/bin/talos"
    if PYTHON="$PYTHON_BIN" talos/build.sh; then
        if [ -x "$TALOS_BIN" ]; then
            success "Talos CLI built at $TALOS_BIN"
        else
            error "Talos build did not produce $TALOS_BIN"
            ERRORS=$((ERRORS + 1))
        fi
    else
        error "Failed to build Talos CLI"
        ERRORS=$((ERRORS + 1))
    fi
fi

echo ""

info "Running add-on pre_setup hooks..."
ADDON_NAMES_ERR=$(mktemp)
ADDON_NAMES_JSON=$("$TALOS_BIN" addon names --json 2>"$ADDON_NAMES_ERR") || ADDON_NAMES_STATUS=$?
ADDON_NAMES_STATUS=${ADDON_NAMES_STATUS:-0}
ADDON_NAMES=$(
    printf '%s' "$ADDON_NAMES_JSON" | python3 - <<'PY'
import json, sys
try:
    names = json.load(sys.stdin)
    if isinstance(names, list):
        print(" ".join(names))
except Exception:
    pass
PY
)
if [ $ADDON_NAMES_STATUS -ne 0 ] || [ -z "$ADDON_NAMES" ]; then
    # Fallback: find */addon.yaml without relying on talos CLI
    FALLBACK_NAMES=$(
        find "$REPO_ROOT" -maxdepth 2 -name addon.yaml -print0 2>/dev/null \
            | while IFS= read -r -d '' file; do
                basename "$(dirname "$file")"
            done \
            | sort -u \
            | tr '\n' ' ' \
            | sed 's/[[:space:]]*$//'
    )
    if [ -n "$FALLBACK_NAMES" ]; then
        info "Using fallback add-on discovery"
        ADDON_NAMES="$FALLBACK_NAMES"
        ADDON_NAMES_STATUS=0
    fi
fi

if [ $ADDON_NAMES_STATUS -ne 0 ] || [ -z "$ADDON_NAMES" ]; then
    warn "Could not determine add-on list; skipping pre_setup hooks"
    if [ -s "$ADDON_NAMES_ERR" ]; then
        while IFS= read -r line; do
            warn "talos: $line"
        done < "$ADDON_NAMES_ERR"
    fi
else
    for addon in $ADDON_NAMES; do
        if "$TALOS_BIN" hook run "$addon" pre_setup --if-missing-ok; then
            success "pre_setup hook: $addon"
        else
            warn "pre_setup hook failed for $addon"
            ERRORS=$((ERRORS + 1))
        fi
    done
fi
rm -f "$ADDON_NAMES_ERR"

echo ""

# 4. Verify SSH access to Home Assistant host (needed for deploy)
HA_HOST=${HA_HOST:-homeassistant.local}
HA_PORT=${HA_PORT:-22}
HA_USER=${HA_USER:-root}
info "Checking SSH access to Home Assistant (${HA_USER}@${HA_HOST}:${HA_PORT})..."
if ssh -o BatchMode=yes -o ConnectTimeout=5 -p "$HA_PORT" "$HA_USER@$HA_HOST" "exit 0" >/dev/null 2>&1; then
    success "SSH to Home Assistant is reachable"
else
    warn "Could not SSH to ${HA_USER}@${HA_HOST}:${HA_PORT}."
    warn "If Home Assistant is up, add your public key (e.g., contents of ~/.ssh/id_rsa.pub) to the authorized_keys field in the Supervisor SSH add-on config: http://${HA_HOST}:8123/hassio/addon/core_ssh/config"
    ERRORS=$((ERRORS + 1))
fi

echo ""

# 5. Run per-add-on setup recipes
info "Running add-on setup recipes..."
if "$TALOS_BIN" addons run setup; then
    success "Add-on setup completed"
else
    error "Add-on setup failed; see logs above"
    ERRORS=$((ERRORS + 1))
fi

echo ""

# Summary
echo "╭────────────────────────────────────────────────────╮"
if [ $ERRORS -eq 0 ]; then
    echo -e "│  ${GREEN}✓ Setup completed successfully!${NC}                   │"
    echo "╰────────────────────────────────────────────────────╯"
    echo ""
    echo "You can now run:"
    echo "  ${BLUE}just dev${NC}  - Start all services for development"
    echo ""
else
    echo -e "│  ${YELLOW}⚠ Setup completed with $ERRORS error(s)${NC}              │"
    echo "╰────────────────────────────────────────────────────╯"
    echo ""
    echo "Please fix the errors above and run 'just setup' again"
    echo ""
    exit 1
fi
