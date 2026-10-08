# Radarr, Sonarr and Prowlarr

The current workflow uses Seerr or explicit Arr search, with native imports and
completed-source cleanup. RSS polling stays off to preserve the existing backlog.
Prowlarr supplies two configured indexers; direct Prowlarr downloads and both
cart feeds stay disabled. Failed removal, automatic retries, automatic import
lists and watchlist acquisition remain disabled.

Images and API version guards are pinned in `compose/` and
`scripts/discovery-config.py`; update them together. Saved resource names
(`Manual discovery only`, `SABnzbd manual discovery`) identify existing resources,
not the current capabilities. Preserve their IDs and keys when restoring state.

Each Arr app has one SAB client with its own category (`radarr` or `sonarr`).
`/library` aliases its subtree of the common `/storage` bind so completed files
and imports can hardlink. No writer key or incomplete-download mount enters the
Arr containers. See [native media](native-media.md) and [repair storage](repair-spool.md).

## Operation and recovery

```sh
just usenet-discovery-health
just usenet-native-ownership-status
just usenet-cloud-health
```

The discovery inspector is read-only and requires the native marker, reviewed
versions, expected indexers/clients, RSS interval zero and no unexpected app
warnings/errors. The old setup configurator was removed because it represented
the superseded acquisition policy. Restore accepted configuration from backups;
do not reconstruct it by replaying historical setup commands.

`usenet-configure-discovery` deploys pinned applications and verifies restored
settings. It requires existing native ownership and reconstructed storage units.
`usenet-configure-native-ownership` refreshes health helpers without restarting
applications or migrating data. Keep private backend ports, proxy authentication
and mount-dependent startup. Stop only `usenet-discovery.service` for Arr
maintenance; do not prune configuration volumes.

[Scheduled backups](scheduled-backups.md) include application databases and
ownership receipts. Restore into an isolated destination first, verify databases
and current settings, then follow [recovery](recovery.md). Historical supplemental
archives remain recoverable with the cloud backup verifier; their pre-native
settings must not replace the accepted current policy.
