# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a smart home automation system built on Raspberry Pi that integrates with Home Assistant, Sonos, Hue lights, and Z-Wave devices. The system provides a custom web interface for controlling various smart home components.

## Architecture

The project consists of three main components:

1. **HomeAssistantConfig** - Home Assistant configuration files including automations, scenes, and Z-Wave device configurations
2. **MetaHassConfig** - Python tool that generates Home Assistant configuration from a metaconfig.yaml file
3. **ExpressServer** - TypeScript/Node.js Express server providing API endpoints and web interface for smart home control

## Key Commands

### Development

```bash
# Generate Home Assistant configuration from metaconfig
./check-hass-configs.sh

# Deploy configuration to Raspberry Pi (hostname: smarterhome5.local)
./put-hass-configs.sh

# Retrieve current configuration from Raspberry Pi
./get-hass-configs.sh

# Deploy entire system using Ansible
cd Ansible && ./deploy.sh
```

### ExpressServer Development

```bash
cd ExpressServer
npm install           # Install dependencies
npm run dev          # Run development server with auto-reload
npm test             # Run tests
npm run check        # Run TypeScript checks
npm run fix          # Fix linting issues
```

### MetaHassConfig Development

```bash
cd MetaHassConfig
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python setup.py develop
hassmetagen ../HomeAssistantConfig/metaconfig.yaml  # Generate Home Assistant config
```

## Deployment Process

1. The Raspberry Pi runs at hostname `smarterhome5.local` (configurable in Ansible/vars/main.yml)
2. Deployment uses Ansible playbooks to configure the Pi with all necessary services
3. Home Assistant configuration is generated from metaconfig.yaml using the MetaHassConfig tool
4. The system requires passwordless SSH access to the Pi for deployment

## Important Files

- `HomeAssistantConfig/metaconfig.yaml` - Master configuration for all Home Assistant entities
- `ExpressServer/src/server/index.ts` - Main Express server entry point
- `Ansible/roles/smarthome/tasks/main.yml` - Primary Ansible role for system setup

## Z-Wave Device Notes

- Dimmer switch 46203 requires manual command class updates for scene support (see README.md:134-163)
- Zooz Zen31 RGBW Dimmer needs specific setting changes after adding (see README.md:165-171)

