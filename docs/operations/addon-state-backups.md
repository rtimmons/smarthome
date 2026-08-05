# Add-on state backups

Talos creates a native Home Assistant Supervisor partial backup containing all seven add-ons discovered from the repository plus the complete `/share` folder. This preserves private add-on `/data` directories, including MongoDB and Node Sonos state, without duplicating Supervisor's backup format.

## Create a backup

Deploy the MongoDB, Printer, and TinyURL reliability changes before the first run. The deployed MongoDB add-on must report `startup: system` and `backup: cold`; Talos rejects older configurations before creating an archive. Printer and TinyURL must also pass database-backed health checks.

Run:

```bash
just addon-state-backup
```

The recipe builds Talos and invokes the equivalent command using the repository's `HA_HOST`, `HA_PORT`, and `HA_USER` conventions:

```bash
talos backup addon-state
```

Use `--output-root PATH` on the Talos command, or pass the same option to the recipe, to override the local output root.

## Operational behavior

The current state is approximately 1.28 GiB, so allow materially more than that on both Home Assistant's `/backup` volume and the local destination. Talos currently requires at least 2 GiB free remotely. No automatic pruning occurs.

MongoDB uses a Supervisor cold backup. Supervisor briefly stops MongoDB while copying its private data and starts it again afterward. Talos polls every add-on that was originally running and fails loudly unless application-level health recovers. Printer's `/health/mongo` and TinyURL's database-backed `/api/urls` endpoint must work both before and after backup creation.

The backup is intentionally unencrypted. It may contain sensitive add-on data and everything under `/share`. Talos sets the local directory to mode `0700`, all local files to `0600`, and the remote archive to `0600`. Protect both machines and their storage accordingly.

This artifact is a focused operational export, not a complete backup strategy. Home Assistant's current guidance recommends encrypted backups with multiple locations, and its 3-2-1 guidance calls for three copies on two media with one off-site. Continue Home Assistant automatic encrypted backups or another off-site workflow alongside this command. See [Home Assistant's backup tasks](https://www.home-assistant.io/common-tasks/general/), [3-2-1 backup guidance](https://www.home-assistant.io/blog/2025/01/03/3-2-1-backup/), and [current backup encryption guidance](https://www.home-assistant.io/blog/2026/03/26/modernizing-encryption-of-home-assistant-backups/).

Home Assistant generally recommends omitting `/share` and media from routine backups to keep archives and restores small. This command includes `/share` deliberately because Printer output and other repository-owned file state are in scope. The custom add-ons otherwise keep private persistent state in `/data`, matching the [app configuration guidance](https://developers.home-assistant.io/docs/apps/configuration/). If a future add-on needs user-editable private files, prefer `addon_config` instead of adding another global shared folder.

## Output and retention

Each successful run publishes atomically under a UTC timestamp:

```text
backups/addon-state/20260805T123456Z/
├── smarthome_addon_state_20260805T123456Z.tar
├── manifest.json
└── SHA256SUMS
```

The native `.tar` remains in `/backup` on Home Assistant as well. Talos verifies exact component membership, archive size, outer tar members, embedded `backup.json`, and a remote-versus-local SHA-256 before publishing the local directory. A failed transfer or verification leaves the remote backup in place for diagnosis and cleans the local staging directory.

The external manifest contains no add-on options, tokens, passwords, MongoDB URIs, or Node Sonos settings. It records:

- Schema and UTC creation time
- Git revision and dirty flag
- Home Assistant Core and Supervisor versions
- Repository keys, manifest slugs, installed IDs, versions, and original states
- Backup slug, name, filename, exact components, byte size, compression/protection flags, remote path, and SHA-256

## Restore contract

No restore command is included yet. The manifest is the contract for a future `talos backup restore-addon-state` workflow. That command will verify this metadata and checksum, create a safety backup, upload/reload the native archive when necessary, restore only `/share` and these seven add-ons in dependency order, preserve their recorded states, and run the same health checks.

Partial Supervisor backups must be restored with an explicit component selection. This matches [Supervisor maintainer guidance for partial CLI restores](https://github.com/home-assistant/supervisor/issues/5637) and is why the manifest records the exact add-on IDs and `/share` rather than relying on an implicit full restore. Also size the restore target from the installed system's disk use, not only the compressed archive size; restore requires working space beyond the `.tar` file.

Until that command exists, use Supervisor's native restore UI or CLI only with deliberate operator review. Restoring add-on state is destructive and should not be inferred from the presence of a backup.
