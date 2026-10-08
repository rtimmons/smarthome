# Usenet, NAS and Plex agent guide

Read the [current plan and closure criteria](../plan.md), then [native media](docs/native-media.md),
[NAS/Plex layout](docs/nas-plex-layout.md) and [scheduled backups](docs/scheduled-backups.md).
Use [operations](docs/operations.md) for additional commands and
[validation](docs/validation.md) for accepted behavior and its evidence limits.

## Media privacy in commits

Never commit real media titles, release names, filenames, title-derived field
names, or identifying external catalog links/IDs from live operations. Use neutral
aliases such as `media-001` and descriptive keys such as
`failed_download_allocated_bytes` in receipts, documentation, tests derived from
live data, and commit messages. Keep exact operational filenames and alias
mappings in ignored private evidence and runtime journals. Review the entire staged
diff for these identifiers before committing; a generic secret scan does not
establish media privacy. Synthetic tests may use clearly invented fixture names.

Redacted receipt paths are aliases, not executable paths. Resolve actual paths
through exact native job/file IDs privately before operating on files. Historical
operational hashes remain dated evidence about the original inputs, not hashes
of subsequently redacted documents. Preserve private bound recovery snapshots
unchanged. Do not commit the private replacement map used for a privacy rewrite.

## Access and validation

- Use root `just usenet-*` recipes or `just --justfile usenet-infra/Justfile
  --working-directory usenet-infra ...`. Native/catalog recipes retain their
  unprefixed names at the root (`just native-status`, `just native-pull`).
  The private `.env` and ignored Ansible
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

- Radarr/Sonarr explicit search and native completed imports are enabled; RSS
  polling stays off under the September 20 native policy.
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
  jobs just to satisfy backup checks. NAS settings-only coverage is deployed with required recurring off-host readback.
  Original media is excluded by the user’s choice; never infer originals coverage.

- Checkout-local preservation and independent restore passed at the checkpoint
  recorded in the recovery ledger. Follow
  [checkout recovery](docs/checkout-recovery.md) and recheck current files, Git
  history/settings and published source before declaring a later checkout safe.
  Preserve the untracked `msg`. Do not delete the checkout as part of a handoff
  update or imply NAS-loss protection. Original bound evidence stays immutable.

## Plex privacy and playback

- Plex runs on the QNAP. `loljk` is the existing private library; preserve its
  files, library ID and root. Do not browse or emit its thumbnails/content while
  inspecting settings. General libraries must never include the share root.
- Managed profile `Movies & TV` is granted exactly `Movies (NAS)`, `TV Shows (NAS)`,
  `Movies (Remote)` and `TV Shows (Remote)` (IDs 2/3/4/5); private `loljk` is ID 1.
  Preserve its exclusion from home/global search and verify actual profile grants,
  not only presentation settings. Owner PIN/client startup
  configuration requires private user/device setup; do not invent a PIN.
- Plex watches local changes, performs partial scans and scans hourly; automatic
  trash emptying is disabled. Do not empty trash to resolve an unavailable mount.
- Native TV sorting, the read-only remote mount and native selective-copy actions
  are deployed. The user confirmed Apple TV and Roku playback and restricted privacy on September 22.
  Record this as user verification, not an agent-run codec/subtitle matrix or proof for every future client.

## Current operation

- Seerr at `http://10.77.0.1:15055/` uses Plex sign-in and only libraries 2/3/4/5.
  Keep local login, registration, watchlist acquisition, RSS polling and direct
  carts disabled. Ultra-HD prefers 2160p with 1080p fallback; no automatic upgrades.
- Radarr/Sonarr own new downloads, imports and completed-source cleanup. The
  publisher, cart importer, capacity admission and incomplete maintenance workers
  are retired. Their source and migration commands have been removed; never
  restore or enable them from an old archive. Keep their journals and receipts.
- Preserve the 100 GiB release limit, both 30 GiB SAB reserves, Arr free-space
  checks and hardlinks, the 100 GiB NAS reserve, mount-dependent startup and
  mode-0000 unmounted directories. Do not modify shared hard-linked bytes in place.
- Preserve current private overrides: BX21, `repair_spool_enabled = true`,
  `qnap_native_tv_copy_enabled: true`, and `qnap_backup_offhost_required: true`.
  Restore current settings and mount identities; do not replay the historical
  storage migrations or reformat the repair volume.
- Filex uses `just usenet-filex-ui` and `http://127.0.0.1:15213/` through a pinned
  SSH tunnel. Keep host trust policy unchanged: no CA installation or TLS bypass.
  Preserve its reviewed image, verified transfers, quarantine and disabled purge.
  Canonical roots are read-only; staging is excluded from configuration backups.
- The static private wiki is deployed at `http://192.168.1.66:8090/`. Edit `wiki/`
  and deploy only through `just usenet-wiki-deploy`. It must not gain credentials,
  live APIs, media listings, Docker access or public exposure.
- Before live changes, use the read-only health commands in the README. Do not
  restart services, inspect private media or enqueue requests merely to audit.
- October 8 closure and its limits are recorded in `plan.md` and
  `recovery/drills/closure-20261008.json`. Dated recovery records are evidence,
  not instructions to replay. Preserve original SOPS-bound snapshots unchanged.
- No PRs. Ask before taking a Git lock, as required by the root guide. Preserve
  unrelated changes, ignored private inputs and `msg`; do not delete refs or
  worktrees as part of consolidation.
