# Usenet, NAS and Plex agent guide

Read the current handoff at the top of `../plan.md`, then `docs/operations.md`,
`docs/nas-plex-layout.md`, `docs/native-media.md` and `docs/scheduled-backups.md`. Chronological
notes describe earlier policies; they do not override the current handoff.

## Access and validation

- Use root `just usenet-*` recipes or `just --justfile usenet-infra/Justfile
  --working-directory usenet-infra ...`. The private `.env` and ignored Ansible
  inventory select dedicated cloud/NAS identities and verified host keys.
  Do not substitute SSH-agent credentials or print tokens/configuration secrets.
- Run the infrastructure `just test` recipe for implementation changes. It
  includes unit tests, shell/YAML checks, deployment syntax and a secret scan.
  The full scan currently fails on two documented historical RSA keys; report
  that result separately from passing tests. Do not add exceptions or rewrite
  history to make it green. `scripts/secret-scan --no-history` explicitly checks
  current sources/index only. See `docs/security-findings.md`.
- Runtime status must be checked before changing storage or restarting services.
  Preserve active transfers and manual SAB pauses. Scope restarts to the affected
  Usenet services; do not restart the NAS, Plex or unrelated containers by default.

## File ownership and recovery

- Radarr/Sonarr automatic search, RSS and native completed imports are enabled.
  `/library` is a real Storage Box SSHFS library, with completed scratch mounted
  at `/data/complete`. Preserve mount-dependent systemd startup and mode-0000
  unmounted directory protection. Never enable the retired publisher timer.
- Five legacy movies have server-side hard links into native movie directories;
  original catalog objects/manifests remain intact. Do not edit shared file bytes
  in place. Native upgrades replace files normally.
- The Storage Box is canonical; the NAS reader credential is server-enforced
  read-only. NAS copies remain selective. Prefer native Arr/Plex features for
  import and scanning; OliveTin is only the transitional copy/removal interface.
- The deployed NAS cache is `/share/FromDrobo/Movies`; application state remains
  `/share/Container/usenet`. Private inventory must retain `qnap_data_root:
  /share/FromDrobo` and `qnap_catalog_cache_dir: /share/FromDrobo/Movies` after an
  older recovery snapshot is restored. Do not silently redeploy the old cache path.
- Prefer same-volume renames, verify device/inode and destination absence, and
  preserve rollback settings. Do not recursively copy, hash or change permissions
  on the existing collection merely to reorganize paths. Manifest-managed file
  names must stay consistent with their verification records.
- The original SOPS-bound snapshot/inventory is immutable and its clean-clone
  secrets/state milestone passed. Do not regenerate keys or repeat purchases/setup.
  Whole-machine replacement drills remain separate. Scheduled backups allow an
  idle or fully paused SAB queue but reject post-processing. Never delete/resume
  jobs just to satisfy backup checks. NAS-loss protection is explicitly deferred.

- Checkout-local preservation and independent restore passed for snapshot
  `20260911T235253Z-9d6bbacf00ac982a`. See `docs/checkout-recovery.md`; rerun the
  current-files/published-source check before declaring a later checkout safe.
  This does not authorize deleting the checkout or imply NAS-loss protection.

## Plex privacy and playback

- Plex runs on the QNAP. `loljk` is the existing private library; preserve its
  files, library ID and root. Do not browse or emit its thumbnails/content while
  inspecting settings. General libraries must never include the share root.
- `Movies (NAS)` and `TV Shows (NAS)` are granted to managed profile `Movies & TV`
  and the two Remote libraries (IDs 2/3/4/5). Preserve `loljk` exclusion from home/global search and verify actual
  profile grants, not only presentation settings. Owner PIN/client startup
  configuration requires private user/device setup; do not invent a PIN.
- Plex watches local changes, performs partial scans and scans hourly; automatic
  trash emptying is disabled. Do not empty trash to resolve an unavailable mount.
- Native TV sorting and the read-only remote mount are deployed. Actual Apple TV/Roku
  playback and a convenient NAS copy action for new native-library titles remain. Do not claim file indexing proves playback
  or that a configured profile proves safe startup on every client.
