# Home Assistant Configuration Sync

## Overview

The bidirectional sync system protects against accidental overwrites of user-created content while maintaining the repo-driven deployment model. It addresses the problem where users modify scenes and automations through the Home Assistant web interface, but those changes are lost when deploying from this repository.

## Quick Start

```bash
# Normal deployment (now includes automatic sync checking)
just deploy

# If conflicts are detected, you have options:
just fetch-config          # Fetch UI changes into repo (recommended)
just deploy-force          # Force deploy, losing UI changes
just deploy-force --backup # Force deploy with backup
just reconcile scenes.yaml # Manual conflict resolution
```

## Architecture

### Change Detection
The system compares live Home Assistant configuration files with repository versions using:
- Checksum-based comparison (whitespace-insensitive)
- UI-created content identification (scenes/automations with numeric IDs)
- Comprehensive monitoring of scenes.yaml, automations.yaml, scripts.yaml, configuration.yaml

### Pre-deployment Protection
- Automatically runs before `just deploy`
- Blocks deployment if configuration drift is detected
- Provides clear resolution options with examples
- Shows deployment summary with file statistics

### Configuration Fetching
- Safely pulls live changes into repository
- Git protection: prevents overwriting uncommitted changes
- Creates automatic backups before applying changes
- Preserves UI-created content and manual configurations

## Workflow Integration

### Protected Deployment (Default)
```bash
just deploy
```
This now includes automatic sync checking. If conflicts are detected, deployment is blocked with clear instructions.

### Handling Conflicts

#### Option 1: Fetch Live Changes (Recommended)
```bash
# Fetch changes from live system
just fetch-config

# Review changes
git diff

# Commit changes
git add . && git commit -m "Sync live HA changes"

# Deploy normally
just deploy
```

#### Option 2: Force Deploy
```bash
# Force deploy, losing live changes
just deploy-force

# Or with backup for safety
just deploy-force --backup
```

#### Option 3: Manual Reconciliation
```bash
# Show detailed diff and resolution options
just reconcile scenes.yaml
just reconcile automations.yaml

# Use auggie for intelligent merging if available
auggie merge scenes.yaml /tmp/live-scenes.yaml > merged-scenes.yaml
```

## Safety Features

### Git Protection
- `fetch-config` checks for uncommitted changes before proceeding
- Prevents overwriting local modifications
- Can be bypassed with `--force` flag

### Backup System
- Automatic timestamped backups before risky operations
- Integration with existing backup system in `new-hass-configs/Justfile`
- Safety backups during restore operations
- Backup tracking via `.last-backup` file (local runtime state)

### Change Detection
- Whitespace-insensitive file comparison
- UI-created content identification
- Comprehensive file monitoring

## Commands Reference

### Root Justfile Commands
```bash
just fetch-config [--force]  # Fetch live HA config changes
just detect-changes          # Check for configuration drift
just reconcile FILE          # Show diff and resolution options
just deploy-force [--backup] # Force deploy with optional backup
```

### Config Justfile Commands
```bash
cd new-hass-configs
just sync-check             # Pre-deployment protection check
just detect-changes         # Change detection
just fetch-config [--force] # Configuration fetching
just reconcile FILE         # Diff reconciliation
just deploy-force [--backup] # Force deployment
```

### Aliases
- `fc` → `fetch-config`
- `dc` → `detect-changes`  
- `df` → `deploy-force`

## Environment Variables

- `FORCE_DEPLOY=true` - Skip sync checks during deployment
- `BACKUP_BEFORE_DEPLOY=true` - Create backup before forced deployment
- `FORCE_FLAG=true` - Skip git checks during fetch

## Configuration Files Monitored

- `scenes.yaml` - Scene definitions
- `automations.yaml` - Automation rules
- `scripts.yaml` - Script definitions
- `configuration.yaml` - Main configuration

## Dependencies

- `rsync` - File synchronization
- `ssh` - Remote access to HA system (`root@homeassistant.local`)
- `auggie` - Intelligent diff/merge (optional, falls back to standard diff)
- `git` - Version control integration

## Implementation Details

### File Structure
```
new-hass-configs/
├── sync-tools/
│   ├── README.md              # Detailed implementation docs
│   ├── detect-changes.sh      # Change detection engine
│   ├── pre-deploy-check.sh    # Pre-deployment protection
│   ├── fetch-config.sh        # Configuration fetching
│   ├── reconcile-diff.sh      # Diff reconciliation
│   └── test-sync.sh          # Validation test suite
└── .last-backup              # Tracks most recent backup (local state)
```

### Integration Points
- **Deployment**: `just deploy` → `sync-check` → `pre-deploy-check.sh`
- **Change Detection**: Automatic before deployment, manual via `detect-changes`
- **Configuration Management**: Integrates with existing config-generator system
- **Backup System**: Uses existing backup infrastructure with timestamped directories

## Troubleshooting

### SSH Connection Issues
Ensure you can connect to the HA system:
```bash
ssh root@homeassistant.local "echo 'Connection OK'"
```

### Permission Issues
Make sure scripts are executable:
```bash
chmod +x new-hass-configs/sync-tools/*.sh
```

### Testing the System
Run the validation test suite:
```bash
cd new-hass-configs
./sync-tools/test-sync.sh
```

## Related Documentation

- [Local Development](local-development.md) - Development environment setup
- [Home Assistant Configuration](../../new-hass-configs/README.md) - Configuration structure
- [Deployment Guide](../deployment/deployment-system-guide.md) - Deployment workflows
- [Sync Tools README](../../new-hass-configs/sync-tools/README.md) - Implementation details
