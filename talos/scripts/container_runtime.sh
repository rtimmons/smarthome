#!/usr/bin/env bash
# Container runtime detection and management utility
# Prefers podman over docker, provides consistent interface

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
info() {
    echo -e "${BLUE}ℹ${NC} $1" >&2
}

success() {
    echo -e "${GREEN}✓${NC} $1" >&2
}

warn() {
    echo -e "${YELLOW}⚠${NC} $1" >&2
}

error() {
    echo -e "${RED}✗${NC} $1" >&2
}

# Detect available container runtime
detect_runtime() {
    if command -v podman >/dev/null 2>&1; then
        echo "podman"
        return 0
    elif command -v docker >/dev/null 2>&1; then
        echo "docker"
        return 0
    else
        return 1
    fi
}

# Get the container runtime command with any necessary flags
get_runtime_cmd() {
    local runtime
    if ! runtime=$(detect_runtime); then
        error "No container runtime available (podman or docker required)"
        return 1
    fi
    echo "$runtime"
}

# Check if container runtime is available
check_runtime() {
    local runtime
    if runtime=$(detect_runtime); then
        success "Container runtime: $runtime"
        return 0
    else
        error "No container runtime found (podman or docker required)"
        return 1
    fi
}

# Verify podman machine is working
verify_podman_machine() {
    if ! command -v podman >/dev/null 2>&1; then
        return 1
    fi

    # Check if machine exists and is running
    local machine_status
    machine_status=$(podman machine list --format "{{.Running}}" 2>/dev/null | head -n1 || echo "false")

    if [[ "$machine_status" == "true" ]]; then
        # Test that podman can actually run containers
        if podman run --rm alpine:latest echo "podman test" >/dev/null 2>&1; then
            return 0
        else
            warn "podman machine is running but cannot execute containers"
            return 1
        fi
    else
        return 1
    fi
}

# Setup podman machine
setup_podman_machine() {
    info "Setting up podman machine..."

    # Check if machine already exists
    local existing_machines
    existing_machines=$(podman machine list --format "{{.Name}}" 2>/dev/null || true)

    if [[ -n "$existing_machines" ]]; then
        info "Found existing podman machine(s): $existing_machines"

        # Try to start existing machine
        info "Starting existing podman machine..."
        if podman machine start 2>/dev/null; then
            success "Existing podman machine started"
        else
            warn "Failed to start existing machine, will recreate"
            # Remove broken machine
            podman machine rm -f 2>/dev/null || true
        fi
    fi

    # Create new machine if none exists or previous failed
    if ! verify_podman_machine; then
        info "Creating new podman machine..."

        # Remove any existing broken machines
        podman machine rm -f 2>/dev/null || true

        # Create machine with appropriate settings
        if podman machine init --cpus 2 --memory 4096 --disk-size 50; then
            info "Starting podman machine..."
            if podman machine start; then
                success "podman machine created and started"

                # Wait a moment for machine to be fully ready
                sleep 3

                # Verify it's working
                if verify_podman_machine; then
                    success "podman machine verified working"
                    return 0
                else
                    error "podman machine started but verification failed"
                    return 1
                fi
            else
                error "Failed to start podman machine"
                return 1
            fi
        else
            error "Failed to create podman machine"
            return 1
        fi
    else
        success "podman machine is already working"
        return 0
    fi
}

# Install podman via Homebrew (macOS)
install_podman() {
    if [[ "$OSTYPE" != "darwin"* ]]; then
        error "Automatic podman installation only supported on macOS"
        error "Please install podman manually: https://podman.io/getting-started/installation"
        return 1
    fi

    if ! command -v brew >/dev/null 2>&1; then
        error "Homebrew required to install podman"
        error "Install Homebrew from https://brew.sh then run: brew install podman"
        return 1
    fi

    info "Installing podman via Homebrew..."
    if brew install podman; then
        success "podman installed successfully"

        # Setup podman machine
        if setup_podman_machine; then
            success "podman installation and setup completed"
            return 0
        else
            error "podman installed but machine setup failed"
            return 1
        fi
    else
        error "Failed to install podman via Homebrew"
        return 1
    fi
}

# Build container image
build_image() {
    local tag="$1"
    local context="$2"
    local platform="${3:-}"
    
    local runtime
    if ! runtime=$(get_runtime_cmd); then
        return 1
    fi
    
    local cmd=("$runtime" "build" "-t" "$tag")
    
    if [[ -n "$platform" ]]; then
        cmd+=("--platform" "$platform")
    fi
    
    cmd+=("$context")
    
    info "Building container image: ${cmd[*]}"
    "${cmd[@]}"
}

# Main command dispatcher
main() {
    case "${1:-}" in
        "detect")
            detect_runtime
            ;;
        "check")
            check_runtime
            ;;
        "verify")
            if command -v podman >/dev/null 2>&1; then
                if verify_podman_machine; then
                    success "podman machine is working correctly"
                    exit 0
                else
                    error "podman machine verification failed"
                    exit 1
                fi
            else
                error "podman not installed"
                exit 1
            fi
            ;;
        "setup-machine")
            if command -v podman >/dev/null 2>&1; then
                setup_podman_machine
            else
                error "podman not installed"
                exit 1
            fi
            ;;
        "install")
            install_podman
            ;;
        "build")
            if [[ $# -lt 3 ]]; then
                error "Usage: $0 build <tag> <context> [platform]"
                exit 1
            fi
            build_image "$2" "$3" "${4:-}"
            ;;
        "cmd")
            get_runtime_cmd
            ;;
        *)
            echo "Container runtime detection and management utility"
            echo ""
            echo "Usage: $0 <command>"
            echo ""
            echo "Commands:"
            echo "  detect        - Output detected runtime (podman or docker)"
            echo "  check         - Check if runtime is available (with status output)"
            echo "  verify        - Verify podman machine is working (podman only)"
            echo "  setup-machine - Setup/repair podman machine (podman only)"
            echo "  install       - Install podman via Homebrew (macOS only)"
            echo "  build         - Build container image: build <tag> <context> [platform]"
            echo "  cmd           - Output runtime command for use in scripts"
            echo ""
            echo "Examples:"
            echo "  $0 detect                           # outputs: podman"
            echo "  $0 verify                           # verifies podman machine works"
            echo "  $0 build myapp:latest /path/to/app  # builds with detected runtime"
            echo "  $0 build myapp:latest /path/to/app linux/arm64  # with platform"
            echo ""
            exit 1
            ;;
    esac
}

main "$@"
