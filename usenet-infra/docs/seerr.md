# Seerr discovery and requests

Open [Seerr](http://10.77.0.1:15055/) on the home network or existing VPN route
and **sign in with the existing Plex owner account**. There is no new password.
Other Plex accounts cannot automatically enroll. Local-password login is enabled
for the user-approved Moonfin integration; the dedicated account can request
and auto-approve explicit requests but has no administration, advanced routing,
watchlist acquisition or separate-4K-copy permissions. Its credentials are stored
privately, never in the web configuration. Existing Plex sign-in remains enabled.
Browse trending/popular movies and TV, filter by genre, or search. Request a
movie or selected TV seasons; use Sonarr directly for individual episodes.
The default quality is Ultra-HD: prefer 2160p / 4K, with 1080p fallback when
no eligible 4K release is available. Both native profile ID 5 definitions allow
1080p beneath every 2160p source; retain that ordering when restoring profiles.
Availability comes from the four general Plex
libraries (IDs 2/3/4/5); private library ID 1 is excluded.

Seerr sends explicit requests to Radarr/Sonarr, which find releases through
Prowlarr, send them to SAB, import into the Storage Box and clean up completed
sources. Watchlist acquisition is off. Arr RSS polling remains off to preserve
the existing missing backlog; future episodes require explicit Sonarr searches.
Wait for a large request to finish before adding another. For automatically
selected releases, Arr blocklists a failed release and searches for an eligible
alternative under the same quality profile. Manually selected interactive-search
releases retain manual retry behavior. Failed payloads remain for review; the
100 GiB release limit and 30 GiB reserves still apply. This does not abort a
slow repair on a time limit, and replacements are not guaranteed to be available.

The existing single-copy server entries use the 4K quality profile; Seerr's
separate `is4k` server flag stays false because it enables a second parallel
copy workflow. Existing library items and pending requests are not bulk
upgraded or searched by a default-profile change. Automatic upgrades remain off.

Both NZBGeek and NZBFinder cart feeds remain disabled. Their credentials are
still used by Prowlarr for native searches. The three old paused requests,
44 journals and retired worker guards are preserved. Do not enable a cart or
restart its retired worker to test Seerr.

## Deployment and verification

The isolated `usenet-seerr` Compose project runs Seerr v3.4.1, pinned to digest
`sha256:f4768de5f616248d723e05891f3345a1402123775d03bf0890dbfedc0831bda1`.
The app listens only on loopback port 5055. Its private proxy listens on
10.77.0.1:15055 and rejects API-key authentication from remote clients.
The VPN firewall permits that UI only through the existing private tunnel;
Plex access is limited to the selected NAS host and port 32400 through IPsec.
No media storage is mounted into Seerr. The service runs as the existing
unprivileged identity with a read-only image and bounded temporary/cache space.

```sh
just usenet configure-seerr
just usenet seerr-status
just usenet native-ownership-status
```

Bootstrap privately derives the existing owner token from Plex preferences;
`secrets/seerr/plex-bootstrap.json` is ignored, mode 0600, and never printed.
The temporary remote bootstrap copy is removed even on deployment failure.
Future VPN role deployments must retain `cloud_vpn_seerr_nas_ip` in the private
inventory. Deployment does not restart Plex, SAB, Arr or Filex.

Status verifies selected library IDs, login policy, native connections,
Ultra-HD profile, watchlist policy and nonempty discovery feeds. Connection tests
do not prove a real request/import; no media is selected implicitly for testing.
The existing native import acceptance is documented separately in the plan.

Cloud encrypted backups include `config/seerr` (settings and SQLite database),
`compose/seerr` and the installed helper. Logs/cache are excluded. Restore into
an isolated directory first; reconstruct `usenet-seerr.service` from source and
reconcile private VPN policy before enabling. Replacement-host startup remains
separate from archive restoration.

To roll back the portal, stop and disable only `usenet-seerr.service`, retaining
its configuration/database for recovery. Keep both carts disabled; native Arr
manual requests remain available. Never restore historical cart/RSS policy.

Official references: [release](https://github.com/seerr-team/seerr/releases/tag/v3.4.1),
[Docker setup](https://docs.seerr.dev/getting-started/docker/),
[service settings](https://docs.seerr.dev/using-seerr/settings/services/).

## Availability sync and Plex routing

Plex must index an imported episode before its availability can be reconciled.
For the remote filesystem, watches are not sufficient: retain the hourly Plex
library scan. When recovering already-imported files, verify visibility through
the NAS reader mount, scan only the affected general-library folders, then run
Seerr's Plex Recently Added Scan from Settings → Jobs. Do not re-request the
media or manually mark it available to hide a sync failure.

Sonarr's automatic episode renaming is now enabled for future imports, retaining
the existing naming formats. This setting does not rename the existing library
or start downloads; recovery remains report-only. Preserve it on configuration
restore. It improves filenames after matching, but cannot identify an ambiguous
file or replace Plex's scan.

An older imported file can still be invisible to Plex when manual matching left
an opaque filename while episode renaming was disabled. Use the existing
Sonarr episode-to-file assignments as the authority. Save a private before
snapshot, verify the exact approved request seasons and file IDs, preview native
renames, require absent destinations, and submit `RenameFiles` only for those
verified IDs. First confirm imports and downloads are idle and retain the
complete naming configuration. Preserve the currently enabled renaming policy;
if any format changes are necessary for an explicitly authorized repair, restore
the saved formats after the scoped commands finish. Do not rename a whole library or
guess assignments from scrambled filenames. Verify unchanged episode bindings,
device/inode, size and modification time, then scan the affected Plex folders.
Keep the original recovery receipts immutable and record new paths separately.

Seerr uses ordinary outbound sockets. Its exact Plex-host route must select
`10.77.0.1` as the source so it matches the existing IPsec selector. A public
source can time out while an explicitly bound diagnostic connection succeeds.
The reviewed helper installs only a `/32` route for the configured Plex host,
using the existing default gateway/interface with a preferred VPN source.
It refuses unrelated exact-host routes and leaves the default route unchanged.
Existing firewall rules still require IPsec and approved ports. The address
service restores this route on boot; normal VPN and Seerr deployments reconcile it.

`just usenet configure-seerr-sync` installs that repair and read-only checks
without restarting Plex, Seerr, SAB or Arr. `just usenet seerr-status` now checks
an ordinary connection against Plex's saved server identity. The report-only
recovery monitor also alerts and holds proposals if any selected general
library's Seerr scan timestamp is missing or more than 20 minutes old. The
five-minute recently-added scan and nightly full scan remain native Seerr jobs.
The report-only monitor still cannot start scans, acquisitions or imports.

To investigate an availability gap, compare native file records and sizes,
Plex episode identities, Seerr scan freshness and request/season states in that
order. Preserve library IDs 2/3/4/5, disabled trash emptying, existing file IDs,
queue contents and acquisition settings. Verify fresh automatic scan timestamps
and fulfilled request seasons after repair. Exact operational evidence remains
in private runtime snapshots, not published media listings.

The October 16 sync repair verified all 191 requested episodes across three
series. Forty-two opaque filenames required native renames; all 189 physical
file identities and metadata were preserved. The source-route repair and scoped
folder scans restored native availability without acquisition commands. These
checks establish catalogue availability, not playback on every client.

## Safe settings and request scope

Recyclarr now owns future-import naming and disabled upgrade/Proper/Repack
settings for Sonarr and Radarr. It preserves the current formats, quality order
and per-movie exceptions. Existing files were not renamed. Approved requests carry
`seerr-approved`; existing movies outside approved requests are unmonitored, and
unrequested TV seasons remain unmonitored. Exact request and season bindings,
not tags alone, continue to define the report-only recovery scope.

Cleanuparr is evaluated in an offline dry-run lab against the five repaired
requests. It has no live service, credentials or media access. Its limited
force-import support cannot resolve the ambiguous episode mappings from those
repairs. Keep manual review for those cases and keep automated recovery
report-only. The [settings and qualification runbook](native-media.md#settings-ownership-and-offline-recovery-qualification)
records commands, evidence, official references, rollback and promotion limits.
