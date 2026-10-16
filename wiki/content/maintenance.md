# Maintenance and recovery

## Work from the repository

Use `just setup` for the pinned runtimes and `just dev` for local development. Validate the affected component with `just test <addon>` and use the documented deployment recipes. A backup of source does not replace backups of application state.

Before changing a system, read its current runbook, inspect health, preserve unrelated local edits, and retain rollback information. Scene operations, printing, media requests, and speaker writes can affect the household; do not use them as generic smoke tests.

## Keep explanations with changes

Update the corresponding guide or runbook when behavior changes. The component catalog connects source files to their explanations. `just wiki-check` rejects unreviewed source fingerprints. After reviewing, record a specific explanation with `just wiki-review <component> '<reason>'`; a no-documentation-impact decision must explain why.

Generated service, device, and scene tables update directly from repository configuration. Narrative review dates remain separate from build dates. Direct UI changes still need an intentional update to the repository’s runbook.

## Publish and recover this guide

`just wiki-preview` builds and serves a local preview. `just wiki-deploy` publishes documentation-only changes. Supported service deployments prepare the guide before changing services and publish it after successful completion. A failed wiki update preserves the previous release and does not roll back household services.

The deployment wrapper checks access to the existing wiki before changing services. It prints and saves its output under `build/wiki/logs/`. If publication fails after services succeed, use `just wiki-deploy` to publish the retained receipts; the failure log identifies the URL and connection error.

Use `just wiki-rollback` to restore the retained previous release. Inspect deployment receipts for scope and revision; these record successful deployment commands, not continuous health monitoring.

The [wiki operations guide](../../docs/operations/wiki.md) owns publication details. Read [add-on state backups](../../docs/operations/addon-state-backups.md) and [media configuration backups](../../usenet-infra/docs/scheduled-backups.md) for the state each system protects. NAS media is excluded from the settings-only backup scope.

The scoped media recovery deployment installs only reporting and Home Assistant notifications, validates the HA package, and publishes this guide after success. See the [media recovery runbook](../../usenet-infra/docs/native-media.md#seerr-recovery-reporting); promotion to automatic repairs is a separate change.

`just usenet-configure-seerr-sync` repairs only the Plex destination route and read-only sync checks. It preserves the default route and does not restart media services.

The [Sonoff recovery guide](../../docs/operations/sonoff-zigbee-thread.md) covers the preserved Zigbee network and the disabled Thread/Matter services. Its separate SOPS supplement stores the saved Thread credentials and encrypted-backup passwords; decryption with the existing recovery key was verified on October 16. Keep the actual Home Assistant and app backups as well. Enabling Thread later uses Home Assistant's retained credentials and does not require decrypting the supplement.
