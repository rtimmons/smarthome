Blinds Controller API
============================

A minimal HTTP API for controlling motorized blinds on Raspberry Pi via I2C.

## Overview

This project provides a REST API for controlling motorized blinds via I2C communication on a Raspberry Pi. Automated deployment using Ansible.

## Architecture

1. **ExpressServer** - Minimal TypeScript/Node.js Express API server
   - REST API for blinds control (`/blinds-i2c/:room`)
   - I2C communication for motor control
   - No web interface - API only

2. **Ansible** - Deployment automation for Raspberry Pi setup

## Hardware Requirements

- Raspberry Pi (tested on Pi 3)
- Quality SD card
- I2C-compatible motor controller
- Motorized blinds connected to the controller
- Heatsink for the Pi

## Available Blinds

The system currently supports these rooms:
- **bedroom_roller**: Bedroom roller blinds
- **bedroom_blackout**: Bedroom blackout blinds
- **living_roller**: Living room roller blinds
- **office_roller**: Office roller blinds
- **office_blackout**: Office blackout blinds

Each blind can be moved up, down, or to mid position (if configured).

## Setup and Install

1. Set up your Raspberry Pi with Raspbian
2. Configure I2C: `sudo raspi-config` → Interface Options → I2C → Enable
3. Follow [setup steps](./setup.md) for networking and SSH access
4. Update `Ansible/vars/main.yml` with your Pi's hostname
5. Deploy: `cd Ansible && ./deploy.sh`

## Development

### ExpressServer Development

```bash
cd ExpressServer
npm install           # Install dependencies
npm run dev          # Run development server with auto-reload
npm test             # Run tests
npm run check        # Run TypeScript checks
npm run fix          # Fix linting issues
```

### Deployment

```bash
# Deploy entire system using Ansible
cd Ansible && ./deploy.sh
```

The deployment:
1. Installs Node.js on the Raspberry Pi
2. Clones/updates the repository
3. Installs dependencies and I2C tools
4. Sets up systemd service
5. Starts the blinds controller service

## API Reference

Base URL: `http://<your-pi-hostname>:3000`

### Health Check
```
GET /
```

Response:
```json
{
  "status": "ok",
  "service": "blinds-controller"
}
```

### Get Blind State
```
GET /blinds-i2c/:room
```

Example: `GET /blinds-i2c/bedroom_roller`

Response:
```json
{
  "state": "up"
}
```

### Control Blind
```
POST /blinds-i2c/:room
Content-Type: application/json

{
  "state": "up" | "down" | "mid"
}
```

Example: `POST /blinds-i2c/bedroom_blackout`
```bash
curl -X POST http://raspberrypi.local:3000/blinds-i2c/bedroom_blackout \
  -H "Content-Type: application/json" \
  -d '{"state":"down"}'
```

Response:
```json
{
  "state": "down"
}
```

Error response (unknown room):
```json
{
  "error": "unknown room bedroom_invalid"
}
```

Error response (missing state):
```json
{
  "error": "Missing state parameter"
}
```

## Configuration

Edit `ExpressServer/src/server/blindControl-i2c.ts` to configure:
- I2C addresses and bits for each blind
- Motor timing (wait periods)
- Add new rooms/blinds

```typescript
const rooms: {[k: string] : Blind} = {
    bedroom_roller: new Blind({
        up: {address: 0x11, bit: 0x2},
        down: {address: 0x11, bit: 0x1}
    }),
    // ... add more blinds here
};
```

## Project Structure

```
ExpressServer/
├── src/
│   └── server/
│       ├── index.ts              # Express server entry point
│       ├── blindControl-i2c.ts   # I2C blinds controller API
│       └── i2c.ts                # I2C bus wrapper
├── package.json
└── tsconfig.json

Ansible/
├── deploy.yml                    # Main deployment playbook
├── roles/
│   ├── express-server/           # Express server deployment
│   ├── node/                     # Node.js installation
│   ├── repo/                     # Git repo management
│   └── ...                       # Supporting roles
└── vars/
    └── main.yml                  # Configuration variables
```

## Integration Examples

### Shell Script
```bash
#!/bin/bash
# Close bedroom blinds
curl -X POST http://raspberrypi.local:3000/blinds-i2c/bedroom_roller \
  -H "Content-Type: application/json" \
  -d '{"state":"down"}'

curl -X POST http://raspberrypi.local:3000/blinds-i2c/bedroom_blackout \
  -H "Content-Type: application/json" \
  -d '{"state":"down"}'
```

### Python
```python
import requests

def control_blind(room, state):
    url = f"http://raspberrypi.local:3000/blinds-i2c/{room}"
    response = requests.post(url, json={"state": state})
    return response.json()

# Open office blinds
control_blind("office_roller", "up")
control_blind("office_blackout", "up")
```

### Home Assistant Integration
```yaml
# configuration.yaml
rest_command:
  bedroom_blinds_up:
    url: http://raspberrypi.local:3000/blinds-i2c/bedroom_roller
    method: POST
    content_type: 'application/json'
    payload: '{"state":"up"}'
  
  bedroom_blinds_down:
    url: http://raspberrypi.local:3000/blinds-i2c/bedroom_roller
    method: POST
    content_type: 'application/json'
    payload: '{"state":"down"}'
```

## Troubleshooting

### Service Status
```bash
sudo systemctl status express-server
sudo journalctl -u express-server -f
```

### I2C Verification
```bash
# Check I2C is enabled
lsmod | grep i2c

# List I2C devices
i2cdetect -y 1
```

### Manual Testing
```bash
# Health check
curl http://localhost:3000/

# Get blind state
curl http://localhost:3000/blinds-i2c/bedroom_roller

# Control blind
curl -X POST http://localhost:3000/blinds-i2c/bedroom_roller \
  -H "Content-Type: application/json" \
  -d '{"state":"up"}'
```
