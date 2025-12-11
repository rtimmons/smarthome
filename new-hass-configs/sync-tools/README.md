# Home Assistant Bidirectional Sync Tools

This directory contains tools for bidirectional synchronization between the Home Assistant UI and this repository's configuration files. These tools protect against accidental overwrites of user-created content while maintaining the repo-driven deployment model.

## Overview

The sync system addresses the problem where users modify scenes and automations through the Home Assistant web interface, but those changes are lost when deploying from this repository.

## Tools

### 1. `detect-changes.sh`
**Purpose**: Detect when scenes/automations have been modified in the live Home Assistant system.

**Usage**:
```bash
# Direct usage
./sync-tools/detect-changes.sh

# Via Justfile
just detect-changes
```

**What it does**:
- Fetches live configuration files from `homeassistant.local`
- Compares checksums with repository versions
- Identifies UI-created content (scenes/automations with numeric IDs)
- Reports configuration drift

### 2. `pre-deploy-check.sh`
**Purpose**: Pre-deployment protection to prevent accidental overwrites.

**Usage**:
```bash
# Automatically called by 'just deploy'
# Can be bypassed with force mode
FORCE_DEPLOY=true just deploy
```

**What it does**:
- Runs change detection before deployment
- Blocks deployment if conflicts are detected
- Provides clear resolution options
- Creates backups when requested

### 3. `fetch-config.sh`
**Purpose**: Fetch live configuration changes into the repository.

**Usage**:
```bash
# Safe fetch (checks for git changes)
just fetch-config

# Force fetch (ignores git status)
just fetch-config --force
```

**What it does**:
- Checks for uncommitted git changes
- Creates backup of current configuration
- Fetches live configuration from HA system
- **Synchronizes local files** to exactly match the live system
- Shows differences via `git diff` for easy review
- Ensures deployment consistency (deploy after fetch = no-op)

### 4. `reconcile-diff.sh`
**Purpose**: Show diffs and provide reconciliation options for conflicts.

**Usage**:
```bash
# Show diff for specific file
just reconcile scenes.yaml
just reconcile automations.yaml
```

**What it does**:
- Shows intelligent diff using `auggie` CLI if available
- Falls back to standard diff with helpful context
- Provides resolution options
- Suggests merge strategies

## Workflow Integration

### Normal Deployment
```bash
# This now includes automatic sync checking
just deploy
```

If conflicts are detected, deployment is blocked with clear instructions.

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

#### Option 2: Force Deploy (Loses Live Changes)
```bash
# Force deploy, losing live changes
just deploy-force

# Or with backup
just deploy-force --backup
```

#### Option 3: Manual Reconciliation
```bash
# Show detailed diff and options
just reconcile scenes.yaml

# Use auggie for intelligent merging if available
auggie merge scenes.yaml /tmp/live-scenes.yaml > merged-scenes.yaml
```

## Configuration Files Monitored

- `scenes.yaml` - Scene definitions
- `automations.yaml` - Automation rules  
- `scripts.yaml` - Script definitions
- `configuration.yaml` - Main configuration

## Safety Features

### Git Protection
- `fetch-config` checks for uncommitted changes
- Prevents overwriting local modifications
- Can be bypassed with `--force` flag

### Backup System
- Automatic backups before risky operations
- Timestamped backup directories
- Integration with existing backup system

### Change Detection
- Checksum-based comparison
- Whitespace-insensitive comparison
- UI-created content identification

## Environment Variables

- `FORCE_DEPLOY=true` - Skip sync checks during deployment
- `BACKUP_BEFORE_DEPLOY=true` - Create backup before forced deployment
- `FORCE_FLAG=true` - Skip git checks during fetch

## Dependencies

- `rsync` - File synchronization
- `ssh` - Remote access to HA system
- `auggie` - Intelligent diff/merge (optional)
- `git` - Version control integration

## Troubleshooting

### SSH Connection Issues
Ensure you can connect to the HA system:
```bash
ssh root@homeassistant.local "echo 'Connection OK'"
```

### Permission Issues
Make sure scripts are executable:
```bash
chmod +x sync-tools/*.sh
```

### Auggie Not Available
The system falls back to standard diff if `auggie` is not installed.

## Integration Points

- **Root Justfile**: `just fetch-config`, `just detect-changes`, `just reconcile`
- **Config Justfile**: `just sync-check`, `just deploy-force`
- **Deployment**: Automatic pre-deployment checks
- **Git Workflow**: Protection against uncommitted changes
