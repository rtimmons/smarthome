# Application maintenance — prepared September 21, deployed September 22, 2026

**Approved, deployed and verified September 22.** Source and live versions now
match the reviewed pins below. Application health has zero findings, native and
discovery policy checks pass, and historical state remains unchanged. See the
[deployment receipt](../recovery/drills/app-maintenance-20260922.json).
Do not run broad cloud/discovery setup to repeat this maintenance:
the old discovery configurator refuses active native ownership and must not replay
its historical acquisition policy.

| Application | Previous image tag | Deployed image tag |
| --- | --- | --- |
| Radarr | `6.3.0.10514-ls315` | `6.4.4.10685-ls318` |
| Sonarr | `4.0.19.2979-ls323` | `4.0.20.3014-ls325` |
| Prowlarr | `2.5.2.5491-ls158` | `2.6.5.5623-ls161` |

All images use `lscr.io/linuxserver/<application>`. Exact stable tags were
confirmed against the publishers' [Radarr](https://github.com/linuxserver/docker-radarr/releases/tag/6.4.4.10685-ls318),
[Sonarr](https://github.com/linuxserver/docker-sonarr/releases/tag/4.0.20.3014-ls325)
and [Prowlarr](https://github.com/linuxserver/docker-prowlarr/releases/tag/2.6.5.5623-ls161)
release records. No floating tag or in-container updater is part of this change.

## Compatibility review

The exact old/new release source comparisons found unchanged Arr
`DownloadClientConfigResource`, `SabnzbdSettings` and import
`FreeSpaceSpecification` interfaces, and unchanged Prowlarr Radarr/Sonarr
application-sync implementations. Prowlarr's provider controller, indexer factory
and SAB settings also match. Version guards were updated together with the pins;
warnings still fail health checks and retired-worker startup guards remain intact.

[Radarr's release notes](https://github.com/Radarr/Radarr/releases/tag/v6.4.4.10685)
include hostname/trusted-network validation and import-related fixes;
[Prowlarr's notes](https://github.com/Prowlarr/Prowlarr/releases/tag/v2.6.5.5623)
also include hostname validation and a Newznab migration fix.
[Sonarr's notes](https://github.com/Sonarr/Sonarr/releases/tag/v4.0.20.3014)
include ordering the free-space check after other import specifications.
Treat database rollback as restoration of the stopped pre-update configuration,
not merely swapping an older image onto a possibly migrated database. Preserve
private proxy authentication and loopback bindings; test access after startup.
Live acceptance subsequently passed on the new versions, as recorded below.

## Recovery checkpoint and deployment sequence

`cloud-20260921T155229Z.tar.age` was encrypted on the cloud, uploaded and read back,
retrieved with matching ciphertext hash, then independently decrypted and restored
into a fresh private local directory. All 726 files and four databases verified.
All 59 selected live native configuration/helper/journal hashes match the restore.
The [recovery receipt](../recovery/drills/native-state-restore-20260921.json)
records scope and limits. Keep that checkpoint and the original bound snapshots.

The completed one-time runner lives in ignored
`build/continuation-20260921/upgrade-remote.py`; its local launcher is
`upgrade-launch.py`. Its remote maintenance directory already exists; do not
replay it. The approved deployment followed this sequence:

1. Recheck active native ownership, inactive retired timers, exact historical
   fingerprints, an idle/fully paused SAB queue and no active Arr/Prowlarr command.
   Hold the shared catalog lock; refuse deployed-source drift.
2. Pull only the exact candidate images, record resolved image identities and
   preserve old images. Recheck idle state before stopping applications.
3. Stop only Radarr, Sonarr and Prowlarr. Save their stopped configuration trees,
   deployed Compose files and changed version guards in a new root-private
   `/srv/usenet/backups/app-maintenance-20260921` directory. Preserve SAB and Filex.
4. Install the reviewed version guards and discovery Compose definition. Change
   only the Prowlarr image line in the existing cloud Compose file, preserving
   its deployed SAB restart/mount controls. Recreate only the three applications
   with `--no-deps`, wait for health, then run the native and discovery inspectors.
5. Verify exact versions, zero application health findings, unchanged queue/history
   and fingerprinted historical state, retained RSS-off policy and reserves, and
   unchanged SAB container identity/start time. Verify private proxy access.
   Record acceptance and refresh the encrypted backup after successful maintenance.

Each phase has a durable receipt. An interrupted or failed run must be inspected;
the launcher refuses an existing maintenance directory and must not be replayed
blindly. A stopped phase requires finishing or deliberate rollback. No automatic
rollback can assume there have been no new user requests or imports.

For rollback, first reconcile any new jobs with their native owner. Stop only the
affected application, preserve its current migrated state, then restore its exact
pre-update configuration and image together with matching version guards. Keep
new native jobs, historical receipts and manual pauses; never run the retired
importer against native-owned files. Recheck ownership, private access and health
before reopening requests.

## Validation

The infrastructure recipe ran **694 tests**, with **nine optional skips** and no
test failures. Compilation, shell/YAML and all deployment syntax checks passed.
The final full-history scan reported only the two documented historical RSA keys.
No exemptions were added. Those September 21 checks validated the prepared source;
no implementation changed during the September 22 rollout.

The three running image identities match their pulled images and all containers
are healthy. Discovery and native ownership pass, with zero application health
issues. Original queue/history/fingerprints and all catalog failure files match;
SAB's container ID/start time and all six mount/service unit hashes are unchanged.
NAS and Filex health pass. Private proxy requests without credentials return 401,
and authenticated backend APIs accept the proxy Host header. No new browser login
was performed. Cloud health fails only on the 14 preserved historical catalog
records, not application notices.

The original runner reached `applications_started`, then its existing command
allowlist refused Prowlarr `CheckHealth` before dispatch. Verification resumed
without redeployment: read Prowlarr's startup health, run the supported Arr health
checks, and verify native/discovery policy and unchanged historical state. The
durable maintenance receipt is now `verified`. All three stopped rollback
databases pass integrity checks; no automatic rollback was used.

Post-update archive `cloud-20260922T191826Z.tar.age` passed remote ciphertext
readback, independent decryption and isolated restore of 726 files/four databases,
including all 44 journals. All 59 selected live hashes match the restored files.
Keep this archive and the earlier checkpoint; neither proves replacement-host
startup or Filex recovery. TV-copy selection remains pending. No new media request
or held-record disposition was part of maintenance.
