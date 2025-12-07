# Home Assistant Setup Guide

> **📋 STATUS**: This document provides Home Assistant OS installation guidance.
> **Last Updated**: 2025-12-07
> **Scope**: Home Assistant OS installation and legacy Raspberry Pi setup

## Overview

Use the upstream Home Assistant documentation in `reference-repos/` as the primary source for installing or repairing Home Assistant OS. The legacy Raspberry Pi notes below are preserved for historical reference.

## Recommended: Home Assistant OS install
1. Flash Home Assistant OS for Raspberry Pi using [`reference-repos/home-assistant.io/source/installation/raspberrypi.markdown`](../reference-repos/home-assistant.io/source/installation/raspberrypi.markdown). It covers image selection, flashing, first boot, network setup, and CLI access.
2. If the board fails to boot or you need recovery/SSH enablement guidance, use [`reference-repos/home-assistant.io/source/installation/troubleshooting.markdown`](../reference-repos/home-assistant.io/source/installation/troubleshooting.markdown).
3. For host internals and Buildroot details, see [`reference-repos/operating-system/Documentation/README.md`](../reference-repos/operating-system/Documentation/README.md) and the Supervisor overview in [`reference-repos/developers.home-assistant/docs/supervisor.md`](../reference-repos/developers.home-assistant/docs/supervisor.md) when debugging services that run outside add-ons.
4. After the OS is up, configure the hostname and SSH credentials you plan to target with `just fetch`/`just deploy`; the workflows assume key-based SSH on port 22.


