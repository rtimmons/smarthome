# Lifecycle Hooks Guide

This guide documents the lifecycle hooks available in the smarthome repository and how each add-on uses them.

## Overview

Lifecycle hooks are executable scripts that add-ons can provide to participate in repository-wide workflows. They enable add-ons to validate **add-on-specific** prerequisites without modifying the core talos tooling.

## Design Principle: DRY (Don't Repeat Yourself)

**Important**: Hooks should only validate concerns that are **specific to an individual add-on**, not common runtime environment validation.

### What Talos Already Handles

The `talos/setup_dev_env.sh` script already validates and configures:

✅ **Homebrew** - Installs if missing
✅ **System libraries** - Installs cairo for printer service
✅ **nvm** - Installs and configures Node Version Manager
✅ **Node.js** - Installs correct version from `.nvmrc`
✅ **pyenv** - Installs and configures Python Version Manager
✅ **Python** - Installs correct version from `.python-version`
✅ **uv** - Installs Python package manager

**These validations should NOT be duplicated in add-on hooks.**

### What Hooks Should Validate

Hooks should only check add-on-specific concerns:

✅ **Add-on-specific system dependencies** (e.g., printer's pkg-config cairo configuration)
✅ **Add-on-specific network requirements** (e.g., node-sonos-http-api's multicast reachability)
✅ **Add-on-specific service availability** (e.g., external APIs, databases)
✅ **Add-on-specific configuration** (e.g., environment variables, config files)

❌ **NOT**: Node.js/npm version (talos handles this)
❌ **NOT**: Python/pip version (talos handles this)
❌ **NOT**: General system tools (talos handles this)

## Hook Locations

Hooks live in each add-on directory:
```
<addon>/local-dev/hooks/
├── pre_setup.sh     # Run during 'just setup'
└── pre_start.sh     # Run before starting service in 'just dev'
```

## Available Hooks

### `pre_setup`
**When**: Run during `just setup` before installing dependencies

**Purpose**: Validate add-on-specific prerequisites
- Check for add-on-specific system libraries or configurations
- Test add-on-specific network connectivity
- Validate add-on-specific external services

**Exit Codes**:
- `0` - Validation passed (or warning displayed but not blocking)
- `1` - Validation failed with error (blocks setup)
- `2` - Special error (e.g., cannot create socket for testing)

### `pre_start`
**When**: Run before starting a service in `just dev`

**Purpose**: Ensure service can start successfully
- Re-validate add-on-specific prerequisites from `pre_setup`
- Check add-on-specific runtime requirements

**Exit Codes**:
- `0` - Service can start
- Non-zero - Service cannot start (displayed in dev output)

## Hook Implementations by Add-on

### node-sonos-http-api

**Hooks**: `pre_setup.sh`, `pre_start.sh`

**Add-on-specific validation**:
- ✅ Sonos multicast/broadcast network reachability
- ✅ SSDP probe packet transmission (specific to Sonos discovery protocol)
- ✅ VPN/ZeroTrust client interference detection
- ✅ macOS Private Wi-Fi Address feature interference

**Why this is add-on-specific**: Sonos discovery requires special multicast networking that can be blocked by VPN clients or macOS privacy features. This is unique to Sonos integration and not a general Node.js concern.

**Implementation**: Uses Node.js UDP socket to attempt SSDP packet transmission

**Example output** (success):
```
[node-sonos-http-api] Validating Sonos discovery reachability...
[OK] SSDP probe (multicast) sent via 239.255.255.250
[OK] SSDP probe (broadcast) sent via 255.255.255.255
```

**Example output** (failure):
```
[FAIL] Unable to send SSDP probe (multicast) to 239.255.255.250: EHOSTUNREACH

Sonos discovery failed before the HTTP API even starts. This typically indicates
a VPN/ZeroTrust client (Tailscale, WARP, corporate VPN) or macOS privacy features
(Private Wi-Fi Address / Limit IP Address Tracking) that inject utun routes and
block multicast/broadcast traffic on macOS.
```

**Files**:
- `node-sonos-http-api/local-dev/hooks/pre_setup.sh` - Wrapper script
- `node-sonos-http-api/tools/check_sonos_multicast.js` - Actual validation logic

### printer

**Hooks**: `pre_setup.sh`, `pre_start.sh`

**Add-on-specific validation**:
- ✅ pkg-config can find cairo (specific to cairocffi Python binding)
- ✅ PKG_CONFIG_PATH is configured correctly

**Why this is add-on-specific**: While talos installs cairo via Homebrew, cairocffi requires pkg-config to find it. This validates the pkg-config configuration is correct for the Python binding.

**Note**: The hook does NOT install cairo (talos does that). It only validates configuration.

**Implementation**: Checks pkg-config configuration for cairo

**Example output** (success):
```
[printer] Validating cairo configuration for cairocffi...
[printer] ✓ cairo library configured (version: 1.18.4)
```

**Example output** (warning):
```
[printer] Validating cairo configuration for cairocffi...
[printer] WARNING: pkg-config cannot find cairo
[printer] If setup already ran, this might indicate a PATH issue
```

**Files**:
- `printer/local-dev/hooks/pre_setup.sh` - Configuration validation
- `printer/local-dev/hooks/pre_start.sh` - Calls pre_setup

### grid-dashboard

**Hooks**: None

**Why no hooks**: This add-on only requires Node.js/npm, which talos already validates and configures. No add-on-specific validation needed.

### sonos-api

**Hooks**: None

**Why no hooks**: This add-on only requires Node.js/npm, which talos already validates and configures. No add-on-specific validation needed.

## Hook Best Practices

### 1. Don't Duplicate Talos Validation

❌ **Bad** - Checking Node.js version (talos does this):
```bash
# DON'T DO THIS
if [ "$current_version" != "$required_version" ]; then
    echo "Node.js version mismatch"
    exit 1
fi
```

✅ **Good** - Checking add-on-specific requirement:
```bash
# DO THIS - add-on-specific validation
if ! can_send_multicast_packets; then
    echo "Multicast networking blocked by VPN"
    exit 1
fi
```

### 2. Add Comments Explaining Add-on Specificity

```bash
#!/usr/bin/env bash
# Pre-setup validation for printer service
# Note: Basic cairo installation is handled by talos/setup_dev_env.sh
# This hook only validates cairo is functional for Python/cairocffi
```

### 3. Fail Gracefully

```bash
if ! check_addon_specific_thing; then
    echo "[addon] ERROR: Specific requirement not met" >&2
    echo "[addon] This is unique to this add-on because..." >&2
    exit 1
fi
```

### 4. Warn Without Blocking

```bash
if ! check_optional_thing; then
    echo "[addon] WARNING: Optional feature won't work" >&2
    exit 0  # Don't block setup
fi
```

### 5. Use Descriptive Prefixes

```bash
echo "[my-addon] Validating add-on-specific requirement..." >&2
```

### 6. Make Hooks Executable

```bash
chmod +x <addon>/local-dev/hooks/pre_setup.sh
chmod +x <addon>/local-dev/hooks/pre_start.sh
```

## Examples of Good vs Bad Hook Usage

### ❌ Bad: Duplicating Talos Validation

```bash
# DON'T - talos already does this
echo "Checking Node.js version..."
if ! node --version | grep -q "v20.18.2"; then
    echo "Wrong Node.js version"
    exit 1
fi
```

### ✅ Good: Add-on-Specific Validation

```bash
# DO - this is specific to Sonos
echo "Checking Sonos multicast reachability..."
if ! can_send_ssdp_probes; then
    echo "Multicast blocked - check VPN settings"
    exit 1
fi
```

### ❌ Bad: Installing System Dependencies

```bash
# DON'T - talos handles system dependencies
if ! brew list cairo; then
    brew install cairo
fi
```

### ✅ Good: Validating Add-on-Specific Configuration

```bash
# DO - validate configuration for this specific library
if ! pkg-config --exists cairo; then
    echo "pkg-config can't find cairo - PATH issue?"
    exit 1
fi
```

## Testing Hooks

### Test Individual Hook

```bash
# With talos CLI
talos hook run <addon> <hook>

# Allow missing hooks
talos hook run <addon> <hook> --if-missing-ok

# Direct execution
./<addon>/local-dev/hooks/pre_setup.sh
```

### Test During Setup

```bash
just setup
# Watch for hook output during setup process
```

### Test During Dev

```bash
just dev
# Hooks run before each service starts
```

## When to Add a Hook

Ask yourself:

1. **Is this validation specific to my add-on?**
   - ✅ Yes → Consider a hook
   - ❌ No → Let talos handle it

2. **Does talos already validate this?**
   - ✅ Yes → Don't duplicate it
   - ❌ No → Good candidate for a hook

3. **Is this a runtime behavior unique to my add-on?**
   - ✅ Yes → Perfect for a hook
   - ❌ No → Probably not needed

## Adding New Hooks

### 1. Create Hook Directory

```bash
mkdir -p my-addon/local-dev/hooks
```

### 2. Create Hook Script

```bash
cat > my-addon/local-dev/hooks/pre_setup.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

# Pre-setup validation for my-addon
# Note: General runtime validation (Node/Python) is handled by talos
# This hook only validates add-on-specific requirements

echo "[my-addon] Validating add-on-specific prerequisites..." >&2

# Your add-on-specific validation here

echo "[my-addon] ✓ Add-on-specific validation passed" >&2
exit 0
EOF
```

### 3. Make It Executable

```bash
chmod +x my-addon/local-dev/hooks/pre_setup.sh
```

### 4. Create pre_start Hook

```bash
cat > my-addon/local-dev/hooks/pre_start.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

"$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/pre_setup.sh"
EOF

chmod +x my-addon/local-dev/hooks/pre_start.sh
```

### 5. Test the Hook

```bash
talos hook run my-addon pre_setup
```

## Current Hook Status

| Add-on | Has Hooks | Validates | Why |
|--------|-----------|-----------|-----|
| node-sonos-http-api | ✅ | Multicast networking | Sonos-specific SSDP protocol |
| printer | ✅ | pkg-config cairo config | cairocffi Python binding requirement |
| grid-dashboard | ❌ | N/A | Only needs Node.js (talos handles) |
| sonos-api | ❌ | N/A | Only needs Node.js (talos handles) |

## Future Hook Opportunities

Only add these if there are **add-on-specific** validations needed:

### `post_setup`
Run after dependency installation to:
- Verify add-on-specific installation succeeded
- Run add-on-specific post-install configuration
- Generate add-on-specific required files

### `pre_build`
Run before building Docker image to:
- Validate add-on-specific source files
- Run add-on-specific linters
- Generate add-on-specific build artifacts

### `post_build`
Run after building Docker image to:
- Verify add-on-specific image contents
- Test add-on-specific image capabilities

### `pre_deploy`
Run before deploying to Home Assistant to:
- Validate add-on-specific deployment requirements
- Check add-on-specific external services

### `post_deploy`
Run after deploying to Home Assistant to:
- Verify add-on-specific functionality
- Run add-on-specific smoke tests

## See Also

- [talos/docs/ARCHITECTURE.md](../talos/docs/ARCHITECTURE.md) - Lifecycle hooks architecture
- [talos/docs/USAGE.md](../talos/docs/USAGE.md) - Hook command usage
- [../setup/dev-setup.md](../setup/dev-setup.md) - Development environment setup (uses hooks)
- [../AGENTS.md](../AGENTS.md) - Repository development guide
