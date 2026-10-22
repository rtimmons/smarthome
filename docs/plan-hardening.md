# Home Assistant hardening: remaining work

Reconciled October 22, 2026 against repository implementation and dated operational
records. The August audit is historical; unverified findings below need a current
check before remediation. This reconciliation changes documentation only.

## Evidence and ownership

[Sonos validation](sonos/ha-migration-validation.md) records a verified live
add-on-state export on August 29. [Radio recovery](operations/sonoff-zigbee-thread.md)
records encrypted October 16 Supervisor archives and successful Zigbee recovery.
Those scoped checks do not establish a full-machine restore or recurring off-host
coverage for every Home Assistant component. The
[backup runbook](operations/addon-state-backups.md) owns the export/restore contract.

The generator already emits `color_temp_kelvin`; current lighting operation is in
[scene operations](operations/zwave-scene-ops.md). Node 2 is permanently retired;
retain the temporary exclusions for nodes 23 and 28. The Sonoff radio's installed
firmware, verified recovery and intentionally parked Thread/Matter services are
covered by its runbook; do not repeat the old firmware-discovery or migration tasks.

## Remaining work

- [ ] **Database containment.** The MongoDB manifest still publishes TCP/27017,
  requests `full_access`, and starts `mongod --bind_ip_all` without authentication.
  Check effective LAN exposure and close unnecessary publication first. Migrate
  credentials and reduce privileges as separate verified changes, using
  least-privilege application users and secret-safe logging.
  Preserve internal `local-mongodb` access, application data and rollback.
  Compare Printer/TinyURL database-backed operations before/after and observe
  restart/error behavior for 48 hours.
- [ ] **Complete Home Assistant recovery.** Verify current full encrypted backup
  membership, an independently available recovery key, durable off-host copies,
  retention and failure/freshness alerts. Exercise full and focused add-on restores
  on a safe target, including databases, radio state and representative controls.
  Implement the pending `talos backup restore-addon-state` command or retain an
  exercised manual procedure. Audit HA-related plaintext copies and permissions;
  never prune the only recovery artifact.
- [ ] **Durable deployment rollback.** Configuration sync now preserves remote
  recovery files, but `deploy-config.sh` still deletes `/tmp/hass-config-backup`
  before restarting Core. Retain a timestamped rollback through config validation,
  restart and post-restart health; fail closed and test sync/check/restart/health/
  rollback failures. Add source/version/health provenance to deployment evidence;
  add-on scheduling and health gates already exist, transaction rollback does not.
- [ ] **Host hardware health.** Refresh the old thermal finding with physical fan/
  heatsink inspection, representative temperature sampling, SSD SMART and power/
  UPS evidence. Resolve cooling before stress or firmware work. Record the current
  BIOS and a justified update/deferral decision. BIOS work requires a verified
  off-host backup, exact board image, stable power, local console and recovery path.
- [ ] **Access and device security.** Recheck Tailscale's current purpose/health;
  configure it intentionally or remove it. Inventory retained direct listeners,
  consumers, authentication and allowed networks before changing access. Verify
  ESPHome API encryption and web authentication, then repair or accept current
  unavailable ESPHome/Hue/Zigbee targets. Resolve nodes 23/28 through the current
  scene runbook; do not restore retired devices or flash healthy radios blindly.
- [ ] **Operational monitoring.** Close unowned health exceptions and add missing
  backup, capacity, thermal, restart and critical-device alerts. Record owners,
  review dates and an ongoing restore/firmware/access review cadence.

Before each live change, capture current health/data, preserve unrelated work,
verify the rollback artifact and isolate the affected system. Keep secrets and
exact private evidence outside Git. A successful build or a dated backup receipt
alone does not close a live recovery or observation gate.
