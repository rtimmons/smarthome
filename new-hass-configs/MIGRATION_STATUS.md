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
just deploy     # Deploy to Home Assistant
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

## Next Steps - Phase 3: Migrate Remaining Scenes

### Immediate Action: Choose a Room to Migrate

**Recommended Order (Simple → Complex):**
1. **Bathroom** (4 lights, 1 switch) - RECOMMENDED FIRST
2. **Bedroom** (3 lights, 2 switches with automations)
3. **Kitchen/Living** (complex - multiple switches)
4. **Remaining rooms**

### Step-by-Step Migration Process

**For Each Room:**

1. **Identify devices in metaconfig.yaml**
   ```bash
   # View the legacy config
   cat HomeAssistantConfig/metaconfig.yaml | grep -A 5 "# Bathroom"
   ```

2. **Get current entity IDs from live HA**
   ```bash
   # Fetch latest config to see current entity names
   just fetch
   # Look at scenes.yaml and automations.yaml for entity IDs
   ```

3. **Map devices to TypeScript**
   - Edit `config-generator/src/devices.ts`
   - Add devices to appropriate section (lights, switches, outlets)
   - For Z-Wave switches, get device_id from current automations.yaml

4. **Find existing scenes**
   - Search metaconfig.yaml for scenes using room devices
   - Note brightness levels, colors, states

5. **Create scenes in TypeScript**
   - Edit `config-generator/src/scenes.ts`
   - Create scene objects referencing devices by logical name
   - Match old scene behavior

6. **Create automations**
   - Edit `config-generator/src/automations.ts`
   - Map old switch events to new Z-Wave JS events
   - Link triggers to new scene names

7. **Generate and validate**
   ```bash
   just generate  # Creates YAML from TypeScript
   # Review generated/scenes.yaml and generated/automations.yaml
   ```

8. **Test configuration**
   ```bash
   just check  # Validates on HA without applying
   ```

9. **Deploy to production**
   ```bash
   just backup "pre-bathroom-migration"  # Safety backup
   just deploy  # Deploy and restart HA
   ```

10. **Verify in Home Assistant UI**
    - Go to Developer Tools > Services
    - Test each scene: `scene.turn_on` with entity_id
    - Test automation triggers (press physical switches)
    - Check HA logs for errors

### Example: Bathroom Migration

**Devices to Map:**
From metaconfig.yaml:
- `bathroom_light_sauna` (hue light)
- `bathroom_light_shower` (hue light)
- `bathroom_light_vanityleft` (hue light)
- `bathroom_light_vanityright` (hue light)
- `bathroom_light_vanitysconces` (dimmer switch, node_id: 22)

**Find Entity IDs:**
After `just fetch`, search scenes.yaml for "bathroom" to find current entity names.

**Create TypeScript entries:**
```typescript
// In config-generator/src/devices.ts
lights: {
  bathroom_sauna: {
    entity: "light.bathroom_light_sauna",  // Get from scenes.yaml
    type: "color_light",
    capabilities: ["brightness", "color_temp"]
  },
  // ... etc
}
```

**Reference Implementation:**
See office devices in `config-generator/src/devices.ts` for examples.

### Migration Checklist Per Room

- [ ] Devices mapped in devices.ts
- [ ] Scenes created in scenes.ts
- [ ] Automations created in automations.ts (if any)
- [ ] Generator runs without errors (`just generate`)
- [ ] Config validates (`just check`)
- [ ] Backup created before deploy
- [ ] Deployed to HA (`just deploy`)
- [ ] Scenes tested in HA UI
- [ ] Automations tested with physical switches
- [ ] No errors in HA logs

### Troubleshooting

**Generator errors:**
- Check device references match keys in devices.ts
- Verify scene references match keys in scenes.ts
- Check TypeScript syntax

**Validation fails:**
- Check entity IDs match current HA entities
- Verify device_id for Z-Wave switches is correct
- Look for typos in entity names

**Scenes don't work:**
- Verify entity IDs in generated YAML match HA
- Check device capabilities match (RGBW vs RGB vs dimmer)
- Test individual entities in HA Developer Tools

**Automations don't trigger:**
- Verify Z-Wave device_id is correct
- Check property_key_name matches (001 = up, 002 = down)
- Monitor HA events: Developer Tools > Events > `zwave_js_value_notification`

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
