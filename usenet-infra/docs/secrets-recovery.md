# Secrets recovery inventory

The first recovery increment inventories the whole smarthome repository before
any vault migration. **Deleting the original checkout is still unsafe.** No new
master key, SOPS vault, independent archive destination, or clean-clone restore
has been implemented by this increment.

Run from the repository root:

```sh
just --no-dotenv secrets-check
just --no-dotenv secrets-check --json
just --no-dotenv secrets-check --manifest-only
```

The same recipe exists in `usenet-infra/`. The checker uses the repository's
Python runtime and standard library; it requires no network, account session,
SSH agent, age identity, or live service. The Usenet test recipe validates the
public manifest and runs isolated fixture tests, so tests also work in a clone
that has none of the ignored files. Use `--no-dotenv` as shown to prevent Just's
existing global settings from loading `.env` before launching the checker;
the checker itself never loads environment files.

## What the inventory establishes

[`recovery/inventory.json`](../recovery/inventory.json) is the versioned public
inventory, schema 1. Each local file has one exact repository-relative source
and future restore destination, service owner, sensitivity, target mode, format,
consumers, current key/backup dependency, rotation procedure, evidence, and
path-rebasing policy. It contains **path metadata only**, never secret values.

| Category | Intended handling in the later recovery implementation |
| --- | --- |
| `vault` | Small configuration/key inputs; migrate only explicitly listed files to master-encrypted exact-byte SOPS payloads. |
| `state` | Consistent encrypted state captures or historical recovery material; offline inspection before installation. |
| `archive` | Preserve the individually enumerated retained ciphertext; publish to the independent versioned destination with authenticated content checks. |
| External dependencies | Live HA/application state, account recovery and unresolved sources; never silently treat local metadata as verified recovery. |
| Exclusions | Exact named source files, provider caches, obsolete plans, candidate host pin and supplemental receipts; these are excluded from discovery/capture, not authorized for deletion. |

The initial review found 42 file entries: 39 present and three optional local
configuration files absent. It records 12 external dependency groups, including
Home Assistant Core, ESPHome, Supervisor add-on state, accounts and the future
independent master/ciphertext store. Eleven retained Usenet encrypted archives
are explicitly enumerated. Historical archives and old Terraform/NVM snapshots
are retained for review, **not selected as the default restore baseline**.

The checker never opens inventoried secret/state/archive files. It inspects
file type, byte count, POSIX mode, owner and hard-link count using directory
descriptors without following symlinks. It checks that each path is untracked
and protected by a repository `.gitignore` unchanged from HEAD; workstation-global ignores
and `.git/info/exclude` do not satisfy the clean-clone requirement. It rejects
unsafe writable parent directories and checks only the bounded discovery roots
in the manifest for unclassified files. It does not scan caches, Downloads,
live hosts, or every ignored directory in the repository. Adding a file outside
those roots requires updating the inventory through deployment-reference review.

Exit codes: `0` means the requested metadata/schema checks passed; `1` means
file metadata, portable ignore coverage or discovery needs attention; `2` means
the public manifest or local checking prerequisites could not be used safely.
External dependencies stay visible even when the metadata check passes, and
`deletion_safe` is always false. The checker does not authenticate ciphertext,
match keypairs, inspect ACLs, prove file freshness, or validate live credentials.
Future restore must create private directories at `0700` and secret files at
`0600`; this metadata check permits current non-writable shared directory modes.

The public manifest loader rejects symlinked paths and special files and limits
input size. When testing in a temporary directory on macOS, use its physical
path (for example `/private/tmp`, rather than the `/tmp` symlink). JSON output
contains filenames and metadata only. Do not add credential-bearing filenames
or credential values to the public manifest.

## Findings that must survive the handoff

1. **Old archive keys are indispensable.** The exact existing `cloud-admin`
   private key decrypts retained cloud, VPN, UniFi and USG backups; the exact
   `qnap-admin` private key decrypts the QNAP backup. Escrow both under the new
   master and verify every retained archive before any key retirement. A new
   SSH login key with the same filename cannot decrypt older archives.
2. **Full Home Assistant recovery is unproven.** The authoritative
   `/config/secrets.yaml`, `.storage` authentication/config entries/registries
   and `/config/esphome` are protected from ordinary config sync. The documented
   native add-on export excludes Core and is unencrypted. No independently
   retrievable full Core backup or exact retained add-on archive location was
   established by this inventory. Capture and test supported consistent backups.
3. **A tracked HA file needs private review.**
   `new-hass-configs/secrets.yaml` is tracked despite its ignore rule and contains
   a nonempty value not certified as a placeholder. It is not authoritative for
   deployment: staging copies the live remote secret file. No value is included
   here. Establish privately whether it is active sensitive material; if so,
   rotate the underlying credential and assess existing Git history. Do not
   automatically vault it or overwrite live HA secrets with it.
4. **Historical HA material needs classification.** Dated local config backups
   contain plaintext secret/ESPHome copies. The enumerated August 21 Z-Wave NVM
   snapshot predates intentional node removals and is not a current controller
   restore baseline. Preserve these files pending a separate exact-file review
   and obtain a fresh supported NVM backup. Never sweep every old backup into
   the vault or restore a stale controller image automatically.
5. **External recovery is a prerequisite.** UniFi's existing 1Password-managed
   identity, human passwords/MFA, private Git access and the password manager
   need independently tested recovery. No such keys were exported. The new
   master must have two independent copies; encrypted archives need a versioned
   destination outside the workstation, cloud VM, QNAP and canonical Storage Box.

During this increment, two local public host-pin files and the historical NVM
backup were tightened from `0644` to `0600`. Their content was unchanged. No live
configuration, accounts, keys or archive contents were changed.

## Native-age/SOPS bootstrap

The first master-key tooling increment is implemented, but **has not created a
master or vault yet**. It pins age 1.3.2 (including `age-keygen`) and SOPS
3.13.3 for Darwin/arm64 and Linux/amd64. Each binary is downloaded only from
the allowlisted official release hosts, SHA-256 verified, cached privately under
ignored `build/tools/`, and rehashed on every run. The compatible local binary
is also version-checked; both platform caches are usable offline after the
first verified fetch.

The next human action is necessary because the private recovery identity needs
two independently retrievable, operator-held copies. Store the generated
`SOPS_AGE_KEY` as a 1Password secret and arrange a separately retrievable copy
outside this checkout, the cloud VM, QNAP, and Storage Box. Do not use an SSH
key, a repository path, a shell-history command, or a password that merely
resembles a key.

With `SOPS_AGE_KEY` injected by the password manager, explicitly acknowledge
that plan from the repository root:

```sh
just --no-dotenv usenet-crypto-bootstrap
just --no-dotenv usenet-recovery-master-init second-copy-planned
```

It writes the identity only to an owner-only temporary file while reviewed
`age-keygen` derives the public recipient, then removes that temporary file.
It never writes the private identity to the checkout, command line, `.env`, or
output. Do this only after you have arranged the required independent second
copy of the same master.

The second command invokes reviewed native `age-keygen` without printing private
bytes. It prints only the public `age1...` recipient. Do not put the private
value in `.env`, logs, chat, CI, or a host being recovered.

On success the command creates two public, reviewable files: the recipient at
`usenet-infra/recovery/age-recipient.txt` and a root `.sops.yaml` whose sole
creation rule is for `usenet-infra/vault/*.sops.{yaml,yml,json,env,ini,bin}`.
Review and commit those public files separately; no vault payload is generated
by this step. The vault tool accepts only `SOPS_AGE_KEY` for one tightly scoped
process; it never belongs in command arguments or persisted shell configuration.

## Clean-clone secret setup

Once the public recipient/configuration and encrypted vault have been committed,
a clone restores its local inputs with one command:

```sh
just --no-dotenv setup-secrets
```

`setup-secrets` accepts only `SOPS_AGE_KEY`, injected by the password-manager
launcher for one child process:

```sh
# Have the password manager inject SOPS_AGE_KEY; never paste an actual key here.
SOPS_AGE_KEY="$PASSWORD_MANAGER_INJECTED_VALUE" just --no-dotenv setup-secrets
```

It rejects a missing or malformed identity and all unrelated `SOPS_*` settings.
The identity is never taken as a Just argument, stored in `.env`, printed,
parsed or forwarded beyond the SOPS child process.

The first operator vault capture uses the same identity input:

```sh
just --no-dotenv secrets-encrypt
```

It captures only the `vault` category in the public inventory into the single
Git-trackable ciphertext `usenet-infra/vault/secrets.sops.json`. Exact bytes are
base64-encoded inside the encrypted envelope; the source-checkout path and all
content hashes remain encrypted too. The command verifies that the supplied
identity can decrypt the just-written ciphertext before reporting success.
`state` and `archive` material are intentionally excluded.

On restore, the complete SOPS bundle is authenticated and schema-checked in an
owner-only temporary directory before any destination is written. It accepts
only inventory IDs and paths, validates checksums and required entries, safely
rebases only an exact checkout-path boundary where inventory policy permits it,
creates private directories, and installs files atomically with the inventory
mode. Existing destinations fail closed unless `--replace` is explicitly
provided; review conflicts before using that migration-only option. Neither
operation sources or evaluates restored content.

The complete intended sequence is therefore: clone → retrieve the independently
held master → inject it for `setup-secrets` → run `secrets-check` → perform
offline archive/state verification. This is not deletion-safe until the
separate escrow, independent-ciphertext retrieval and clean-clone drills pass.

Before encrypting, review path rebasing for `.env`, inventory, rclone and
Terraform inputs; preserve remote paths and resource IDs. The inventory is not
a restore executor or permission to evaluate recovered configuration.
Future restore must authenticate all ciphertext before any install, use strict
schema/path allowlists, avoid `source`/`eval`, and handle conflicting existing
files with recoverable prior versions.

Then escrow the existing archive identities, capture both independent Terraform
states without concurrent apply, select an independently retrievable ciphertext
destination, and implement the clean-clone and failure drills from plan.md.
Do not schedule retention, delete this checkout, or claim master-only recovery
until those acceptance gates and the second operator-led master retrieval pass.
