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
else
    warn "Homebrew not found. Please install from https://brew.sh"
    warn "Then run: brew install cairo"
    ERRORS=$((ERRORS + 1))
fi

echo ""

# 2. Check and setup nvm + Node.js
info "Checking Node.js version management..."

# Try to load nvm if it exists
export NVM_DIR="$HOME/.nvm"
if [ -s "$NVM_DIR/nvm.sh" ]; then
    source "$NVM_DIR/nvm.sh"
elif [ -s "/opt/homebrew/opt/nvm/nvm.sh" ]; then
    # Homebrew location on Apple Silicon
    source "/opt/homebrew/opt/nvm/nvm.sh"
elif [ -s "/usr/local/opt/nvm/nvm.sh" ]; then
    # Homebrew location on Intel
    source "/usr/local/opt/nvm/nvm.sh"
fi

NVM_BREW_INSTALLED=0
if brew_formula_installed "nvm"; then
    NVM_BREW_INSTALLED=1
fi

NVM_AVAILABLE=0
# Check if nvm is available
if ! command -v nvm &> /dev/null; then
    warn "nvm not found"
    if [ $NVM_BREW_INSTALLED -eq 1 ]; then
        warn "Homebrew reports nvm is installed, but 'nvm' is not available in this shell"
        print_brew_post_install_notes "nvm"
    elif command -v brew &> /dev/null; then
        warn "Installing nvm via Homebrew..."
        if brew install nvm; then
            success "nvm installed"
            # Create nvm directory
            mkdir -p "$HOME/.nvm"
            # Try to source again
            [ -s "/opt/homebrew/opt/nvm/nvm.sh" ] && source "/opt/homebrew/opt/nvm/nvm.sh"
            [ -s "/usr/local/opt/nvm/nvm.sh" ] && source "/usr/local/opt/nvm/nvm.sh"
        else
            error "Failed to install nvm via Homebrew"
            ERRORS=$((ERRORS + 1))
        fi
    else
        error "Cannot install nvm without Homebrew"
        ERRORS=$((ERRORS + 1))
    fi
fi

if command -v nvm &> /dev/null; then
    NVM_AVAILABLE=1
fi

# Now check Node.js version
REQUIRED_NODE_VERSION="v20.18.2"
if [ -f ".nvmrc" ]; then
    REQUIRED_NODE_VERSION=$(cat .nvmrc)
fi

if [ $NVM_AVAILABLE -eq 1 ]; then
    info "Using nvm to manage Node.js version..."
    if nvm install "$REQUIRED_NODE_VERSION" &> /dev/null; then
        nvm use "$REQUIRED_NODE_VERSION" &> /dev/null
        success "Node.js $REQUIRED_NODE_VERSION is active"
    else
        error "Failed to install Node.js $REQUIRED_NODE_VERSION via nvm"
        ERRORS=$((ERRORS + 1))
    fi
elif command -v node &> /dev/null; then
    CURRENT_NODE_VERSION=$(node --version)
    if [ "$CURRENT_NODE_VERSION" = "$REQUIRED_NODE_VERSION" ]; then
        success "Node.js $CURRENT_NODE_VERSION is installed"
    else
        warn "Node.js version mismatch: current=$CURRENT_NODE_VERSION, required=$REQUIRED_NODE_VERSION"
        warn "Install nvm to manage Node versions: brew install nvm"
    fi
else
    error "Node.js not found and nvm unavailable"
    ERRORS=$((ERRORS + 1))
fi

if [ $NVM_AVAILABLE -eq 0 ]; then
    error "nvm is required but not available in this shell; ensure it is installed and sourced"
    [ $NVM_BREW_INSTALLED -eq 1 ] && print_brew_post_install_notes "nvm"
    ERRORS=$((ERRORS + 1))
fi

echo ""

# 3. Check and setup pyenv + Python
info "Checking Python version management..."

PYENV_BREW_INSTALLED=0
if brew_formula_installed "pyenv"; then
    PYENV_BREW_INSTALLED=1
fi

# Try to initialize pyenv if it exists
if command -v pyenv &> /dev/null; then
    eval "$(pyenv init -)"
    success "pyenv is available"
elif [ $PYENV_BREW_INSTALLED -eq 1 ]; then
    warn "Homebrew reports pyenv is installed, but 'pyenv' is not available in this shell"
    print_brew_post_install_notes "pyenv"
elif command -v brew &> /dev/null; then
    warn "pyenv not found - installing via Homebrew..."
    if brew install pyenv; then
        success "pyenv installed"
        eval "$(pyenv init -)"
    else
        warn "Failed to install pyenv (continuing with system Python)"
    fi
else
    info "pyenv not available (using system Python)"
fi

PYENV_AVAILABLE=0
if command -v pyenv &> /dev/null; then
    PYENV_AVAILABLE=1
fi

# Determine required Python version
REQUIRED_PYTHON_VERSION="3.12.12"
if [ -f ".python-version" ]; then
    REQUIRED_PYTHON_VERSION=$(cat .python-version)
fi

IFS='.' read -r PYTHON_MAJOR PYTHON_MINOR _ <<< "$REQUIRED_PYTHON_VERSION"
PYTHON_MAJOR_MINOR="${PYTHON_MAJOR}.${PYTHON_MINOR:-0}"
BREW_PYTHON_FORMULA="python@${PYTHON_MAJOR_MINOR}"
BREW_PYTHON_PREFIX=""
BREW_PYTHON_BIN=""
PYTHON_BIN=""

# Prefer Homebrew's Python to avoid compiling from source
if command -v brew &> /dev/null; then
    info "Checking Homebrew for Python $REQUIRED_PYTHON_VERSION..."
    if HOMEBREW_NO_AUTO_UPDATE=1 brew list "$BREW_PYTHON_FORMULA" &> /dev/null; then
        success "$BREW_PYTHON_FORMULA is installed"
    else
        warn "$BREW_PYTHON_FORMULA not found - installing via Homebrew..."
        if HOMEBREW_NO_AUTO_UPDATE=1 brew install "$BREW_PYTHON_FORMULA"; then
            success "$BREW_PYTHON_FORMULA installed"
        else
            warn "Failed to install $BREW_PYTHON_FORMULA via Homebrew"
        fi
    fi

    BREW_PYTHON_PREFIX=$(HOMEBREW_NO_AUTO_UPDATE=1 brew --prefix "$BREW_PYTHON_FORMULA" 2>/dev/null || true)
    if [ -n "$BREW_PYTHON_PREFIX" ]; then
        for candidate in \
            "$BREW_PYTHON_PREFIX/bin/python${PYTHON_MAJOR_MINOR}" \
            "$BREW_PYTHON_PREFIX/bin/python${PYTHON_MAJOR}" \
            "$BREW_PYTHON_PREFIX/bin/python3" \
            "$BREW_PYTHON_PREFIX/libexec/bin/python${PYTHON_MAJOR_MINOR}" \
            "$BREW_PYTHON_PREFIX/libexec/bin/python3" \
            "$BREW_PYTHON_PREFIX/bin/python"; do
            if [ -x "$candidate" ]; then
                BREW_PYTHON_BIN="$candidate"
                break
            fi
        done

        if [ -n "$BREW_PYTHON_BIN" ]; then
            BREW_PYTHON_VERSION=$("$BREW_PYTHON_BIN" --version 2>/dev/null | awk '{print $2}')
            if [ "$BREW_PYTHON_VERSION" = "$REQUIRED_PYTHON_VERSION" ]; then
                success "Homebrew Python $BREW_PYTHON_VERSION detected at $BREW_PYTHON_BIN"
            else
                warn "Homebrew $BREW_PYTHON_FORMULA provides $BREW_PYTHON_VERSION (expected $REQUIRED_PYTHON_VERSION)"
                BREW_PYTHON_BIN=""
            fi
        else
            warn "Homebrew $BREW_PYTHON_FORMULA installed but Python binary not found"
        fi
    fi
fi

if [ -n "$BREW_PYTHON_BIN" ]; then
    PYTHON_BIN="$BREW_PYTHON_BIN"
fi

# Try to install/use correct Python version with pyenv
if [ $PYENV_AVAILABLE -eq 1 ]; then
    info "Using pyenv to manage Python version..."
    PYENV_HAS_VERSION=0
    if pyenv versions --bare | grep -q "^${REQUIRED_PYTHON_VERSION}$"; then
        PYENV_HAS_VERSION=1
    fi

    if [ $PYENV_HAS_VERSION -eq 0 ] && [ -n "$BREW_PYTHON_BIN" ] && [ -n "$BREW_PYTHON_PREFIX" ]; then
        PYENV_ROOT_DIR=$(pyenv root)
        PYENV_VERSION_DIR="$PYENV_ROOT_DIR/versions/$REQUIRED_PYTHON_VERSION"
        if [ ! -d "$PYENV_VERSION_DIR" ]; then
            info "Linking Homebrew Python into pyenv at $PYENV_VERSION_DIR..."
            mkdir -p "$PYENV_VERSION_DIR"
            if command -v rsync &> /dev/null; then
                if rsync -a "$BREW_PYTHON_PREFIX"/ "$PYENV_VERSION_DIR"/ > /dev/null 2>&1; then
                    PYENV_HAS_VERSION=1
                fi
            else
                if cp -R "$BREW_PYTHON_PREFIX"/. "$PYENV_VERSION_DIR"/; then
                    PYENV_HAS_VERSION=1
                fi
            fi

            if [ $PYENV_HAS_VERSION -eq 1 ]; then
                if [ -x "$PYENV_VERSION_DIR/bin/python3" ] && [ ! -e "$PYENV_VERSION_DIR/bin/python" ]; then
                    ln -sf python3 "$PYENV_VERSION_DIR/bin/python"
                fi
                if [ -x "$PYENV_VERSION_DIR/bin/pip3" ] && [ ! -e "$PYENV_VERSION_DIR/bin/pip" ]; then
                    ln -sf pip3 "$PYENV_VERSION_DIR/bin/pip"
                fi
                success "Homebrew Python linked into pyenv"
            else
                warn "Failed to copy Homebrew Python into pyenv"
                rm -rf "$PYENV_VERSION_DIR" 2>/dev/null || true
            fi
        fi
    fi

    if [ $PYENV_HAS_VERSION -eq 0 ]; then
        info "Installing Python $REQUIRED_PYTHON_VERSION via pyenv..."
        # Use all CPU cores for parallel compilation
        NCPU=$(sysctl -n hw.ncpu 2>/dev/null || echo 4)
        info "Using $NCPU CPU cores for parallel compilation..."
        if MAKE_OPTS="-j$NCPU" pyenv install "$REQUIRED_PYTHON_VERSION"; then
            success "Python $REQUIRED_PYTHON_VERSION installed"
            PYENV_HAS_VERSION=1
        else
            warn "Failed to install Python $REQUIRED_PYTHON_VERSION via pyenv"
        fi
    fi

    if [ $PYENV_HAS_VERSION -eq 1 ]; then
        pyenv local "$REQUIRED_PYTHON_VERSION"
        success "Python $REQUIRED_PYTHON_VERSION is active"
        PYENV_PYTHON_BIN=$(pyenv which python3 2>/dev/null || pyenv which python 2>/dev/null || true)
        if [ -n "$PYENV_PYTHON_BIN" ]; then
            PYTHON_BIN="$PYENV_PYTHON_BIN"
        fi
    fi
fi

# Check if Python is available
if [ -z "$PYTHON_BIN" ]; then
    if command -v python3 &> /dev/null; then
        PYTHON_BIN=$(command -v python3)
    elif command -v python &> /dev/null; then
        PYTHON_BIN=$(command -v python)
    fi
fi

if [ -n "$PYTHON_BIN" ]; then
    PYTHON_VERSION=$("$PYTHON_BIN" --version | awk '{print $2}')
    success "Python $PYTHON_VERSION is available via $PYTHON_BIN"
else
    error "Python 3 not found"
    ERRORS=$((ERRORS + 1))
fi

if [ $PYENV_AVAILABLE -eq 0 ]; then
    error "pyenv is required but not available in this shell; ensure it is installed and initialized"
    [ $PYENV_BREW_INSTALLED -eq 1 ] && print_brew_post_install_notes "pyenv"
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
TALOS_BIN="$REPO_ROOT/talos/build/bin/talos"
if talos/build.sh; then
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
