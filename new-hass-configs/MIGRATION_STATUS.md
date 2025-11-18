# Migration Status

**Last Updated:** 2025-11-18
**Current Phase:** Phase 2 Complete ✓ | Ready for Phase 3

## Completed

### Phase 1: Setup & Backup ✓
- Backup/restore system working (`just backup`, `just backups`, `just restore`)
- TypeScript generator infrastructure complete
- All type definitions created
- Build pipeline functional

### Phase 2: Device Registry ✓
- Mapped office devices (5 lights, 1 outlet, 1 Z-Wave switch)
- Created 2 office scenes
- Created 2 office automations
- Generator producing valid YAML
- Z-Wave JS event mapping confirmed working

## Current State

### Working Commands
```bash
just fetch      # Fetch current HA config (now protects local directories)
just generate   # Generate YAML from TypeScript
just check      # Validate config (dry-run)
just push       # Deploy to Home Assistant
just backup     # Create timestamped backup
just backups    # List backups
just restore    # Restore from backup
```

### Protected Directories
The `just fetch` command now protects these directories from deletion:
- `config-generator/` - TypeScript source files
- `generated/` - Generated YAML files
- `manual/` - Hand-written YAML overrides
- `backups/` - Local backup snapshots
- `HomeAssistantConfig/` - **LEGACY REFERENCE - DO NOT DELETE**
  - Contains `metaconfig.yaml` with 217 entities, 40+ scenes, 88+ automations
  - Master reference for entire migration
- `MetaHassConfig/` - **LEGACY REFERENCE - DO NOT DELETE**
  - Python-based generator (deprecated)
  - Reference for understanding old generation logic
  - Contains tests and examples
- `.git/` - Git repository

## Device Inventory (from metaconfig.yaml)

### Migrated (Phase 2)
- ✅ Office: 5 lights, 1 outlet, 1 Z-Wave switch

### To Migrate (Phase 3)
From `HomeAssistantConfig/metaconfig.yaml`:

**Bathroom:**
- 4 Hue lights (sauna, shower, vanityleft, vanityright)
- 1 dimmer switch (vanitysconces, node_id: 22)

**Bedroom:**
- 3 Hue lights (mikedesk, dresser, flamingo)
- 2 dimmer switches:
  - bedside (node_id: 3) - double up→high, double down→off
  - closet (node_id: 5) - double up→bathroom_closet_medium, double down→off

**Kitchen:**
- entry_switch_kitchen (node_id: 11) - double up→kitchen_living_high, double down→off
- global_switch_hall (node_id: 15)

*[Additional rooms to be inventoried]*

## Known Issues

### FIXED: Fetch Command Deleting Local Files
- **Issue:** `just fetch` was using `--delete` which removed local-only directories
- **Impact:** Deleted `config-generator/`, `HomeAssistantConfig/`, etc.
- **Fix:** Updated to use `--filter='protect ...'` instead of `--exclude`
- **Status:** ✅ Fixed - verified directories now protected

## Next Steps

### Phase 3: Migrate Remaining Scenes
1. Review complete device inventory in metaconfig.yaml
2. Map all rooms systematically (bathroom, bedroom, kitchen, living, etc.)
3. For each room:
   - Add devices to `devices.ts`
   - Create scenes in `scenes.ts`
   - Create automations in `automations.ts`
   - Generate and test with `just generate && just check`
4. Deploy room-by-room to minimize risk

### Migration Strategy
- Start with simple rooms (fewer devices)
- Test each room before moving to next
- Keep office scenes as reference implementation
- Use `just backup` before each deployment
- Verify scenes work in HA UI before automations

## Files Changed This Session

### Created
- `config-generator/` - Complete TypeScript project
- `generated/` - Generated YAML output
- `manual/` - Manual YAML overrides
- `backups/` - Local backup directory
- `.gitignore` - Ignore generated/backup files

### Modified
- `Justfile` - Added generate, backup, restore commands; fixed fetch protection
- `README.md` - Comprehensive documentation of architecture and workflow
- `config-generator/src/devices.ts` - Office devices mapped
- `config-generator/src/scenes.ts` - Office scenes created
- `config-generator/src/automations.ts` - Office automations created

### Restored
- `HomeAssistantConfig/metaconfig.yaml` - Restored from git after accidental deletion
- `HomeAssistantConfig/configuration.yaml` - Restored from git
- `HomeAssistantConfig/groups.yaml` - Restored from git
- `HomeAssistantConfig/scripts.yaml` - Restored from git
