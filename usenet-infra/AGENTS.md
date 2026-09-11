# Usenet, NAS and Plex agent guide

Read the current handoff at the top of `../plan.md`, then `docs/operations.md`,
`docs/nas-plex-layout.md` and `docs/media-workflow-review.md`. Chronological
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

- Radarr/Sonarr automatic search and monitored RSS are enabled. Native completed
  imports remain disabled: `/library` is still metadata-only, with no real media
  mount. Preserve that distinction when reporting an item as downloaded/imported.
- The cloud `usenet-publish.timer` owns successful SAB completed directories.
  Its worker uses stable job IDs, remote checksums/manifests and durable receipts
  before local cleanup. Never run another mover against those directories.
  Disable the timer and let any active publisher finish before transitioning to
  native Arr imports. Remote Path Mappings do not transfer files.
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
  Whole-machine deletion safety remains unproven. Supplemental backups currently
  require an empty SAB queue; do not delete/resume jobs just to satisfy that check.

## Plex privacy and playback

- Plex runs on the QNAP. `loljk` is the existing private library; preserve its
  files, library ID and root. Do not browse or emit its thumbnails/content while
  inspecting settings. General libraries must never include the share root.
- `Movies (NAS)` and `TV Shows (NAS)` are granted to managed profile `Movies & TV`
  only. Preserve `loljk` exclusion from home/global search and verify actual
  profile grants, not only presentation settings. Owner PIN/client startup
  configuration requires private user/device setup; do not invent a PIN.
- Plex watches local changes, performs partial scans and scans hourly; automatic
  trash emptying is disabled. Do not empty trash to resolve an unavailable mount.
- TV sorting/native Arr imports, a remote playback mount, and actual Apple TV/Roku
  playback are separate pending work. Do not claim file indexing proves playback
  or that a configured profile proves safe startup on every client.
