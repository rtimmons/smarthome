# Container Runtime Management

This project uses a container runtime detection system that prefers `podman` over `docker` for building container images. The system automatically detects available runtimes and provides a consistent interface for container operations.

## Overview

The container runtime system consists of:

1. **Detection utility** (`talos/scripts/container_runtime.sh`) - Detects and manages container runtimes
2. **Setup integration** - Automatically installs podman during `just setup` if no runtime is available
3. **Build integration** - Used by printer add-on builds and potentially other container operations

## Runtime Priority

1. **podman** (preferred) - Modern, rootless container runtime
2. **docker** (fallback) - Traditional container runtime

## Automatic Installation

During `just setup`, the system will:

1. Check for existing container runtime (podman or docker)
2. If none found, attempt to install podman via Homebrew (macOS only)
3. Initialize podman machine if needed
4. Report success or provide manual installation instructions

## Manual Installation

### macOS (Homebrew)
```bash
brew install podman
podman machine init --cpus 2 --memory 4096 --disk-size 50
podman machine start
```

### Linux
See [podman installation guide](https://podman.io/getting-started/installation) for your distribution.

### Docker (alternative)
```bash
# macOS
brew install docker

# Or install Docker Desktop from https://docker.com
```

## Usage

### Direct Usage
```bash
# Detect runtime
./talos/scripts/container_runtime.sh detect
# Output: podman

# Check runtime status
./talos/scripts/container_runtime.sh check
# Output: ✓ Container runtime: podman

# Build image
./talos/scripts/container_runtime.sh build myapp:latest /path/to/context

# Build with platform
./talos/scripts/container_runtime.sh build myapp:latest /path/to/context linux/arm64

# Get runtime command for scripts
RUNTIME=$(./talos/scripts/container_runtime.sh cmd)
$RUNTIME --version
```

### Integration Usage

The printer add-on automatically uses this system:

```bash
# Build printer image (uses detected runtime)
just printer-image

# Build for specific platform
PRINTER_DOCKER_PLATFORM=linux/arm64 just printer-image
```

## Troubleshooting

### No Runtime Available
If you see "No container runtime found", install one manually:

```bash
# Preferred: Install podman
brew install podman  # macOS
# or follow https://podman.io/getting-started/installation

# Alternative: Install docker
brew install docker  # macOS
# or install Docker Desktop
```

### Podman Machine Issues
If podman is installed but builds fail:

```bash
# Check machine status
podman machine list

# Start machine if stopped
podman machine start

# Recreate machine if corrupted
podman machine rm
podman machine init --cpus 2 --memory 4096 --disk-size 50
podman machine start
```

### Permission Issues
If you get permission errors:

```bash
# For podman (should work rootless)
podman info

# For docker (may need group membership)
sudo usermod -aG docker $USER
# Then log out and back in
```

## Implementation Details

The container runtime detection script (`talos/scripts/container_runtime.sh`) provides:

- **Runtime detection** - Checks for podman first, then docker
- **Consistent interface** - Same commands work regardless of runtime
- **Error handling** - Clear error messages and installation guidance
- **Platform support** - Handles platform-specific builds
- **Integration hooks** - Easy integration with build systems

The script is used by:
- Setup process (`talos/setup_dev_env.sh`)
- Printer builds (`printer/Justfile`)
- Future container operations as needed

## Future Enhancements

Potential future improvements:
- Support for other container runtimes (buildah, etc.)
- Automatic runtime switching based on requirements
- Container registry operations
- Multi-platform build orchestration
