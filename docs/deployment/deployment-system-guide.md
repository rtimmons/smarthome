# Deployment System Guide

## Overview

The enhanced deployment system provides robust, production-ready deployment capabilities for Home Assistant add-ons with comprehensive error handling, validation, and troubleshooting features.

## Key Features

### 🚀 **Deployment Modes**
- **Standard Deployment**: Clean, professional output suitable for production
- **Verbose Deployment**: Detailed output with full command visibility
- **Dry-Run Mode**: Preview deployments without making changes
- **Batch Deployment**: Deploy multiple add-ons atomically

### 🛡️ **Safety Features**
- **Pre-deployment Validation**: SSH connectivity, HA core status, disk space
- **Configuration Sync Protection**: Automatic detection of UI-modified configurations
- **Health Checking**: Post-deployment verification of add-on state
- **Atomic Operations**: All-or-nothing deployment strategy
- **Error Recovery**: Comprehensive error handling with troubleshooting steps

### 📊 **Enhanced Diagnostics**
- **Log Capture**: Automatic capture of add-on logs during failures
- **Rich Error Reporting**: Structured error messages with context
- **Troubleshooting Guidance**: Automated suggestions for common issues
- **Progress Tracking**: Real-time deployment progress indicators

## Usage

### Basic Deployment Commands

```bash
# Deploy single add-on (clean output)
just deploy grid-dashboard

# Deploy multiple add-ons
just deploy grid-dashboard sonos-api mongodb

# Deploy all discovered add-ons
just deploy

# Verbose deployment with detailed output
just deploy-verbose grid-dashboard

# Dry-run preview (no changes made)
just deploy-dry-run grid-dashboard

# Verbose dry-run with full details
just deploy-dry-run-verbose grid-dashboard
```

### Individual Add-on Deployment

```bash
# From add-on directory
cd grid-dashboard
just deploy

# Dry-run from add-on directory
cd grid-dashboard
just deploy-dry-run
```

### Command Aliases

```bash
# Short aliases for common operations
just d grid-dashboard      # deploy
just dd grid-dashboard     # deploy-dry-run
just dv grid-dashboard     # deploy-verbose
just df grid-dashboard     # deploy-force (skip sync checks)
```

### Configuration Sync Commands

The deployment system includes bidirectional sync protection for Home Assistant configurations:

```bash
# Check for configuration drift
just detect-changes

# Fetch UI changes into repository
just fetch-config

# Show diff and resolution options
just reconcile scenes.yaml

# Force deploy (skip sync checks)
just deploy-force

# Force deploy with backup
just deploy-force --backup
```

> **Note**: Standard `just deploy` now includes automatic sync checking. If UI-modified configurations are detected, deployment will be blocked with resolution options. See [Configuration Sync Guide](../development/configuration-sync.md) for details.

## Architecture

### Deployment Flow

1. **Discovery Phase**: Identify add-ons to deploy
2. **Validation Phase**: Check prerequisites (SSH, HA core, disk space)
3. **Sync Check Phase**: Detect configuration drift and prevent overwrites
4. **Build Phase**: Build add-on containers if needed
5. **Deploy Phase**: Upload and install add-ons
5. **Health Check Phase**: Verify add-on started successfully
6. **Reporting Phase**: Display results and capture logs on failure

### Error Handling

The system uses structured error handling with the `DeploymentError` class:

```python
class DeploymentError(Exception):
    def __init__(self, message, addon_name=None, context=None, logs=None):
        self.message = message
        self.addon_name = addon_name
        self.context = context or {}
        self.logs = logs or []
```

### Output Modes

- **Quiet Mode** (default): Clean, professional output
- **Verbose Mode**: Full command output and detailed progress
- **Dry-Run Mode**: Preview without execution
- **Error Mode**: Rich error display with logs and troubleshooting

## Configuration

### Environment Variables

```bash
# Override default settings
export HA_HOST="homeassistant.local"
export HA_PORT="22"
export HA_USER="root"
export DEPLOYMENT_TIMEOUT="300"
```

### Justfile Variables

Common variables are defined in `talos/just/common.just`:

```just
ha_host := env_var_or_default("HA_HOST", "homeassistant.local")
ha_port := env_var_or_default("HA_PORT", "22")
ha_user := env_var_or_default("HA_USER", "root")
```

## Troubleshooting

### Common Issues

#### SSH Connection Failed
```
❌ Deployment Failed: grid-dashboard
💬 SSH connection failed

🔧 Troubleshooting Steps:
1. Check network connectivity to homeassistant.local
2. Verify SSH is enabled in Home Assistant
3. Confirm SSH key authentication is set up
4. Try manual SSH connection: ssh root@homeassistant.local
```

#### Home Assistant Core Not Running
```
❌ Deployment Failed: grid-dashboard
💬 Home Assistant core is not running

🔧 Troubleshooting Steps:
1. Check Home Assistant system status
2. Review Home Assistant logs for errors
3. Restart Home Assistant if needed
4. Verify system resources (CPU, memory, disk)
```

#### Add-on Build Failed
```
❌ Deployment Failed: grid-dashboard
💬 Add-on build failed

📋 Recent Logs:
2025-12-07 10:00:00 ERROR Failed to install dependencies
2025-12-07 10:00:01 ERROR Build process terminated

🔧 Troubleshooting Steps:
1. Check addon configuration (config.yaml)
2. Verify Dockerfile syntax and dependencies
3. Review build logs for specific errors
4. Test container build locally
```

### Debug Mode

Enable debug mode for maximum verbosity:

```bash
# Set debug environment variable
export TALOS_DEBUG=1
just deploy-verbose grid-dashboard
```

## Best Practices

### Development Workflow

1. **Test Locally**: Always test add-on builds locally first
2. **Use Dry-Run**: Preview deployments with `deploy-dry-run`
3. **Deploy Incrementally**: Deploy one add-on at a time during development
4. **Monitor Logs**: Check add-on logs after deployment
5. **Validate Health**: Verify add-on functionality after deployment

### Production Deployment

1. **Batch Deploy**: Use batch deployment for multiple add-ons
2. **Monitor Progress**: Watch deployment progress indicators
3. **Verify Results**: Check deployment summary for any failures
4. **Rollback Plan**: Have rollback procedures ready
5. **Document Changes**: Keep deployment logs for audit trail

### Error Recovery

1. **Read Error Messages**: Review structured error output carefully
2. **Check Logs**: Examine captured add-on logs for details
3. **Follow Troubleshooting**: Use provided troubleshooting steps
4. **Incremental Fix**: Address issues one at a time
5. **Test Again**: Re-run deployment after fixes

## Integration

### CI/CD Integration

The deployment system is designed for CI/CD integration:

```bash
# CI-friendly deployment with structured output
just deploy --ci-mode grid-dashboard

# Exit codes:
# 0 = Success
# 1 = Deployment failed
# 2 = Validation failed
# 3 = Configuration error
```

### Monitoring Integration

Deployment events can be monitored:

```bash
# JSON output for monitoring systems
just deploy --json-output grid-dashboard
```

## Security

### SSH Key Management

- Use SSH key authentication (no passwords)
- Rotate SSH keys regularly
- Limit SSH access to deployment systems only

### Network Security

- Deploy over secure networks only
- Use VPN for remote deployments
- Monitor deployment access logs

### Add-on Security

- Scan add-on containers for vulnerabilities
- Review add-on permissions and capabilities
- Keep base images updated

## Performance

### Optimization Tips

- Use parallel deployment for multiple add-ons
- Cache container builds when possible
- Monitor deployment times and optimize slow steps
- Use local container registry for faster uploads

### Resource Management

- Monitor Home Assistant system resources during deployment
- Schedule deployments during low-usage periods
- Clean up old container images regularly

## Support

For deployment issues:

1. Check this guide for common solutions
2. Review deployment logs and error messages
3. Test with dry-run mode first
4. Use verbose mode for detailed diagnostics
5. Check Home Assistant system status and logs
