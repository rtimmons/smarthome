# Home Assistant hardening plan

> **Status:** Active — focused backup tooling implemented; live recovery validation remains open
>
> **Audit baseline:** 2026-08-05
>
> **Repository reassessment:** 2026-08-05 at `89df8c3` (backup/deployment work through `c7c7292`)
>
> **Scope:** The live Home Assistant host, repository-managed add-ons and configuration, attached radios, and operational recovery procedures
>
> **Primary rule:** Establish recoverability before mutation, then isolate the critical exposure before undertaking general improvements.

## Objective

Bring the Home Assistant installation from a healthy but incompletely hardened appliance to a system that is recoverable, minimally exposed, thermally sound, deliberately maintained, and safe to deploy.

Completion means that:

- MongoDB is not reachable anonymously from the LAN.
- Full encrypted backups exist off-host and a restore has been demonstrated.
- Printer and TinyURL pass application-level health checks without watchdog restarts.
- CPU/GPU junction temperatures have adequate margin under normal and representative load.
- Firmware decisions are recorded and updates are performed only through controlled maintenance windows.
- Remote access and directly published services are intentional, authenticated, and documented.
- Home Assistant configuration deployment retains a rollback artifact until validation and post-restart health checks pass.
- Unavailable or noisy devices are repaired, retired, or explicitly accepted as known exceptions.

This is an execution plan, not a claim that the listed work has been completed.

## Baseline findings

The 2026-08-05 read-only audit established the following baseline:

| Area | Baseline |
| --- | --- |
| Home Assistant platform | HAOS 18.2, Core 2026.8.0, and Supervisor 2026.07.5 were current, supported, and healthy. |
| Configuration | `ha core check` passed and no repository/live drift was detected. A runtime service-schema error involving `color_temp` was still present because static validation does not exercise service calls. |
| Host capacity | Approximately 32 GiB RAM, low load, unused swap, and about 72 GiB free on the 128 GB SATA SSD. No disk, filesystem, OOM, USB, or throttling errors were found. |
| Recovery | Three recent protected backups existed, but they were partial and local to the same SSD. Supervisor reported `no_current_backup`. |
| Critical exposure | MongoDB listened on all host interfaces without authentication and TCP/27017 was reachable from another LAN client. |
| Application health | TinyURL was in a watchdog restart loop because of an invalid MongoDB hostname. Printer ran, but its MongoDB health endpoint failed. |
| Thermals | CPU and GPU junction sensors remained near 85 degrees C under light load. Fan RPM and SSD SMART data were unavailable from the protected SSH environment. |
| Firmware | The UDOO BOLT V3 BIOS was 1.04 from 2019; UDOO publishes 1.08. Z-Wave controller firmware was current. Zigbee coordinator firmware was not exposed by Home Assistant. |
| Remote access | Tailscale was logged out and repeatedly restarted. |
| Devices | Two ESPHome devices were unreachable; reachable fan-controller web interfaces were unauthenticated. Two Z-Wave nodes were dead, and one responsive node showed endpoint-level failures despite a strong RF link. |
| Deployment | Current config deployment removes its temporary backup before restart and post-restart health verification. Existing documentation acknowledges that deployment is not atomic. |

The audit inventory is retained under `new-hass-configs/inventory_snapshots/zwave-scene-audits/20260805-160618/`.

## Progress since the audit

The repository has advanced materially since this plan was written:

- Commit `171d9ba` implements and documents a Talos-native Supervisor partial backup for all seven repository add-ons plus `/share`.
- The backup workflow discovers add-ons from their manifests, orders them by dependency, requires a healthy/supported Supervisor, validates MongoDB cold-backup configuration, checks required applications before and after backup creation, and rejects insufficient remote space.
- Downloaded backups are validated against Supervisor metadata, exact tar membership, size, and a remote-versus-local SHA-256. Publication is atomic, local directories use mode `0700`, files use `0600`, and the generated manifest excludes add-on options and connection secrets.
- Commit `c7c7292` adds dependency-ready deployment scheduling, application health checks, graceful shutdown handling, `--skip-config`, and structured deployment timing output.
- A repository-wide `just test` run on 2026-08-05 passed the selected Talos suite, all configured add-on suites, and every add-on container build check.

This establishes that the **backup implementation** is complete in the repository. It does not establish that a live focused archive was created, copied to durable off-host storage, or restored. No `backups/addon-state/` artifact was present in the repository workspace during this reassessment, and live host state was not re-audited. Those operational gates remain open.

## Priorities and sequencing

| Order | Workstream | Priority | Status | Dependency |
| --- | --- | --- | --- | --- |
| 0 | Recoverability and change isolation | P0 | Operational work open | None |
| 1 | MongoDB containment and application recovery | P0 | Repository preparation partial; deployment open | Phase 0 safety backup |
| 2 | Backup, restore, and secret-file hardening | P1 | Focused backup implementation complete; execution, retention, and restore open | Healthy database stack for focused add-on export |
| 3 | Cooling, storage health, and BIOS maintenance | P1 | Open | Verified off-host backup and physical access |
| 4 | Remote access, service exposure, and device security | P1 | Open | Phase 0; may proceed alongside Phase 3 |
| 5 | Deployment and rollback hardening | P1 | Add-on scheduling/observability partial; config rollback open | Phase 0; complete before routine config changes |
| 6 | Home Assistant runtime and device remediation | P2 | Open | Safe deployment path |
| 7 | Monitoring and maintenance cadence | P2 | Open | Stable post-change baseline |

P0 work addresses an active exposure or is required to make subsequent changes safely. P1 work materially reduces the chance or impact of an outage. P2 work improves correctness and long-term operability.

## Safety rules

These rules apply to every phase:

1. Use repository `just` recipes and pinned runtimes. Do not substitute ad-hoc deployment commands when an established workflow exists.
2. Do not deploy a dirty worktree wholesale. Review and isolate the intended diff, preserve unrelated user work, and identify the exact add-ons or configuration files in scope.
3. Capture before-and-after evidence. At minimum, record Home Assistant health, Supervisor resolution issues, relevant add-on states and restart counts, and the user-facing behavior being changed.
4. Change one fault domain per maintenance window. Do not combine BIOS, HAOS, Zigbee coordinator, Z-Wave, and ESPHome firmware updates.
5. Do not put credentials, recovery keys, tokens, or complete connection strings in Git, command transcripts, issue text, or plan evidence.
6. Define rollback before applying a change. Stop rather than improvising if the expected rollback artifact is absent or cannot be read.
7. Treat `started` as insufficient evidence. A service is healthy only when its dependency-aware endpoint, logs, restart count, and representative user operation are healthy.
8. Use a 24-48 hour observation window for changes involving persistence, watchdog behavior, networking, or device stability.
9. Never perform the UDOO BIOS update remotely. Require stable power, physical console access, the exact board image, recorded settings, and a recovery path.

## Phase 0: Recoverability and change isolation

### Prerequisites

- Administrative access to Home Assistant and the backup encryption emergency kit.
- A destination outside the Home Assistant SSD, preferably a configured network backup mount plus a second off-site copy.
- A maintenance window and a documented way to reach the host locally if network access fails.

### Actions

- [ ] Record the current Git revision, dirty files, live Home Assistant versions, installed add-on states, and Supervisor resolution output.
- [ ] Run `just detect-changes` and resolve any repository/live drift before a deployment.
- [ ] Run `ha core check` and retain the result as baseline evidence.
- [ ] Create a new **full, encrypted Supervisor backup** after the current Core version is installed.
- [ ] Copy or configure that backup to an off-host destination and verify that the remote copy is visible and has plausible metadata and size.
- [ ] Confirm that the backup emergency kit/recovery key is available without relying on the Home Assistant host.
- [ ] Schedule a restore exercise. Backup existence alone is not a restore test.
- [ ] Record application-level MongoDB baselines without storing sensitive values: collection/document counts and representative Printer/TinyURL reads where possible.
- [ ] Identify the exact repository diff needed for Phase 1 and exclude unrelated worktree changes.

Do not use `just addon-state-backup` as this phase's initial safety backup. The focused export requires the repaired MongoDB, Printer, and TinyURL stack to be deployed and healthy first.

### Stop conditions

- No readable full backup exists outside the Home Assistant SSD.
- The emergency kit is unavailable.
- Live configuration drift is unexplained.
- The intended Phase 1 diff cannot be isolated from unrelated work.

If off-host backup configuration cannot be completed promptly, use network-level firewall containment for TCP/27017 as a temporary emergency control before changing add-on state. Do not treat that as the final fix.

### Exit criteria

- [ ] A current full encrypted backup exists locally and off-host.
- [ ] Recovery material is available independently of Home Assistant.
- [ ] Baseline health and application data evidence are retained.
- [ ] The Phase 1 change set and rollback path are explicit.

## Phase 1: MongoDB containment and application recovery

### Repository work — partially complete

The database dependency and backup preparation landed in `171d9ba` and passed `just test`. Remaining and completed items are:

- [ ] Remove MongoDB's host/LAN port publication. Keep database traffic on the Supervisor add-on network.
- [x] Standardize Printer and TinyURL on the confirmed internal hostname `local-mongodb` or its Supervisor FQDN.
- [x] Retain legacy hostname fallbacks for migration, with bounded retries and tested fallback ordering.
- [x] Set MongoDB to `startup: system` and `backup: cold` so Supervisor orders startup and captures consistent database state.
- [x] Add explicit `depends_on: mongodb` declarations and application-level deployment health paths for Printer and TinyURL.
- [x] Preserve private add-on data and `/share` in the focused Supervisor backup contract.
- [x] Add regression tests for hostname selection, retry behavior, dependency order, backup membership, health gates, interrupted transfer, malformed archives, and checksum failure.
- [x] Run `just test` against the committed implementation; all configured tests and container build checks passed on 2026-08-05.

Closing the host port, dropping elevated add-on privileges, running MongoDB as a non-root user, and enabling MongoDB authentication are separate changes. Close the LAN port first. Design and test credential migration afterward so containment is not delayed by a larger database migration.

### Deployment

- [ ] Deploy only the scoped add-on changes; do not invoke a full config deployment as a side effect.
- [ ] Deploy MongoDB first, wait for database readiness, then deploy Printer and TinyURL.
- [ ] Preserve previous add-on packages/configuration and the Phase 0 full backup until the observation window completes.
- [ ] Verify that existing MongoDB data remains readable before allowing new writes to proceed normally.

### Validation

- [ ] A LAN-side connection attempt to Home Assistant TCP/27017 fails.
- [ ] MongoDB remains reachable from authorized internal add-ons.
- [ ] Printer `/health/mongo` succeeds and a representative preset/read operation works.
- [ ] TinyURL's database-backed endpoint succeeds and a representative redirect works.
- [ ] Pre-change and post-change application data counts reconcile.
- [ ] TinyURL and Printer show no watchdog restart or dependency failure for at least 24 hours.
- [ ] Logs contain no repeated DNS fallback, connection timeout, or unrestricted-LAN-listener warnings.

### Post-containment database hardening

Perform this as a separate change after the port-closure observation window:

- [ ] Inventory required databases and client operations for Printer and TinyURL.
- [ ] Design per-application MongoDB users with only the permissions each service needs.
- [ ] Store database credentials in Supervisor-managed options or another approved secret store, never in repository defaults.
- [ ] Redact credentials from TinyURL MongoDB retry/error logs before connection URLs contain authentication data.
- [ ] Create and test the users while existing clients still have a rollback path.
- [ ] Migrate one client at a time, validate its application-level operations, and then disable anonymous database access.
- [ ] Determine whether the add-on can run as a non-root user and without `full_access`; make each privilege reduction independently testable.
- [ ] Confirm an unauthenticated connection from another add-on is rejected and normal Printer/TinyURL behavior remains healthy for 24 hours.

### Rollback

If data or application health fails, stop dependent add-ons, restore the prior add-on state or full Supervisor backup, and revalidate counts before resuming writes. Prefer a temporary internal hostname correction or firewall rule over reopening unauthenticated MongoDB to the LAN.

## Phase 2: Backup, restore, and secret-file hardening

### Focused add-on-state backup — repository implementation complete

- [x] Add the root `just addon-state-backup` recipe and `talos backup addon-state` CLI command.
- [x] Discover all repository add-ons from manifests and serialize backup components in dependency order.
- [x] Require healthy/supported Home Assistant, the expected installed add-on set, MongoDB `startup: system`/`backup: cold`, required database dependents running, and at least 2 GiB free in remote `/backup`.
- [x] Run dependency-aware health checks before and after Supervisor briefly stops MongoDB for its cold backup.
- [x] Create a compressed Supervisor partial backup containing exactly the seven repository add-ons and `/share`, without Home Assistant Core.
- [x] Verify Supervisor metadata, exact outer tar members, embedded `backup.json`, archive size, and remote-versus-local SHA-256.
- [x] Publish atomically with directory mode `0700`, file mode `0600`, a `SHA256SUMS` file, and a secret-free manifest containing Git and Home Assistant version evidence.
- [x] Cover success and failure paths with automated tests and document operation, retention limitations, and the restore contract.
- [ ] After Phase 1 is deployed and healthy, execute `just addon-state-backup` against the live host and retain its timestamped manifest/checksum as evidence.

### Backup policy

- [ ] Configure automatic full encrypted Supervisor backups to a network or cloud destination.
- [ ] Define and document retention. A reasonable initial policy is seven daily, four weekly, and three monthly recovery points, adjusted for archive size and storage capacity.
- [ ] Maintain at least three copies on two storage types with one copy off-site, following Home Assistant's [3-2-1 guidance](https://www.home-assistant.io/blog/2025/01/03/3-2-1-backup/).
- [ ] Alert on backup failure, stale last-success time, unavailable destination, and insufficient free space.
- [x] Implement manifest/checksum verification for the focused add-on-state export.
- [x] Enforce owner-only permissions for the focused export; it is intentionally unencrypted and includes `/share`.
- [ ] Define pruning or transfer policy for both the remote native archive and downloaded focused export; the command intentionally performs no automatic pruning.

### Restore exercise

- [x] Define a versioned, secret-free manifest as the contract for a future focused restore workflow.
- [ ] Implement `talos backup restore-addon-state` with checksum validation, a pre-restore safety backup, explicit component selection, dependency-ordered recovery, state preservation, and post-restore health checks.
- [ ] Select a non-production restore target or a documented destructive maintenance window.
- [ ] Restore a full encrypted backup and confirm Core startup, integrations, secrets, add-ons, radios, and representative automations.
- [ ] Separately exercise the documented manual restore procedure for the focused add-on-state export until a Talos restore command exists.
- [ ] Record duration, required free space, manual steps, failures, and the exact recovery artifact used.

### Local secret copies

- [ ] Inventory ignored local config backup directories before pruning anything.
- [ ] Change directories containing secrets to mode `0700` and sensitive files to `0600`.
- [ ] Encrypt or deliberately remove obsolete plaintext copies after confirming they are not the only recovery artifact.
- [ ] Add an automated permission check that fails if a sensitive backup is group/world-readable.

### Exit criteria

- [x] The focused add-on-state backup command and failure handling pass automated repository tests.
- [ ] A verified focused archive has been created from the live host and copied to its intended durable destination.
- [ ] Supervisor no longer reports `no_current_backup`.
- [ ] A current full backup exists in at least one off-host location.
- [ ] A restore has been demonstrated and documented.
- [ ] No known sensitive local backup is group/world-readable.

See [Add-on state backups](operations/addon-state-backups.md) for the focused export contract.

## Phase 3: Cooling, storage health, and BIOS maintenance

### Physical inspection before testing

- [ ] Shut down safely and inspect the fan, dust buildup, airflow obstruction, heatsink mounting, and thermal-interface condition.
- [ ] Confirm the fan spins as temperature rises. Do not infer fan operation solely from the 85 degrees C plateau.
- [ ] Record enclosure position, ambient temperature, and whether fan RPM can be enabled through UDOO EC/EAPI settings.
- [ ] Do not stress-test or flash firmware until this inspection is complete.

### Thermal validation

- [ ] Sample the `k10temp` Tctl and AMD GPU edge sensors over at least 15 minutes at normal idle and representative Home Assistant workload.
- [ ] Target a sustained light-load junction temperature below 75 degrees C and eliminate the observed light-load 85 degrees C plateau.
- [ ] Define an initial warning at 85 degrees C sustained for 10 minutes and a critical alert at 95 degrees C; refine these thresholds from the post-maintenance baseline.
- [ ] Confirm there are no kernel throttling or thermal events.

If temperatures remain near 85 degrees C at light load after cleaning and fan verification, stop and resolve heatsink contact, fan control, or enclosure airflow before firmware work.

### Storage and power evidence

- [ ] Obtain SSD SMART health, temperature, power-on hours, wear, reallocated sectors, pending sectors, and error-log data through a maintenance environment that can access the controller.
- [ ] Record that the unused eMMC remains a spare rather than assuming it is a current recovery device.
- [ ] Confirm whether the host is protected by a UPS and verify clean shutdown behavior during a controlled power-loss test.
- [ ] Document Secure Boot state, RAM/ECC capability, and any remaining hardware-health unknowns.

### BIOS update

- [ ] Download the exact UDOO BOLT V3 BIOS 1.08 package from the [official update page](https://www.udoo.org/docs-bolt/BIOS_UEFI_and_Tools/BIOS_UEFI_Update.html) and verify the published hash when available.
- [ ] Record current BIOS settings, boot order, fan settings, virtualization settings, and AC-loss behavior with photos or exported values.
- [ ] Confirm stable 19 V power, physical console/keyboard access, and a boot/recovery device.
- [ ] Apply the update locally and complete the required cold power cycle.
- [ ] Reapply intentional settings, especially boot order, fan curve, and restore-on-AC-loss behavior.
- [ ] Verify BIOS 1.08, cold boot, Ethernet, HAOS slot state, storage, USB radios, all add-ons, and thermal behavior.
- [ ] Observe the host for at least 48 hours before any other firmware update.

### Rollback and stop conditions

BIOS rollback may not be routine or remotely recoverable. Stop before flashing if the exact image, stable power, console, recovery method, or verified off-host backup is missing. Do not bundle the BIOS update with HAOS, coordinator, or ESPHome updates.

## Phase 4: Remote access, service exposure, and device security

### Tailscale

- [ ] Decide whether Tailscale is an intentional remote-access dependency.
- [ ] If required, reauthenticate it, review advertised subnet/exit-node/connector roles, and confirm least privilege.
- [ ] If unused, disable and remove it rather than accepting a permanent restart loop.
- [ ] Verify 24 hours without `NeedsLogin`, coordination failures, unhealthy watchdog restarts, or exit-code 137 events.
- [ ] Test the intended remote-access path from outside the LAN.

### Published service inventory

- [ ] Create a port matrix containing listener, purpose, consumer, authentication, network segment, ingress availability, and owner.
- [ ] Review direct host mappings for ports 3000, 5005, 5006, 8099, 4010, and 4100.
- [ ] Prefer authenticated Home Assistant ingress where direct LAN access is unnecessary.
- [ ] Inventory consumers before removing mappings: TinyURL redirects, printer QR URLs, Sonos integrations, or dashboards may intentionally rely on direct URLs.
- [ ] Require explicit authentication and network restriction for every retained direct listener.
- [ ] Disable or remove unconfigured Radarr/Whisparr services if they are not intentional workloads.

No undocumented listener should remain at phase completion.

### ESPHome

- [ ] Recover or retire the unreachable fan controller and human-sensor devices; first verify power, DHCP lease, cabling/Wi-Fi, and physical condition.
- [ ] Store ESPHome API encryption keys and web credentials outside Git.
- [ ] Enable encrypted native API access on every device.
- [ ] Add web authentication or remove `web_server` where it is unnecessary.
- [ ] Rebuild against the current pinned ESPHome toolchain and update one device at a time.
- [ ] Validate control, telemetry, reconnect behavior, and fallback/recovery access before proceeding to the next device.

### Zigbee and Z-Wave firmware

- [ ] Back up ZHA, Z-Wave, and ESPHome configuration before any coordinator or device firmware work.
- [ ] Identify the Sonoff coordinator's exact installed firmware with a vendor-supported diagnostic method; do not flash based only on the USB product name.
- [ ] Compare the installed version with official release notes and update only for a relevant fix or supported migration path.
- [ ] Leave the skipped, incompletely validated Third Reality OTA deferred unless it addresses a demonstrated problem.
- [ ] Do not re-include healthy Z-Wave nodes solely to change security class.
- [ ] Confirm the shared USB hub is adequately powered and use extension cables/radio separation if RF coexistence evidence warrants it.

## Phase 5: Deployment and rollback hardening

This phase turns the safety assumptions needed above into the normal deployment path. It should be completed before routine Home Assistant configuration changes resume.

### Add-on deployment

- [x] Provide explicit add-on-only workflows through `talos addons deploy` and `talos deploy --skip-config`.
- [x] Implement dependency-ready scheduling so MongoDB completes before Printer and TinyURL become eligible while unrelated add-ons continue in parallel.
- [x] Retain application-level health checks and add graceful shutdown handling for Grid Dashboard, Printer, and Sonos API.
- [x] Emit dependency schedule, per-phase status, and timing events to a default JSON metrics artifact.
- [ ] Add the exact Git revision, rendered/deployed add-on versions, and summarized health results to the deployment artifact.
- [ ] Do not describe add-on deployment as atomic until successful add-ons can actually be rolled back after a later failure.

The same commit instruments Home Assistant config phases, but it does not close the config safety gap below: the current script still removes `/tmp/hass-config-backup` before restarting Core and confirming post-restart health.

### Home Assistant configuration deployment

Update `new-hass-configs/sync-tools/deploy-config.sh` so the workflow becomes:

1. Generate configuration and run generator tests.
2. Confirm no unexplained live/repository drift.
3. Upload to staging and show the exact dry-run diff.
4. Create a durable, timestamped rollback artifact outside the staging directory.
5. Synchronize configuration while preserving runtime-owned directories and secrets.
6. Run `ha core check` against the synchronized configuration before restart. If a true staged check becomes supported, run it before synchronization as an additional gate.
7. Automatically restore the rollback artifact if validation fails.
8. Restart Core only after successful validation.
9. Wait for Core and Supervisor health, then exercise representative runtime semantics.
10. Retain the rollback artifact through the observation gate; prune it according to an explicit policy afterward.

- [ ] Parameterize host, user, port, and target directory consistently.
- [ ] Fail closed on validation, restart, timeout, or health-check errors.
- [ ] Add tests for validation failure, sync failure, restart failure, health timeout, and rollback failure.
- [ ] Align deployment documentation with implemented guarantees. Track broader work in [Operations improvements](operations/improvements.md).

### Exit criteria

- [ ] Add-on-only, config-only, and combined workflows are explicit and tested.
- [ ] A failed config validation automatically restores the previous configuration without restarting into the bad state.
- [ ] A failed restart or post-restart health check preserves the rollback artifact and produces actionable output.
- [ ] A controlled rollback exercise succeeds.

## Phase 6: Home Assistant runtime and device remediation

### Scene and generator correctness

- [ ] Change generated light service data from `color_temp` to `color_temp_kelvin` while preserving Kelvin semantics.
- [ ] Add generator regression tests that assert the Home Assistant service schema emitted for office high, medium, and low scenes.
- [ ] Generate configuration and run the full config-generator test suite.
- [ ] Deploy through the hardened configuration workflow.
- [ ] Exercise office high, medium, low, and off paths and confirm Core logs contain no service-schema errors.

### Registry and availability

- [ ] Determine whether `light.light_bathroom_vanityright` was renamed, removed, or should be recreated; update source configuration rather than generated YAML.
- [ ] Reconcile the Enbrighten 35931 device taxonomy for bathroom vanity-left and above-sauna lights.
- [ ] Repair, replace, exclude, or explicitly retire dead Z-Wave nodes 2 and 38.
- [ ] Investigate node 23 as an endpoint/security-session problem before adding repeaters; its direct RF link was strong despite response failures.
- [ ] Monitor node 28 and the latency watch list over multiple inventories before changing routes.
- [ ] Repair or remove the three unavailable Hue scene targets.
- [ ] Run `just zwave-inventory` and the registry-drift/scene-availability checks after changes.
- [ ] Document every remaining unavailable target as an owned, time-bounded exception.

### Exit criteria

- [ ] Office scene paths run without runtime schema errors.
- [ ] Registry-drift checks pass or all exceptions have an owner and disposition.
- [ ] Dead/noisy Z-Wave endpoints are repaired, retired, or accepted with evidence.
- [ ] The unavailable-entity baseline is materially reduced and no unknown critical device remains unavailable.

## Phase 7: Monitoring and maintenance cadence

### Continuous alerts

- [ ] Backup failure, stale backup age, and backup destination unavailable.
- [ ] Disk usage warning at 75 percent and critical at 85 percent.
- [ ] Sustained CPU/GPU junction temperature thresholds established in Phase 3.
- [ ] Add-on watchdog restart, repeated unhealthy state, or restart-count increase.
- [ ] Tailscale logged-out/coordination failure if Tailscale remains in service.
- [ ] Z-Wave controller not ready, unusual dropped traffic, dead critical node, or rapid unavailable-entity increase.
- [ ] ESPHome critical device offline beyond a device-specific grace period.

### Cadence

| Frequency | Review |
| --- | --- |
| Daily | Backup success, host health, critical unavailable devices, add-on restart alerts. |
| Weekly | Disk capacity, temperature trend, Supervisor resolution issues, Tailscale state, focused log anomalies. |
| Monthly | Restore-point inventory, direct-listener matrix, firmware/update review, Z-Wave inventory trend, stale entities. |
| Quarterly | Restore drill or rotating recovery exercise, SSD SMART evidence, UPS test, account/key review, documentation reconciliation. |
| Annually | Physical cleaning, fan/heatsink inspection, BIOS/firmware posture review, recovery-media validation. |

## Definition of done

The hardening effort is complete when all of the following are true or explicitly recorded as accepted risks with an owner and review date:

- [ ] Supervisor is healthy and supported with no current-backup issue.
- [ ] A full encrypted off-host backup and recovery key exist, and a restore has succeeded.
- [ ] LAN TCP/27017 is closed while authorized internal database clients remain healthy.
- [ ] MongoDB anonymous access and elevated runtime privileges have been removed or accepted through a documented threat assessment.
- [ ] Printer and TinyURL pass health and representative user operations with no restart loop for 48 hours.
- [ ] Light-load thermal behavior no longer plateaus near 85 degrees C, monitoring is active, and SSD health has been captured.
- [ ] BIOS 1.08 is installed, or deferral has a documented technical reason, compensating controls, owner, and review date.
- [ ] Tailscale is healthy and intentionally configured or removed.
- [ ] Every directly published service has a documented consumer, authentication boundary, and owner.
- [ ] ESPHome APIs are encrypted and web interfaces are authenticated or removed.
- [ ] Zigbee/Z-Wave firmware posture is documented; no blind or bundled firmware update remains planned.
- [ ] Runtime scene tests pass and Core logs show no related schema failures.
- [ ] Every unavailable critical entity and noisy/dead Z-Wave node has a disposition.
- [ ] Config deployment retains rollback through validation and post-restart health, and a rollback exercise has succeeded.
- [ ] Repository documentation describes only guarantees the tooling actually implements.

## Evidence log

Record completed work without copying credentials or sensitive configuration:

| Date | Phase/task | Change reference | Before evidence | After evidence | Rollback artifact | Result/owner |
| --- | --- | --- | --- | --- | --- | --- |
| 2026-08-05 | Phases 1-2: database dependency and focused backup implementation | `171d9ba` | No repository-native add-on state export | Native Supervisor partial backup with health gates, exact membership/checksum validation, private atomic publication, manifest, docs, and tests | Supervisor archive remains in `/backup`; restore command still pending | Repository implementation complete |
| 2026-08-05 | Phase 5: deployment scheduling and observability | `c7c7292` | Sequential deployment and limited timing evidence | Dependency-ready queue, `--skip-config`, health/graceful-shutdown checks, structured timings | Add-on transaction rollback and config rollback remain pending | Partial completion |
| 2026-08-05 | Repository validation | `just test` | Reassessment required | Talos, configured add-on suites, and all add-on container build checks passed | Not applicable | Passed |
|  |  |  |  |  |  |  |

## Related documentation

- [Operations improvements](operations/improvements.md)
- [Add-on state backups](operations/addon-state-backups.md)
- [System consistency verification](operations/system-verification.md)
- [Z-Wave scene operations](operations/zwave-scene-ops.md)
- [ESPHome fan controllers](operations/esphome-fancontrollers.md)
- [Configuration synchronization](development/configuration-sync.md)
- [Deployment system guide](deployment/deployment-system-guide.md)
