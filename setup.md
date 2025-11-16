Setup
=====

Goal is for the Raspberry Pi to be [cattle not a pet](https://www.theregister.co.uk/2013/03/18/servers_pets_or_cattle_cern/), so the entire build and deploy process is designed to:

1. Have a custom hostname so you can have multiple Raspberry Pis on your network
2. Not require **ever** plugging in a keyboard or monitor

## Prerequisites

You will need:

1. Raspberry Pi 3 (or compatible model) with heatsink
2. Quality SD card (don't cheap out on this)
3. Ethernet cable to connect your Pi to your router
4. Your Pi and computer on the same network (same subnet for `.local` mDNS to work)
5. No existing hosts with the `raspberrypi.local` hostname
6. Internet connection for the Pi to download dependencies
7. A Mac or Linux computer (tested on Mac; Windows should work with WSL)

## Initial SD Card Setup

1. Download Raspbian Buster Lite from [here](https://www.raspberrypi.org/downloads/raspbian/)
   - Direct link: https://downloads.raspberrypi.com/raspios_lite_armhf/images/
   - Use the "lite" version (no desktop needed)

2. Burn to SD card using [Etcher](https://etcher.io/)

3. Mount SD card to your computer

4. Enable SSH by creating an empty file:
```sh
touch /Volumes/boot/ssh
```

5. Unmount the SD card

## First Boot

1. Insert SD card into Raspberry Pi
2. Connect Pi to your router via Ethernet cable
3. Plug in power to the Pi
4. Wait about 30 seconds for it to boot

## Enable Passwordless SSH

```sh
# If necessary, install ssh-copy-id (Mac)
brew install ssh-copy-id

# Copy your SSH key to the Pi (using default pi user initially)
ssh-copy-id 'pi@raspberrypi.local'
```

This will ask you to confirm adding to your `known_hosts` file.
Default password is `raspberry`.

After initial setup, you'll create a `blinds` user during deployment.

**Note**: If you've re-burned the image or connected to another host named `raspberrypi.local`, SSH will complain. Remove the old entry from `~/.ssh/known_hosts`.

## Configure Hostname

Edit `./Ansible/vars/main.yml` to set your desired hostname (default is `blinds.local`).

## Initial System Update

Update the system packages before deployment:

```sh
ssh pi@raspberrypi.local

# Update package lists
sudo apt update --allow-releaseinfo-change

# Upgrade all packages (takes about 6-7 minutes)
sudo apt upgrade -y

# Reboot (takes about 75 seconds)
sudo /sbin/reboot -h now
```

## Deploy Blinds Controller

Wait for the Pi to reboot, then run the deployment:

```sh
# Configure networking and hostname
./Ansible/setup-networking.sh

# Deploy the blinds controller
./Ansible/deploy.sh
```

## Enable I2C

The blinds controller requires I2C to be enabled:

```sh
ssh blinds@blinds.local
sudo raspi-config
```

Navigate to: **Interface Options → I2C → Enable**

Then reboot:
```sh
sudo /sbin/reboot -h now
```

## Access the API

After deployment completes, access the API at:
```
http://blinds.local:3000
```

Test it with:
```sh
curl http://blinds.local:3000
curl http://blinds.local:3000/blinds-i2c/bedroom_roller
```

## Troubleshooting

### Starting Over

If things go wrong, you can easily start fresh:

1. Unplug Pi from power
2. Remove any lines from your `~/.ssh/known_hosts` file that contain `raspberrypi.local` or your chosen hostname
3. Re-burn the SD card and start from the top

### SSH Connection Issues

- Ensure your computer and Pi are on the same network
- Check that mDNS/Bonjour is working (`.local` resolution)
- Try using the IP address instead of hostname
- Verify SSH is enabled on the Pi

### I2C Not Working

- Double-check I2C is enabled via `raspi-config`
- Verify I2C devices are connected properly
- Check with `i2cdetect -y 1` to see connected devices
- Ensure proper permissions for the `blinds` user

### Service Not Starting

Check service status:
```sh
sudo systemctl status express-server
```

View logs:
```sh
sudo journalctl -u express-server -f
```

Restart service:
```sh
sudo systemctl restart express-server
```
