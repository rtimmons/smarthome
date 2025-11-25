# Hook Consistency Update

**Date**: 2025-11-25
**Status**: ✅ Completed

## Problem

Previously, only `node-sonos-http-api` had lifecycle hooks (`pre_setup` and `pre_start`). Other add-ons could benefit from these hooks to validate prerequisites and provide better error messages during setup and development.

## Solution

Added consistent lifecycle hooks to all add-ons in the repository.

## Changes Made

### 1. New Hooks Created

#### printer (`printer/local-dev/hooks/`)
- **`pre_setup.sh`** - Validates cairo library availability
  - Checks for Homebrew
  - Verifies cairo is installed via `brew list --formula cairo`
  - Tests pkg-config can find cairo
  - Reports cairo version
  - Provides helpful warnings and installation instructions

- **`pre_start.sh`** - Calls `pre_setup.sh` for consistency

**Example output**:
```
[printer] Validating cairo library availability...
[printer] ✓ cairo library found (version: 1.18.4)
```

#### grid-dashboard (`grid-dashboard/local-dev/hooks/`)
- **`pre_setup.sh`** - Validates Node.js environment
  - Loads nvm if available
  - Checks Node.js version against `.nvmrc`
  - Validates npm is available
  - Reports versions and mismatches

- **`pre_start.sh`** - Calls `pre_setup.sh` for consistency

**Example output**:
```
[grid-dashboard] Validating Node.js environment...
[grid-dashboard] ✓ Node.js version: v20.18.2
[grid-dashboard] ✓ npm version: 10.8.2
```

#### sonos-api (`sonos-api/local-dev/hooks/`)
- **`pre_setup.sh`** - Validates Node.js environment
  - Same validation as grid-dashboard
  - Checks Node.js version against `.nvmrc`
  - Validates npm availability

- **`pre_start.sh`** - Calls `pre_setup.sh` for consistency

**Example output**: Same as grid-dashboard

### 2. Documentation Updates

#### New Documentation
- **`docs/hooks-guide.md`** - Comprehensive lifecycle hooks guide
  - Overview of hook system
  - Available hooks (`pre_setup`, `pre_start`)
  - Implementation details for each add-on
  - Hook best practices
  - Testing instructions
  - Guide for adding new hooks
  - Future hook opportunities

#### Updated Documentation
- **`CLAUDE.md`** - Added "Lifecycle Hooks" section explaining:
  - What hooks are available
  - Which add-ons have hooks
  - What each hook validates
  - Link to detailed hooks guide

- **`talos/docs/IMPROVEMENTS.md`** - Updated:
  - Changed "Hook usage inconsistent" from ⚠️ to ✅
  - Added "Expand Hook Usage" as ✅ COMPLETED
  - Listed all new hooks and what they check

- **`talos/docs/USAGE.md`** - Added link to hooks guide in "See Also"

- **`talos/docs/ARCHITECTURE.md`** - Added "See Also" section with link to hooks guide

### 3. Testing

All hooks tested successfully:

```bash
$ ./talos/build/bin/talos hook run printer pre_setup
[printer] Validating cairo library availability...
[printer] ✓ cairo library found (version: 1.18.4)

$ ./talos/build/bin/talos hook run grid-dashboard pre_setup
[grid-dashboard] Validating Node.js environment...
[grid-dashboard] ✓ Node.js version: v20.18.2
[grid-dashboard] ✓ npm version: 10.8.2

$ ./talos/build/bin/talos hook run sonos-api pre_setup
[sonos-api] Validating Node.js environment...
[sonos-api] ✓ Node.js version: v20.18.2
[sonos-api] ✓ npm version: 10.8.2
```

## Benefits

### 1. Early Error Detection
Hooks catch environment issues during `just setup` before they cause cryptic failures during dependency installation:

- **printer**: Detects missing cairo before `pip install cairocffi` fails
- **grid-dashboard**: Detects Node.js version mismatch before npm install
- **sonos-api**: Detects Node.js version mismatch before npm install
- **node-sonos-http-api**: Detects VPN interference before Sonos discovery fails

### 2. Better Error Messages
Hooks provide actionable error messages:

**Before** (without hooks):
```
ERROR: Command errored out with exit status 1:
  building 'cairocffi._ffi' extension
  xcrun: error: SDK "macosx" cannot be located
  [hundreds of lines of compiler errors...]
```

**After** (with hooks):
```
[printer] WARNING: cairo library not found.
[printer] The setup process will install it via Homebrew.
[printer] If you want to install it now: brew install cairo
```

### 3. Consistent Pattern
All add-ons now follow the same pattern:
- `pre_setup.sh` - Validate environment
- `pre_start.sh` - Call `pre_setup.sh`
- Helpful warnings with installation instructions
- Non-blocking (warnings) unless critical error

### 4. Developer Experience
New developers get immediate, actionable feedback:
- "Node.js version mismatch" with exact versions
- "Rerun just setup (or bash talos/scripts/nvm_use.sh) to install the pinned Node version without touching your shell profile"
- Links to documentation when needed

### 5. Documentation
Comprehensive guide (`docs/hooks-guide.md`) enables:
- Understanding what each hook does
- Adding new hooks to other add-ons
- Following best practices
- Testing hooks during development

## Hook Architecture

### Invocation Flow

```
User runs: just setup
    ↓
talos/setup_dev_env.sh
    ↓
Runs: talos hook run <addon> pre_setup --if-missing-ok
    ↓
Executes: <addon>/local-dev/hooks/pre_setup.sh
    ↓
Output: [addon] Validation messages...
    ↓
Exit code: 0 (success/warning) or 1 (error)
```

### Hook Execution

```bash
# talos/src/talos/hooks.py
def run_hook(addon: str, hook: str, if_missing_ok: bool = False) -> bool:
    hook_path = _resolve_hook(addon_dir, hook)  # Tries: hook, hook.sh, hook.py
    if not hook_path:
        return if_missing_ok
    result = subprocess.run([str(hook_path)], cwd=str(addon_dir))
    return result.returncode == 0
```

## Consistency Achieved

### Before
- ❌ Only 1 of 4 add-ons had hooks
- ❌ No documentation on how to add hooks
- ❌ No examples for different add-on types
- ❌ Setup errors were cryptic and late

### After
- ✅ All 4 add-ons have hooks
- ✅ Comprehensive hooks guide with examples
- ✅ Consistent pattern across all hooks
- ✅ Early validation with helpful messages
- ✅ Well-documented and easily extensible

## Future Hook Opportunities

Documented in `docs/hooks-guide.md`:

- `post_setup` - Verify installation succeeded
- `pre_build` - Validate before Docker build
- `post_build` - Test Docker image
- `pre_deploy` - Validate before deployment
- `post_deploy` - Verify deployment success

## Files Modified/Created

### Created
- `printer/local-dev/hooks/pre_setup.sh` (36 lines)
- `printer/local-dev/hooks/pre_start.sh` (4 lines)
- `grid-dashboard/local-dev/hooks/pre_setup.sh` (60 lines)
- `grid-dashboard/local-dev/hooks/pre_start.sh` (4 lines)
- `sonos-api/local-dev/hooks/pre_setup.sh` (60 lines)
- `sonos-api/local-dev/hooks/pre_start.sh` (4 lines)
- `docs/hooks-guide.md` (493 lines)
- `docs/HOOK-CONSISTENCY-UPDATE.md` (this file)

### Modified
- `CLAUDE.md` - Added Lifecycle Hooks section
- `talos/docs/IMPROVEMENTS.md` - Updated hook status
- `talos/docs/USAGE.md` - Added hooks guide link
- `talos/docs/ARCHITECTURE.md` - Added hooks guide link

## Total Impact

- **8 new files created** (661 lines)
- **4 documentation files updated**
- **All add-ons now consistent**
- **Better developer experience**
- **Comprehensive documentation**

## Verification

Test that all hooks work:

```bash
# Test all add-on hooks
for addon in node-sonos-http-api printer grid-dashboard sonos-api; do
  echo "Testing $addon..."
  ./talos/build/bin/talos hook run "$addon" pre_setup --if-missing-ok
done

# Run full setup (hooks run automatically)
just setup

# Run dev (hooks run before each service starts)
just dev
```

## Conclusion

The hook system is now **consistent, well-documented, and useful across all add-ons**. This improvement makes the development environment more robust and provides better error messages to developers.

The pattern is established and documented, making it easy to:
1. Add hooks to new add-ons
2. Add new hook types (post_setup, pre_build, etc.)
3. Customize validation for specific needs
4. Debug environment issues early
