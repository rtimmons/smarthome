# Disposable checkout and encrypted workstation recovery

Durable workstation inputs live at `~/.local/share/smarthome/tree/`, outside Git.
The private manifest at `~/.local/share/smarthome/manifest.json` records their
checkout-relative locations. `SMARTHOME_STATE_DIR` selects a separate restored
state tree for a drill or another controller. Never point it inside a checkout.

`just checkout-prepare` recreates ignored compatibility symlinks, refusing any
existing conflicting input or overlap with tracked source. Root ignore rules
explicitly cover symlinks as well as directories, preventing accidental staging
of private-path links. Directory links keep
future writes in the external tree. Individual private files beside tracked
source retain compatibility links; code that atomically replaces such a file
must reconcile that replacement into the external tree before another clean.
`just deploy` and its dry-run variants prepare these links before checking or
rebuilding pinned runtimes, including the wiki generator dependencies. Terraform
runs in an external working directory so atomic state replacements stay outside Git. The infrastructure Justfile reads its inventory directly from the external tree
and its dotenv through the compatibility link. Other standalone tools may need `just checkout-prepare`
first on a new checkout.

The supported command on an already provisioned controller is:

```sh
git clean -dfx && just deploy
```

Git, Just, uv, pyenv and system build/container prerequisites are controller
prerequisites. Node and the pinned Python version, virtual environments and
build artifacts can be rebuilt. This does not make an arbitrary new machine
ready without the documented initial tool setup. New recovery/bootstrap sources
must be tracked before running Git clean. Untracked new source work is still
subject to Git's normal deletion rules. Do not use `-ff` to remove nested Git
repositories, and do not run a destructive clean in the working checkout as a test.

## Encryption and the 1Password handoff

Current credential files also have a Git-tracked SOPS escrow at
`identity-infra/credentials.sops.json`, encrypted to this same workstation master.
Use `just credentials capture` after reviewed credential changes and
`just credentials verify` to compare and independently restore them.
`just credentials restore --destination /absolute/new-directory` creates a
separate private recovery tree; it never overwrites deployed credentials.
See [household identity](../operations/household-identity.md#git-tracked-sops-credential-escrow)
for scope, the historical master's distinction, native database recovery, and
the complete AD/Authelia/ACME architecture.

The new workstation recovery bundle uses native age with the repository's
existing SHA-256-verified, pinned bootstrap. It is additive: the original SOPS
vault, recovery master, bound inventory and immutable historical snapshots remain
unchanged. Existing SSH private keys are copied and byte-verified, never generated
again or rotated. Historical backup-decryption keys are preserved too.

The new master is an owner-only file at
`~/.config/smarthome/recovery.agekey`, outside both Git and the encrypted payload.
Save the complete file as a **1Password Document**, named **Smarthome workstation
recovery master**. Keep the existing historical SOPS recovery item as well.
An independent offline copy is recommended. Never paste the key into command
arguments, chat, source code, dotenv files or deployment logs.

Encrypted snapshots live under `~/.local/share/smarthome/recovery/`; `latest.json`
identifies the accepted archive and its SHA-256. Store a copy of the ciphertext
independently of the Mac. The key alone cannot reconstruct the ciphertext, and
the archive alone cannot recover its key. The operational tree is plaintext with
private parent directories; age encrypts the recovery snapshots, not an unlocked
application's working files. Host disk encryption remains a separate layer.

```sh
just checkout-state status
just checkout-state backup
just checkout-state restore --archive /absolute/snapshot.tar.gz.age --destination /absolute/new-state
SMARTHOME_STATE_DIR=/absolute/new-state just checkout-prepare
```

Set `SMARTHOME_RECOVERY_KEY` to an independently retrieved age key file for a
recovery drill. Restore requires a new destination and refuses overwrite. It
fully authenticates ciphertext before extraction, rejects unsafe archive paths
and special files, verifies every restored regular file against the encrypted
manifest, and rebases only the two known workstation configuration files. SSH
key bytes remain identical. Archived symlinks are recreated last and are never
followed during extraction. A wrong key or altered ciphertext installs no state.

Migration verifies the external copy and a complete encrypted round trip before
removing the original ignored inputs. A failed pre-migration copy can resume only
when copied bytes match. Local MongoDB must be stopped for migration and backup;
the tool refuses when that cannot be established. This is workstation recovery,
not a live NAS, HA Core or cloud database backup.

The migration conservatively preserves private operational records, backups,
inventories, local MongoDB, UI-created Home Assistant automations and nested
upstream source. Root `new-hass-configs/automations.yaml` is persistent UI state;
only the root scenes/scripts and the `generated/` directory are rebuildable.
Configuration uploads dereference file contents and exclude local build/evidence
directories, so Home Assistant never receives a workstation-path YAML symlink.
Use `just fetch-config` to synchronize UI automations into their external target. It excludes only named
rebuildable caches and generated outputs. Private manifests and archived filenames
can contain media identifiers and must never be committed or published to the wiki.

## Verification

```sh
just checkout-test
```

Tests use synthetic keys and actual age encryption, corrupted ciphertext, a wrong
key, conflicting destinations and a real Git clean. Production acceptance also
requires restoring the current encrypted archive into an isolated external tree,
creating a disposable checkout with the reviewed source, cleaning it, preparing
it using only the restored state, and exercising deployment. A dry-run is not
proof of a completed live deployment; record the two outcomes separately.
