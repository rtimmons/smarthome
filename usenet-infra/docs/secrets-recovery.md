# Secrets and state recovery

The committed SOPS vault restores the small secrets/configuration inputs. The
native-age recovery package preserves both Terraform states and all retained
archives. The user selected the QNAP as the off-checkout ciphertext store and
confirmed the same recovery master is in 1Password (`SOPS_AGE_KEY`) and on paper
outside 1Password on September 11, 2026. No private master is installed on the NAS.

**The full clean-clone secrets/state drill passed; deleting the original checkout
is still unsafe.** Published revision `6fa9174` restored 24 vault entries and 15
NAS bundle entries, verified six keypairs, and restored zero new files on repeat.
See the [saved report](../recovery/drills/20260911T194408Z.json).
The Usenet prerequisite is complete; active work has returned to
[curated discovery](discovery.md). The original inventory's external-dependency
statuses are an inventory-time snapshot: its `planned` master/store and
`local-backup-only` archive labels predate the verified NAS retrieval and clone
drill. The vault cryptographically binds the entire inventory. Preserve that
exact manifest with this vault; updating those labels alone would invalidate
restoration. This paragraph and the saved drill report record current evidence
without changing the bound recovery policy.
Whole-Home-Assistant recovery has
separate unresolved gaps below. A NAS copy protects against Mac/cloud loss but
cannot survive loss of the NAS disks as well. This is the user's selected
failure scope, replacing the original requirement for an off-NAS backup store.

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
| `vault` | Small configuration/key inputs in the committed master-encrypted exact-byte SOPS vault. |
| `state` | Both local Terraform states captured under POSIX locks; historical material retained separately by exact inventory ID. |
| `archive` | All eleven retained archives validated and included in the master-encrypted package stored on the NAS. |
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
   master has two copies confirmed by the operator: 1Password and paper. The
   operator selected versioned QNAP ciphertext storage, accepting its shared
   NAS-disk failure domain. Git and password-manager account recovery remain
   external prerequisites.

During this increment, two local public host-pin files and the historical NVM
backup were tightened from `0644` to `0600`. Their content was unchanged. No live
configuration, accounts, keys or archive contents were changed.

## Native-age/SOPS bootstrap

The public recipient, SOPS configuration and encrypted vault are committed.
The bootstrap pins age 1.3.2 (including `age-keygen`) and SOPS
3.13.3 for Darwin/arm64 and Linux/amd64. Each binary is downloaded only from
the allowlisted official release hosts, SHA-256 verified, cached privately under
ignored `build/tools/`, and rehashed on every run. The compatible local binary
is also version-checked; both platform caches are usable offline after the
first verified fetch.

The existing private recovery identity is a random native-age key stored in
1Password's `SOPS_AGE_KEY` field; the operator also keeps the same key on paper.
Do not generate a replacement during an ordinary recovery. An SSH key or a
memorable password cannot substitute for this identity.

For a new installation only, initialize public metadata after arranging the
second copy. Ordinary recovery only needs the first bootstrap command:

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
mode. Identical destinations are accepted without rewriting and their modes are
repaired. Divergent destinations fail unless `--replace` is explicitly provided;
that option first preserves prior bytes privately beneath
`build/recovery-prior/<unique-id>/<original-path>`. Keep those prior copies until
replacement is verified. Ciphertext replacement is authenticated before atomic
publication. Neither operation sources or evaluates restored content. SOPS runs
with a private empty home directory and only the injected identity; ambient key
files, SSH agents and other providers cannot satisfy a wrong-key test.

## State and archive package

Run from the repository root, using a new absolute output directory each time:

```sh
just --no-dotenv usenet-crypto-bootstrap
just --no-dotenv recovery-capture --bundle /absolute/new/package-directory
just --no-dotenv recovery-store push --bundle /absolute/new/package-directory
```

Capture also creates the public receipt under `usenet-infra/recovery/snapshots/`.
Review and commit/publish that receipt before the fresh-clone drill. Verification
requires an exact match to this Git-carried receipt before it decrypts the NAS
package. A receipt fetched beside the ciphertext is not an independent integrity
anchor: anyone with a public age recipient can encrypt new data to that recipient.

Capture uses the committed public age recipient, never the private master. It
captures 15 present non-vault entries: two current Terraform states, the optional
prior cloud state, eleven retained archives, and the historical NVM image. Both
current state files are held under Terraform-compatible POSIX shared locks
throughout capture; active lock records, concurrent writers, changed files and
inode replacement are refused. This assumes the configured local state backends
and cooperating Terraform clients; never run Terraform with locking disabled.
No plan, apply, destroy, refresh or live service operation occurs.

Every retained archive is first authenticated using the exact escrowed SSH key.
Cloud archives validate the file allowlist, checksums and SQLite integrity;
QNAP, VPN and USG archives validate their respective exact formats. Native UniFi
exports must match recorded source hashes, but this is not a native UniFi
application-restore test. The historical NVM image remains stale, opaque material
for manual review, never an automatic controller restore.

The outer package is native-age ciphertext addressed directly to the dedicated
master. Old archive key bytes remain inside the SOPS vault and must be retained
while those inner archives exist. Future cloud/QNAP capture helpers currently
still encrypt their inner archives to SSH recipients; the outer recovery package
adds the dedicated age boundary without rotating or discarding those keys.

`receipt.json` records the snapshot ID, UTC capture timestamp, Git source
revision, inventory and vault fingerprints, native recipient, ciphertext size
and SHA-256, and expected entry IDs. Plaintext state hashes, lineage and resource
IDs are inside the authenticated package. The downloaded receipt is checked
against its Git-carried copy and then against the authenticated package. A
modified NAS receipt cannot redefine the expected checksum or make a substituted
package pass. Capture alone reports `master_decryption_verified=false`.
The receipt's source revision identifies the source checkpoint at capture, not a
claim that an uncommitted implementation has been published.

## NAS storage and retrieval

The dedicated directory is `/share/Container/usenet-recovery/<snapshot-id>/`.
It is outside the Usenet app and cache roots and contains only
`recovery.tar.age` and `receipt.json`. Directories are mode `0700`, files `0600`,
owned by the dedicated NAS deployment account. No private master is stored there.
Uploads use a unique staging directory and verify size and SHA-256 before
publication. Existing versions are immutable: an identical retry succeeds;
different content fails. No automated pruning or retention is enabled.

Transport uses the strict literal `.env` parser and the inventoried dedicated NAS
key and host pin. It never sources the file, uses an ambient SSH agent, scans new
host keys or falls back to other credentials. These retrieval credentials are
already in the small Git-hosted SOPS vault, so fetching does not depend on secrets
inside the package being fetched. Git/account access and a reachable surviving
NAS are external prerequisites. If the NAS configuration has also been lost,
restore the dedicated account/authorized key and independently confirm the host
pin before retrieval; the tool will not bypass those checks.

```sh
just --no-dotenv recovery-store probe
just --no-dotenv recovery-store fetch --snapshot SNAPSHOT_ID --destination /absolute/new/download-directory
just --no-dotenv recovery-verify --bundle /absolute/new/download-directory
just --no-dotenv recovery-restore --bundle /absolute/new/download-directory
```

Inject the existing `SOPS_AGE_KEY` for verify/restore only, through 1Password as
before. The master is passed privately to native age, never through a command
argument or durable key file. `--prompt-master` optionally reads it without echo
from an interactive terminal. All subprocess environments after decryption are
scrubbed. Restoring requires the matching small vault already restored in that
checkout, then authenticates all package content and verifies all six SSH
keypairs before installing state/archive files. All destinations are preflighted;
divergent existing files are refused. Identical files are left alone. Interrupted
restores can be repeated. State is installed at its inventoried path for offline
inspection; no application or Terraform process is started automatically.

## Full clone drill and remaining acceptance

The recovery implementation is published on `origin/usenet`. Inject the master
into one process and run:

```sh
just --no-dotenv recovery-drill --snapshot SNAPSHOT_ID --destination /absolute/new/clone
```

The drill requires a clean published source revision. It clones from GitHub,
bootstraps pinned public crypto tools, restores only the Git vault, retrieves the
NAS package with restored credentials, verifies all entries/keypairs, restores
state/archive paths, repeats restoration to prove idempotence, and runs the
metadata inventory check. It reads no original ignored inputs and produces a
sanitized `build/recovery-drill.json` in the fresh clone. It does not repeat the
previous isolated application-startup drills or perform a full NAS/UniFi/HA
machine replacement. Failure preserves the clone for diagnosis.

The September 11, 2026 drill completed at 19:44 UTC from published revision
`6fa9174bb27b482033c32f0c642e89134894ce29`, using snapshot
`20260911T191749Z-5150bea3423e3707`. The fresh clone restored 24 vault entries,
verified 15 bundle entries and six keypairs, restored 15 files on the first pass
and zero on repeat, and passed the inventory check. The operator's saved report
was inspected and copied as [public evidence](../recovery/drills/20260911T194408Z.json).
Application startup was not repeated; deletion safety remains false.

Before deleting the original checkout, preserve unrelated user work and all
other inventoried/external prerequisites, and resolve the HA and remaining
application/machine recovery gaps. Record actual results in `plan.md`; inventory success alone must
never be treated as deletion approval. Capture freshness, new archive inventory,
future native-recipient migration and manual scheduling/retention remain explicit
maintenance work. New files in bounded discovery roots require inventory review;
changing inventory policy also requires re-encrypting the small vault.
