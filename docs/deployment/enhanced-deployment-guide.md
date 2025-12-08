# Enhanced Deployment System Guide

This guide covers the improved `just deploy` workflow with enhanced error handling, **much cleaner output**, and deployment safety features. The deployment system now provides professional, concise output by default with verbose modes available when detailed information is needed.

## Quick Start

### Basic Deployment
```bash
# Deploy all add-ons with enhanced features
just deploy

# Deploy specific add-on
just deploy grid-dashboard

# Deploy with verbose output for troubleshooting
just deploy-verbose

# Preview deployment without making changes (clean, concise output)
just deploy-dry-run

# Detailed preview with full deployment plans
just deploy-dry-run-verbose
```

### Advanced Options
```bash
# Deploy with verbose output
just deploy all --verbose

# Dry run to see what would be deployed
just deploy all --dry-run

# Deploy specific add-ons with options
just deploy grid-dashboard sonos-api --verbose
```

## Key Improvements

### 1. Enhanced Error Handling
- **Structured errors** with context and troubleshooting steps
- **Immediate error surfacing** with clear next steps
- **Deployment validation** before making any changes
- **Automatic rollback** on critical failures

### 2. Output Optimization ⭐ **MAJOR IMPROVEMENT - COMPLETED**
- **✅ Clean, professional output** - Eliminated verbose nvm initialization messages, npm output, and raw shell commands
- **✅ Concise default output** showing only essential progress and status information
- **✅ Verbose mode** (`--verbose`) for detailed troubleshooting when needed
- **✅ Progress indicators** with real-time status updates and emoji
- **✅ Rich error messages** with actionable guidance and troubleshooting steps
- **✅ Suppressed build output** - Test commands, build steps, and container operations run silently unless in verbose mode

### 3. Deployment Safety
- **Pre-deployment validation** of SSH connectivity and system health
- **Atomic operations** - all add-ons succeed or all fail
- **Health checks** after deployment to verify success
- **Backup and recovery** capabilities

### 4. Architecture Improvements
- **Single SSH session** for all operations (reduced overhead)
- **Enhanced remote scripts** with proper error handling
- **Batch deployment** with coordinated operations
- **Deployment state tracking** for recovery

## Command Reference

### Main Commands
- `just deploy [addon]` - Enhanced deployment with safety checks
- `just deploy-verbose [addon]` - Deployment with detailed output
- `just deploy-dry-run [addon]` - Preview deployment without changes

### Talos Commands
- `talos addon deploy <name>` - Deploy single add-on
- `talos addons deploy [names...]` - Deploy multiple add-ons
- `talos addons deploy --verbose` - Verbose batch deployment
- `talos addons deploy --dry-run` - Dry run batch deployment

## Error Handling

### Error Types
1. **SSH_CONNECTION_FAILED** - Cannot connect to Home Assistant
2. **HA_CORE_NOT_RUNNING** - Home Assistant core is not running
3. **UPLOAD_FAILED** - Failed to upload add-on files
4. **REMOTE_DEPLOYMENT_FAILED** - Deployment failed on remote system
5. **ADDON_START_FAILED** - Add-on failed to start after installation

### Troubleshooting Steps
Each error includes specific troubleshooting steps:
- Check system connectivity and health
- Verify add-on configuration and logs
- Validate Home Assistant system status
- Review deployment logs for details

### Example Error Output
```
❌ Deployment Error: REMOTE_DEPLOYMENT_FAILED

Details:
  Failed to deploy grid-dashboard on remote system

Context:
  • addon: grid-dashboard
  • host: homeassistant.local
  • exit_code: 1

Troubleshooting Steps:
  1. Check add-on logs: ha addons logs local_grid_dashboard
  2. Check add-on info: ha addons info local_grid_dashboard
  3. Check supervisor logs: ha supervisor logs
  4. Rebuild add-on: just ha-addon grid-dashboard
  5. Check Home Assistant system health

Timestamp: 2024-12-07T12:34:56.789Z
```

## Deployment Process

### Phase 1: Pre-deployment Validation
- SSH connectivity test
- Home Assistant health check
- Disk space verification
- System prerequisites validation

### Phase 2: Build and Preparation
- Build all add-ons locally
- Run pre-deployment tests
- Validate add-on configurations
- Create deployment package

### Phase 3: Deployment Execution
- Upload add-on files
- Stop existing add-ons safely
- Install/rebuild add-ons
- Configure add-on options
- Start add-ons with health checks

### Phase 4: Post-deployment Verification
- Verify add-ons are running
- Check ingress endpoints
- Validate inter-service communication
- Generate deployment summary

## Configuration

### Environment Variables
- `HA_HOST` - Home Assistant hostname (default: homeassistant.local)
- `HA_PORT` - SSH port (default: 22)
- `HA_USER` - SSH user (default: root)
- `SUPERVISOR_TOKEN` - Home Assistant supervisor token (for API access)

### Add-on Configuration
Add-ons can specify deployment-specific configuration in `addon.yaml`:
```yaml
deployment:
  health_check_timeout: 30
  requires_restart: true
  dependencies: ["sonos-api"]
```

## Monitoring and Logs

### Deployment Logs
Logs are stored in `/tmp/deployment-<timestamp>.log` with:
- All executed commands and output
- Timing information for each phase
- Error details and context
- System health information

### Health Monitoring
Post-deployment health checks include:
- Add-on running status
- Ingress endpoint responsiveness
- Resource usage monitoring
- Dependency validation

## Migration from Old System

The enhanced deployment system is backward compatible:
- Existing `just deploy` commands work unchanged
- Old deployment scripts continue to function
- Gradual migration to new features is supported

### Recommended Migration Steps
1. Test with `just deploy-dry-run` to preview changes
2. Use `just deploy-verbose` for detailed output during transition
3. Update any custom deployment scripts to use new error handling
4. Adopt new batch deployment features for multiple add-ons

## Best Practices

1. **Always test first** - Use dry-run mode before production deployments
2. **Use verbose mode** - When troubleshooting deployment issues
3. **Monitor health checks** - Verify add-ons are healthy after deployment
4. **Check logs** - Review deployment logs for any warnings or issues
5. **Validate prerequisites** - Ensure system health before deployment

## Support and Troubleshooting

For deployment issues:
1. Run with `--verbose` flag for detailed output
2. Check deployment logs in `/tmp/deployment-*.log`
3. Verify Home Assistant system health
4. Review add-on specific logs and configuration
5. Use dry-run mode to validate deployment plan
