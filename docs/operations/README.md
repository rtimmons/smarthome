# Operations

For the generated directory of published runbooks, use the [wiki](https://wiki.home.rytim.com/runbooks/). Its ownership and navigation come from `wiki/components.json`; see [wiki operations](wiki.md).

- [plan-dashboard-upgrade.md](../plan-dashboard-upgrade.md) — Proposed compatibility-first upgrade plan for the iPad Grid Dashboard
- [plan-nas-storage-and-access.md](../plan-nas-storage-and-access.md) — Flat service shares, writable Hetzner access, phased migrations, legacy-share retirement, System volume label and QNAP cleanup exceptions
- [plan-nas-access-model.md](../plan-nas-access-model.md) — Named datasets, homes, users and roles; `svc-` migration; Forgejo isolation, Hetzner/Plex/HA access and restricted platform roots
- [plan-nas-data-protection.md](../plan-nas-data-protection.md) — Per-share and QNAP-exception B2 policies, complete application recovery, retention, restore checks and current/future RAID placement
- [nas-preflight-2026-10-25.md](../nas-preflight-2026-10-25.md) — Read-only disk/snapshot, homes, legacy-share and backup findings; resolved ownership and remaining migration gates
- [nas-media-retirement-2026-10-25.md](../nas-media-retirement-2026-10-25.md) — QNAP media apps removed with encrypted state preservation; retained-service checks and deferred scrub decision
- [system-verification.md](system-verification.md) — System consistency verification procedures
- [addon-state-backups.md](addon-state-backups.md) — Talos-native Supervisor backup workflow and restore-ready artifact contract
- [household-identity.md](household-identity.md) — AD, unified SMB credentials, browser SSO, certificate trust and rollout checkpoints
- [unifi-network-setup.md](unifi-network-setup.md) — Current UniFi topology, radio plan, IoT SSID, client placement, and iteration workflow
- [unifi-ssh-access.md](unifi-ssh-access.md) — Cloud Gateway Max console and retained AP/switch SSH access
- [unifi-post-migration.md](unifi-post-migration.md) — Native DNS pilot, Site Magic, VPN modernization, backup and firewall acceptance
- [UniFi as code investigation](../plan-unifi-iac.md) — Terraform/provider comparison, adoption limits, external state and proposed `just deploy` integration
- [UniFi MCP](../../network-infra/unifi-mcp/README.md) — Pinned launcher with explicit approval required for writes using the MCP settings environment
- [unifi-apple-tv-remote.md](unifi-apple-tv-remote.md) — Evidence-first UniFi, Bonjour, and Apple TV Remote troubleshooting
- [nest-integration.md](nest-integration.md) — Google Nest OAuth, Device Access, Pub/Sub, entity naming, and verification
- [zwave-scene-ops.md](zwave-scene-ops.md) — Z-Wave scene responsiveness diagnostics and inventory workflow
- [sonoff-zigbee-thread.md](sonoff-zigbee-thread.md) — Shared Sonoff Zigbee and Thread configuration, restore fix, and recovery
- [esphome-fancontrollers.md](esphome-fancontrollers.md) — ESPHome fan controller inventory and setup workflow
- [improvements.md](improvements.md) — Comprehensive improvements roadmap
- [Usenet acceptance](../../usenet-infra/docs/validation.md) — Current deployment and accepted recovery limits
- [Native media](../../usenet-infra/docs/native-media.md) — Arr imports, canonical storage and remote Plex playback
- [Repair volume](../../usenet-infra/docs/repair-spool.md) — Current mount definitions and existing-volume recovery
- [Scheduled backups](../../usenet-infra/docs/scheduled-backups.md) — Host-owned schedules, freshness, scope and retention
- [Checkout recovery](../../usenet-infra/docs/checkout-recovery.md) — Local files, Git history/stashes, restore and deletion check
- [Security findings](../../usenet-infra/docs/security-findings.md) — Dependency fixes and historical-key limits
- [Usenet operations](../../usenet-infra/docs/operations.md) — Operating commands for native acquisition and selective NAS copies
- [Private file portal](../../usenet-infra/docs/filex.md) — Bounded staging, verified transfers, read-only canonical media and emergency disable
- [Filex recovery](../../usenet-infra/docs/filex-recovery.md) — Encrypted portal state, key escrow and restore procedure
- [NAS and Plex layout](../../usenet-infra/docs/nas-plex-layout.md) — Media directories, library separation, profile permissions and rollback
- [Hardware catalog](zwave-product-catalog.json) — Product identities; live status belongs in inventory snapshots

[Documentation index](../README.md)
