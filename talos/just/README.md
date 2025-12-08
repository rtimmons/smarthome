# Justfile Libraries for Smarthome Project

This directory contains reusable Justfile libraries that provide common patterns, variables, and helper functions for all addon Justfiles in the smarthome project.

## Usage

To use these libraries in your addon Justfile, import the ones you need:

```just
import "../talos/just/common.just"
import "../talos/just/nvm.just"  # For Node.js addons
```

## 📚 Available Libraries

### `common.just` - Core Functionality
Provides essential variables and helper functions for all addons:

- **Variables**: `repo_root`, `talos_bin`, `build_dir`, `ha_host`, `ha_port`, `ha_user`
- **Helper Functions**: `ensure-talos`, `addon-name`, `validate-addon`, `show-addon-info`
- **Settings**: Bash shell, dotenv loading, positional arguments

### `nvm.just` - Node.js Version Management
Provides Node.js version management functionality:

- **Variables**: `nvm_use`, `nvmrc_file`, `nvm_dir`
- **Recipes**: `nvm-init`, `node-version`, `node-versions`, `node-install`, `node-update-lts`, `clean-nvm`

### `nodejs.just` - Node.js Development (Optional)
Full Node.js development recipes (use with caution due to potential conflicts):

- **Recipes**: `setup`, `dev`, `test`, `lint`, `fmt`, `typecheck`, `build`, `install`, `update`, `audit`

### `python.just` - Python Development (Optional)
Full Python development recipes (use with caution due to potential conflicts):

- **Recipes**: `setup`, `dev`, `test`, `lint`, `fmt`, `typecheck`, `install`, `freeze`, `audit`

### `testing.just` - Testing Patterns (Optional)
Comprehensive testing recipes:

- **Recipes**: `test-all`, `test-unit`, `test-integration`, `test-container`, `test-security`, `test-performance`

## 🏗️ Usage Patterns

### Basic Addon Justfile Structure

```just
# Import shared libraries
import "../talos/just/common.just"
import "../talos/just/nvm.just"  # For Node.js addons

# Addon-specific variables
addon_var := "value"

# Addon-specific recipes
[group: 'setup']
setup:
    @echo "Setting up addon..."
    # Addon-specific setup logic

# Common addon recipes using shared functions
[group: 'build']
ha-addon: ensure-talos validate-addon
    @{{talos_bin}} addon build $(just addon-name)

[group: 'deploy']
deploy: ensure-talos validate-addon
    @{{talos_bin}} addon deploy $(just addon-name)

[group: 'info']
info: validate-addon show-addon-info
```

### Avoiding Recipe Conflicts

**❌ Don't import full development libraries** if your addon defines recipes with the same names:
- `nodejs.just` defines: `setup`, `dev`, `test`, `lint`, `fmt`, etc.
- `python.just` defines: `setup`, `dev`, `test`, `lint`, `fmt`, etc.

**✅ Do use the common library** and define your own recipes:
- Import `common.just` for variables and helper functions
- Define your own `setup`, `test`, `deploy` recipes
- Use helper functions like `ensure-talos`, `validate-addon`

### Recipe Grouping

Use recipe groups to organize functionality:

```just
[group: 'setup']     # Setup and installation
[group: 'dev']       # Development server, watch mode
[group: 'test']      # All testing recipes
[group: 'build']     # Building and compilation
[group: 'deploy']    # Deployment recipes
[group: 'clean']     # Cleanup recipes
[group: 'info']      # Information and status
[group: 'debug']     # Debugging and diagnostics
```

## 🔧 Helper Functions Reference

### `ensure-talos`
Checks if talos binary exists and builds it if needed.

### `addon-name`
Returns the current addon name (directory basename).

### `validate-addon`
Validates that the current directory is an addon (has config.yaml or addon.yaml).

### `show-addon-info`
Displays comprehensive addon information including config details.

## 📋 Best Practices

1. **Always import `common.just`** for basic functionality
2. **Use helper functions** instead of duplicating logic
3. **Group recipes** by functionality using `[group: 'name']`
4. **Add `@` prefix** to suppress command echoing
5. **Use descriptive recipe names** and add comments
6. **Handle errors gracefully** with proper exit codes
7. **Provide user feedback** with echo statements

## 🚀 Migration Guide

To migrate an existing addon Justfile:

1. Add import statement: `import "../talos/just/common.just"`
2. Replace hardcoded paths with variables: `{{talos_bin}}`, `{{repo_root}}`
3. Use helper functions: `ensure-talos`, `validate-addon`
4. Add recipe groups: `[group: 'deploy']`
5. Add `@` prefixes to suppress command echoing
6. Test with `just info` and `just deploy`

## 📖 Examples

See the refactored addon Justfiles for complete examples:
- `grid-dashboard/Justfile` - Node.js addon with Express server
- `sonos-api/Justfile` - Simple Node.js API addon
- `printer/Justfile` - Complex Python addon with visual testing
