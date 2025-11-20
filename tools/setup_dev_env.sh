#!/usr/bin/env bash
set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

# Check if nvm is available
if ! command -v nvm &> /dev/null; then
    warn "nvm not found"
    if command -v brew &> /dev/null; then
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

# Now check Node.js version
REQUIRED_NODE_VERSION="v20.18.2"
if [ -f ".nvmrc" ]; then
    REQUIRED_NODE_VERSION=$(cat .nvmrc)
fi

if command -v nvm &> /dev/null; then
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

echo ""

# 3. Check and setup pyenv + Python
info "Checking Python version management..."

# Try to initialize pyenv if it exists
if command -v pyenv &> /dev/null; then
    eval "$(pyenv init -)"
    success "pyenv is available"
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
if command -v pyenv &> /dev/null; then
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

# Validate that SSDP probes can leave this host. VPN/ZeroTrust clients on macOS
# often install utun routes that block 239.255.255.250/255.255.255.255 traffic,
# which makes node-sonos-http-api fail with "No system has yet been discovered".
info "Validating Sonos discovery reachability..."
SONOS_CHECK_LOG=$(mktemp -t sonos-check.XXXXXX)
if python tools/addon_hooks.py run node-sonos-http-api pre_setup > "$SONOS_CHECK_LOG" 2>&1; then
    success "SSDP multicast/broadcast probes were sent successfully"
else
    warn "Sonos discovery test failed:"
    cat "$SONOS_CHECK_LOG"
    warn "Disable VPN/ZeroTrust adapters (Tailscale, WARP, corp VPN), turn off 'Private Wi-Fi Address' and 'Limit IP Address Tracking' for your Wi-Fi network, then rerun 'just setup'."
    ERRORS=$((ERRORS + 1))
fi
rm -f "$SONOS_CHECK_LOG"

echo ""

# 4. Setup repo-level Python dependencies
info "Setting up repo-level Python dependencies..."

if [ -z "$PYTHON_BIN" ]; then
    error "Skipping Python virtual environment setup because no interpreter was found"
    ERRORS=$((ERRORS + 1))
else
    if [ ! -d ".venv" ]; then
        info "Creating Python virtual environment..."
        "$PYTHON_BIN" -m venv .venv
        success "Virtual environment created"
    fi

    info "Installing Python dependencies..."
    if .venv/bin/pip install -r requirements.txt > /dev/null 2>&1; then
        success "Python dependencies installed"
    else
        error "Failed to install Python dependencies"
        ERRORS=$((ERRORS + 1))
    fi
fi

echo ""

# 5. Setup node-sonos-http-api (special case)
info "Setting up node-sonos-http-api..."

SONOS_DIR="node-sonos-http-api"
SONOS_UPSTREAM="$SONOS_DIR/node-sonos-http-api"

if [ -d "$SONOS_UPSTREAM" ]; then
    success "Upstream node-sonos-http-api already cloned"
else
    info "Cloning upstream node-sonos-http-api..."
    if git clone https://github.com/jishi/node-sonos-http-api.git "$SONOS_UPSTREAM"; then
        success "Upstream repository cloned"
    else
        error "Failed to clone upstream repository"
        ERRORS=$((ERRORS + 1))
    fi
fi

if [ -d "$SONOS_UPSTREAM" ]; then
    info "Installing node-sonos-http-api dependencies..."
    cd "$SONOS_UPSTREAM"
    if npm install > /dev/null 2>&1; then
        success "node-sonos-http-api dependencies installed"
    else
        error "Failed to install node-sonos-http-api dependencies"
        ERRORS=$((ERRORS + 1))
    fi
    cd "$REPO_ROOT"
fi

echo ""

# 6. Setup sonos-api
info "Setting up sonos-api..."

cd sonos-api
if [ -d "node_modules" ]; then
    success "sonos-api dependencies already installed"
else
    info "Installing sonos-api dependencies..."
    if npm install > /dev/null 2>&1; then
        success "sonos-api dependencies installed"
    else
        error "Failed to install sonos-api dependencies"
        ERRORS=$((ERRORS + 1))
    fi
fi
cd "$REPO_ROOT"

echo ""

# 7. Setup grid-dashboard
info "Setting up grid-dashboard..."

cd grid-dashboard/ExpressServer
if [ -d "node_modules" ]; then
    success "grid-dashboard dependencies already installed"
else
    info "Installing grid-dashboard dependencies..."
    if npm install > /dev/null 2>&1; then
        success "grid-dashboard dependencies installed"
    else
        error "Failed to install grid-dashboard dependencies"
        ERRORS=$((ERRORS + 1))
    fi
fi
cd "$REPO_ROOT"

echo ""

# 8. Setup printer
info "Setting up printer service..."

cd printer
if [ -f "uv.lock" ]; then
    info "Syncing printer dependencies with uv..."
    if uv sync --python "$REQUIRED_PYTHON_VERSION" > /dev/null 2>&1; then
        success "printer dependencies synced"
    else
        error "Failed to sync printer dependencies"
        ERRORS=$((ERRORS + 1))
    fi
else
    warn "uv.lock not found in printer/"
fi
cd "$REPO_ROOT"

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
