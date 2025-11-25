# Hook Refactoring: DRY Principle Applied

**Date**: 2025-11-25
**Status**: ✅ Completed

## Problem

The initial hook implementation duplicated validation logic that talos already handles:
- `grid-dashboard` and `sonos-api` hooks checked Node.js versions
- `printer` hook checked cairo installation
- All of these validations are already done by `talos/setup_dev_env.sh`

This violated the DRY (Don't Repeat Yourself) principle and would scale poorly as more Node.js or Python add-ons are added.

## Design Principle

**Hooks should only validate add-on-specific concerns, not general runtime environment.**

### What Talos Handles (Don't Duplicate)

The `talos/setup_dev_env.sh` script already:
- ✅ Installs and configures Homebrew
- ✅ Installs system libraries (including cairo)
- ✅ Installs and configures nvm
- ✅ Installs correct Node.js version from `.nvmrc`
- ✅ Installs and configures pyenv
- ✅ Installs correct Python version from `.python-version`
- ✅ Installs uv package manager

### What Hooks Should Validate (Add-on-Specific Only)

Hooks should only check:
- ✅ Add-on-specific system dependencies or configurations
- ✅ Add-on-specific network requirements
- ✅ Add-on-specific service availability
- ✅ Add-on-specific runtime behaviors

## Changes Made

### Removed Redundant Hooks

**Deleted**:
- `grid-dashboard/local-dev/hooks/pre_setup.sh` (60 lines) - Duplicated Node.js validation
- `grid-dashboard/local-dev/hooks/pre_start.sh` (4 lines) - Wrapper
- `sonos-api/local-dev/hooks/pre_setup.sh` (60 lines) - Duplicated Node.js validation
- `sonos-api/local-dev/hooks/pre_start.sh` (4 lines) - Wrapper

**Total removed**: 128 lines of redundant code

### Refactored Add-on-Specific Hooks

**`printer/local-dev/hooks/pre_setup.sh`** - Simplified from 36 → 27 lines
- **Before**: Checked Homebrew, installed cairo, validated pkg-config
- **After**: Only validates pkg-config configuration (cairo installation is talos's job)
- **Add-on-specific**: cairocffi Python binding requires pkg-config to find cairo

**`node-sonos-http-api/local-dev/hooks/pre_setup.sh`** - No changes
- **Validates**: Multicast network reachability for SSDP protocol
- **Add-on-specific**: Sonos discovery requires special multicast networking

### Updated Documentation

**Comprehensive rewrite** of `docs/hooks-guide.md`:
- Added "Design Principle: DRY" section
- Listed what talos already handles
- Listed what hooks should validate
- Provided "Good vs Bad" examples
- Added "When to Add a Hook" decision tree
- Updated hook status table

**Updated**:
- `CLAUDE.md` - Clarified hook design principle
- `talos/docs/IMPROVEMENTS.md` - Updated hook implementation description
- All cross-references updated

## Before vs After

### Before (Duplicated Logic)

```bash
# grid-dashboard/local-dev/hooks/pre_setup.sh (DELETED)
required_version=$(cat .nvmrc)
current_version=$(node --version)
if [ "$current_version" != "$required_version" ]; then
    echo "Node.js version mismatch"
    # ...duplicates what talos already does
fi
```

### After (Add-on-Specific Only)

```bash
# printer/local-dev/hooks/pre_setup.sh (SIMPLIFIED)
# Note: Basic cairo installation is handled by talos/setup_dev_env.sh
# This hook only validates cairo is functional for Python/cairocffi
if ! pkg-config --exists cairo; then
    echo "pkg-config can't find cairo - PATH issue?"
fi
```

## Current Hook Status

| Add-on | Has Hooks | Validates | Reason |
|--------|-----------|-----------|--------|
| node-sonos-http-api | ✅ | Multicast networking | SSDP protocol requirement |
| printer | ✅ | pkg-config cairo config | cairocffi Python binding |
| grid-dashboard | ❌ | N/A | Only needs Node.js (talos handles) |
| sonos-api | ❌ | N/A | Only needs Node.js (talos handles) |

## Testing Results

All hooks tested successfully:

```bash
$ ./talos/build/bin/talos hook run printer pre_setup
[printer] Validating cairo configuration for cairocffi...
[printer] ✓ cairo library configured (version: 1.18.4)

$ ./talos/build/bin/talos hook run node-sonos-http-api pre_setup
[OK] SSDP probe (multicast) sent via 239.255.255.250
[OK] SSDP probe (broadcast) sent via 255.255.255.255

$ ./talos/build/bin/talos hook run grid-dashboard pre_setup --if-missing-ok
(no output - no hook, which is correct)

$ ./talos/build/bin/talos hook run sonos-api pre_setup --if-missing-ok
(no output - no hook, which is correct)
```

## Benefits

### 1. No Code Duplication
- ❌ Before: 128 lines of duplicated validation logic
- ✅ After: 0 lines of duplication

### 2. Scalability
- ❌ Before: Each new Node.js add-on would need 60+ lines of hook code
- ✅ After: New Node.js add-ons need zero hook code (unless they have add-on-specific needs)

### 3. Maintainability
- ❌ Before: Update Node.js validation logic in 3+ places
- ✅ After: Update once in talos, all add-ons benefit

### 4. Clarity
- ❌ Before: Unclear what's add-on-specific vs general
- ✅ After: Hooks clearly document why they exist

### 5. Performance
- ❌ Before: Redundant checks during setup
- ✅ After: Each check runs once

## Decision Tree for Future Hooks

When considering a new hook, ask:

1. **Does talos already handle this?**
   - ✅ Yes → Don't add hook
   - ❌ No → Continue to #2

2. **Is this specific to this add-on?**
   - ✅ Yes → Good candidate for hook
   - ❌ No → Add to talos instead

3. **Is this a runtime behavior unique to this add-on?**
   - ✅ Yes → Perfect for hook
   - ❌ No → Probably not needed

## Examples for Future Add-ons

### Example 1: New Node.js Add-on
**Question**: Should I add hooks to validate Node.js version?
**Answer**: ❌ No - talos already does this.

### Example 2: Add-on Requiring MongoDB
**Question**: Should I add a hook to check MongoDB connection?
**Answer**: ✅ Yes - this is add-on-specific.

```bash
# my-addon/local-dev/hooks/pre_setup.sh
if ! curl -s http://localhost:27017 > /dev/null; then
    echo "[my-addon] ERROR: MongoDB not running"
    echo "[my-addon] Start it with: brew services start mongodb-community"
    exit 1
fi
```

### Example 3: Add-on Requiring Specific Python Package
**Question**: Should I add a hook to check if the package is installed?
**Answer**: ❌ No - `just setup` will install it via `uv sync`.

### Example 4: Add-on Requiring External API Key
**Question**: Should I add a hook to check for API key?
**Answer**: ✅ Yes - this is add-on-specific configuration.

```bash
# my-addon/local-dev/hooks/pre_setup.sh
if [ -z "${MY_API_KEY:-}" ]; then
    echo "[my-addon] ERROR: MY_API_KEY environment variable not set"
    echo "[my-addon] Get your key from: https://example.com/api-keys"
    exit 1
fi
```

## Documentation Updates

### Files Modified
- `docs/hooks-guide.md` - Complete rewrite with DRY principles
- `CLAUDE.md` - Updated hook description
- `talos/docs/IMPROVEMENTS.md` - Updated hook implementation status
- `docs/HOOK-REFACTORING-DRY.md` - This document

### Files Deleted
- `grid-dashboard/local-dev/hooks/pre_setup.sh`
- `grid-dashboard/local-dev/hooks/pre_start.sh`
- `sonos-api/local-dev/hooks/pre_setup.sh`
- `sonos-api/local-dev/hooks/pre_start.sh`

### Files Simplified
- `printer/local-dev/hooks/pre_setup.sh` - 36 → 27 lines

## Impact Summary

**Code reduction**: 137 lines removed (128 deleted + 9 simplified)
**Principle established**: DRY for hooks clearly documented
**Scalability improved**: New add-ons need minimal/no hooks
**Maintainability improved**: Single source of truth for runtime validation
**Documentation improved**: Clear guidance on when to add hooks

## Conclusion

The refactoring successfully applies the DRY principle to lifecycle hooks by:

1. **Removing duplication**: Deleted redundant Node.js validation from 2 add-ons
2. **Simplifying existing hooks**: Reduced printer hook to only add-on-specific concerns
3. **Documenting the principle**: Clear guidance for future add-ons
4. **Establishing the pattern**: Only 2 of 4 add-ons need hooks, both for truly add-on-specific reasons

The hook system now clearly separates concerns:
- **Talos**: General runtime environment (Node.js, Python, system dependencies)
- **Hooks**: Add-on-specific validations (multicast networking, pkg-config configuration, external services)

This pattern will scale cleanly as the repository grows.
