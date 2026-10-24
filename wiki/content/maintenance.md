# Maintenance and recovery

## Work from the repository

Use `just setup` for the pinned runtimes and `just dev` for local development. Validate the affected component with `just test <addon>` and use the documented deployment recipes. A backup of source does not replace backups of application state.

Infrastructure commands use `just usenet <recipe> [args...]`; list them with `just usenet --list`. Common health/test and offline recovery shortcuts remain. See [operations](../../usenet-infra/docs/operations.md) for the command migration and recovery environment handling.

Before changing a system, read its current runbook, inspect health, preserve unrelated local edits, and retain rollback information. Scene operations, printing, media requests, and speaker writes can affect the household; do not use them as generic smoke tests.

Standard local add-on deployment detects the actual source mount in the SSH environment: `/local_apps` on current Home Assistant, or a mounted `/addons` on older versions. It refuses to stop or replace an add-on if neither mount is present. An ordinary leftover `/addons` directory is not a valid destination: uploading there can produce an apparently successful rebuild of old source. Verify served assets or behavior after deployment, in addition to service readiness.

New local add-ons are registered with `ha store reload`. On the current CLI,
`ha apps reload` only lists installed apps and does not discover new source.
The [HTTP proxy](network.md#named-web-services) binds an explicit LAN address
using host networking, so its acceptance checks target that address rather
than the Supervisor's internal bridge address.

Home Assistant configuration checks and deployments preserve remote-only backups, hidden recovery directories, and installed template blueprints during synchronization. These files may not exist in the checkout and must not be deleted just because they are absent locally.

The configuration deployment also includes the root `light_profiles.csv`, which supplies the household's zero-second default light transition. It is an explicit deployment include; unrelated CSV files are not deployed.

Room organization has separate, explicit maintenance commands: `just rooms-generate` and `just rooms-check` manage the shared dashboard/Sonos definitions; `just rooms-audit` inspects Home Assistant areas; `just rooms-apply` aligns known names while preserving stable IDs and voice aliases. Optional legacy-area cleanup only removes audited empty, unreferenced areas and saves private recovery metadata first. Follow the [dashboard guide](dashboard.md) for scope and deployment.

Open Home Assistant database containment, full recovery, deployment rollback, hardware and device-security checks are tracked in the [hardening checklist](../../docs/plan-hardening.md). Verified scoped backups and radio recovery do not establish a full-machine restore.

## Disposable workstation checkout

Durable controller credentials, recovery evidence and local database state live
outside the repository. `just deploy` recreates compatibility links before
rebuilding missing runtimes, so a provisioned controller can run
`git clean -dfx && just deploy`. New source files must already be tracked.
The [workstation recovery guide](../../docs/setup/disposable-checkout.md) explains
the external state directory, separate age master for 1Password, authenticated
restore drill and remaining controller prerequisites. The older SOPS recovery
package stays unchanged. Preserve both recovery masters and their ciphertext.

## Keep explanations with changes

Update the corresponding guide or runbook when behavior changes. The component catalog connects source files to their explanations. `just wiki-check` rejects unreviewed source fingerprints. After reviewing, record a specific explanation with `just wiki-review <component> '<reason>'`; a no-documentation-impact decision must explain why.

Generated service, device, effective scene, control and DNS tables update directly from repository configuration. The [coverage report](wiki-reference:coverage) records guide ownership, watched sources and review reasons. Narrative review dates remain separate from build dates. Direct UI changes still need an intentional update to the repository’s runbook.

## Publish and recover this guide

`just wiki-preview` builds and serves a local preview. `just wiki-deploy` publishes documentation-only changes. Supported service deployments prepare the guide before changing services and publish it after successful completion. A failed wiki update preserves the previous release and does not roll back household services.

The deployment wrapper checks access to the existing wiki before changing services. It prints and saves its output under `build/wiki/logs/`. If publication fails after services succeed, use `just wiki-deploy` to publish the retained receipts; the failure log identifies the URL and connection error.

Use `just wiki-rollback` to restore the retained previous release. Inspect deployment receipts for scope and revision; these record successful deployment commands, not continuous health monitoring.

The [wiki operations guide](../../docs/operations/wiki.md) owns publication details. Read [add-on state backups](../../docs/operations/addon-state-backups.md) and [NAS backup coverage](../../usenet-infra/docs/scheduled-backups.md) for the state each system protects. NAS media is excluded from the repository-owned settings archives. The separate HBS/B2 job selects irreplaceable files, the current laptop's `SpaceBlackTimeMachine` share and those settings archives. The retired SpaceGray share was removed from future backups on October 19. Its expanded uploads succeeded on October 18–19; a sample restore remains unverified. Its upload rate is capped at 10 MB/s every day to reduce contention with Plex.

The scoped media recovery deployment installs only reporting and Home Assistant notifications, validates the HA package, and publishes this guide after success. See the [media recovery runbook](../../usenet-infra/docs/native-media.md#seerr-recovery-reporting); promotion to automatic repairs is a separate change.

`just usenet configure-seerr-sync` repairs only the Plex destination route and read-only sync checks. It preserves the default route and does not restart media services.

The [Sonoff recovery guide](../../docs/operations/sonoff-zigbee-thread.md) covers the preserved Zigbee network and the disabled Thread/Matter services. Its separate SOPS supplement stores the saved Thread credentials and encrypted-backup passwords; decryption with the existing recovery key was verified on October 16. Keep the actual Home Assistant and app backups as well. Enabling Thread later uses Home Assistant's retained credentials and does not require decrypting the supplement.

`just usenet configure-seerr-safety` stages a private Recyclarr preview; adding
`true` applies only the reviewed settings and request-monitoring scope. The daily
Recyclarr timer maintains settings, while recovery stays report-only. The
separate `just usenet cleanuparr-replay` lab has no production credentials or
media mounts and is removed after testing. See the [settings rollout runbook](../../usenet-infra/docs/native-media.md#settings-ownership-and-offline-recovery-qualification).

## Choose the recovery scope

The NAS also hosts [Forgejo](../../git-host/README.md) for private Git repositories,
issues and pull requests. Open `http://git.home.arpa/` on the LAN and run
`just git-host status` for health. It uses one resource-limited container with
SQLite; registration and CI runners are disabled. Its application state is
separate from media services. Its encrypted backup workflow captures the stopped
service and verifies off-host readback in the existing confined Storage Box backup
account. Run `just git-host backup-status` to check freshness, and follow the
runbook's dated acceptance evidence and restore procedure before upgrading.

| What was lost | Recovery guide | What it can recover |
| --- | --- | --- |
| An add-on’s saved state | [Add-on backups](../../docs/operations/addon-state-backups.md) | The selected application state; verify the archive scope |
| Cloud services or NAS settings | [Media recovery](../../usenet-infra/docs/recovery.md) | Configuration and databases; media and replacement NAS boot are excluded |
| Filex settings or operator access | [Filex recovery](../../usenet-infra/docs/filex-recovery.md) | Portal state and separately escrowed operator material; staging payloads are excluded |
| This checkout or its private local files | [Checkout recovery](../../usenet-infra/docs/checkout-recovery.md) | The dated preserved files and Git history; check freshness before relying on it |
| Recovery credentials | [Secrets and state recovery](../../usenet-infra/docs/secrets-recovery.md) | Existing escrowed identities; retain the original recovery key and bound inventory |

Restore into a new private directory for verification before touching surviving state. A fresh wiki build does not refresh a backup or prove a full Home Assistant restore.
