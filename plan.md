You are my implementation agent. Starting from a cold state, guide me interactively through creating the required accounts and then build, configure, test, and document a reproducible Usenet acquisition and storage system.

Do not merely give me instructions. Perform everything you reasonably can using the tools available to you. Stop for me only when human interaction is actually necessary, such as payment, CAPTCHA, 2FA, entering a secret that you should not see, or making an irreversible purchasing decision.

Keep this document updated as agents make progress.

## Resume here — current handoff, September 11, 2026

This section is authoritative over chronological notes below. The Usenet
secrets/state milestone is closed; Radarr/Sonarr discovery, automatic publication
and the NAS/Plex layout are deployed. Continue with native import/storage and
playback validation as described below. The small SOPS vault, locked Terraform
state/archive capture, immutable QNAP ciphertext store, offline content checks,
and full-clone drill tooling are implemented. Do not repeat account setup,
purchases, credential generation, NAS bootstrap, diagnostic downloads or VPN
provisioning. Read `usenet-infra/AGENTS.md` before operating this stack.

**Current recovery milestone:** NAS snapshot
`20260911T191749Z-5150bea3423e3707` contains all 15 present non-vault entries,
including both current Terraform states and all eleven retained archives. Its
61,250,344-byte ciphertext was uploaded, downloaded into a separate directory,
and verified byte-identical. The user then ran `recovery-verify` with the actual
master: all 15 entries authenticated/validated, all six SSH keypairs matched,
and `master_decryption_verified` was true. Cloud backups each passed two SQLite
integrity checks. No live application or Terraform state was restored or changed.

The user explicitly selected **QNAP NAS storage**, replacing the proposed
requirement for a store independent of the NAS. The immutable directory is
`/share/Container/usenet-recovery/20260911T191749Z-5150bea3423e3707/`, outside
application/cache roots. This protects Mac/cloud loss; it cannot survive loss
of the NAS disks as well. On September 11 the user confirmed the same master
is in 1Password (`SOPS_AGE_KEY`) and written on paper outside 1Password. Count
that independent-copy requirement as done; do not ask again or generate a key.
The private master remains absent from repository files, NAS and agent context.

**Full clean-clone secrets/state drill: passed.** On September 11 at 19:44 UTC,
the operator ran the drill from published revision
`6fa9174bb27b482033c32f0c642e89134894ce29`. The fresh GitHub clone bootstrapped
pinned public tools, restored 24 vault entries, fetched the NAS snapshot using
restored credentials, verified all 15 bundle entries and six keypairs, and
passed the inventory check. The first pass restored 15 state/archive files;
the repeat restored zero new files. The saved report and clean clone were
inspected. Public evidence is committed at
`usenet-infra/recovery/drills/20260911T194408Z.json`; the original report is
`/Users/rtimmons/scratch/2026-09-11/smarthome-full-dr/build/recovery-drill.json`.
This closes the planned clean-clone Usenet secrets/state milestone.

To repeat with a new destination, inject the existing master and run:

```sh
just --no-dotenv recovery-drill --snapshot 20260911T191749Z-5150bea3423e3707 --destination /absolute/new/clone
```

The destination must have an existing operator-owned non-writable parent. The
drill clones `origin/usenet`, requires the exact published current revision,
bootstraps public pinned tools, restores the vault, fetches NAS ciphertext using
restored credentials, verifies/restores state and archives twice, and records
`build/recovery-drill.json`. It reads no original ignored files.

**Deletion safety: not ready.** Whole-HA recovery, native UniFi restore,
application startup from this new clone and unrelated local user work remain
separate deletion prerequisites. The successful drill explicitly reports
`deletion_safe: false`. The user approved staging, committing and publishing
this recovery checkpoint and its handoff updates; do not ask again for those
actions. Implementation commit `ea73226` and the tested handoff revision above
are published on `origin/usenet`.

**Security audit finding:** expanded whole-main-repository source/index scanning
passes, but reachable history contains two distinct RSA private keys committed
in 2017–2018 and deleted from working files in 2018. Neither matches the six
current dedicated identities. Live revocation of the historical Raspberry Pi
consumers is unverified. See `usenet-infra/docs/security-findings.md` for public
fingerprints, commits and consumer evidence. No keys were used, no history was
rewritten, and no scanner exception was added. Full `secret-scan` intentionally
fails on those findings; do not claim the repository's history is credential-free.

### Live system and operating entry points

| Component | Current verified state |
| --- | --- |
| Cloud | Hetzner `usenet-acquisition`, IPv4 `89.167.18.138`; Ubuntu 26.04; SABnzbd, Prowlarr, writer/catalog, private proxy and strongSwan |
| Storage | BX11 canonical Storage Box; QNAP subaccount is server-enforced read-only; VM scratch and NAS cache are disposable |
| NAS | `usenet-deploy@rynapqnap.local`, LAN `192.168.1.66`; QNAP TS-451D2/QTS 5.2.10.3577; UID:GID `1004:100` |
| QNAP data | Application root `/share/Container/usenet`; cache `/share/FromDrobo/Movies`; 100 GiB minimum free space |
| UniFi | Cloud Key `192.168.1.180`, UniFi OS 5.1.31/Network 10.6.101; USG 3P `192.168.1.1`, firmware 4.4.57.5578372 |
| Search | `http://10.77.0.1:19696/`: catalog credentials in browser popup, then existing Prowlarr Forms credentials |
| Downloads | `http://10.77.0.1:18080/`: catalog credentials in browser popup |
| Catalog/cache | `http://192.168.1.66:1337/`: existing dashboard login; explicit Download/Remove actions |

The user confirmed both cloud UIs and the QNAP dashboard work. UniFi maintains
the private route automatically; no workstation tunnel is needed. IPsec protects
gateway-to-cloud traffic; these URLs still use HTTP within the trusted LAN.
Home Assistant can link to them but does not carry the tunnel. Eweka is the only
provider; **UsenetExpress is explicitly deferred until actual completion gaps
justify it**. NZBGeek and NZBFinder Pro are paid, enabled and tested. Provider,
indexer and application credentials stay in private forms/files, never chat.

**Curated discovery is live.** The user selected Radarr and Sonarr on September
11. Movies are at `http://10.77.0.1:19696/radarr/`; TV is at
`http://10.77.0.1:19696/sonarr/`, using the existing catalog login. Prowlarr syncs
both existing indexers with interactive/automatic search and RSS enabled, as
explicitly authorized on September 11. RSS runs every 15 minutes for monitored
titles; existing monitoring selections are preserved. Both apps have a tested SAB client; completed imports, automatic
retries and download removal are disabled. They have no download or canonical
storage mounts. Initial setup added no titles or list subscriptions; the user
subsequently downloaded four movies. A request portal remains deferred.
See `usenet-infra/docs/discovery.md`.

Live acceptance: Radarr Discover returned 30 movies; movie/series metadata
lookups returned results; both private routes return 401 anonymously. The two
application configurations repeat without writes after accounting for the API's
masked credential responses. The current policy permits only the disabled-import
health notice; RSS/search problems now fail the check. Existing cloud/catalog health
passes, with the same seven historical SAB warnings. The in-app browser blocked
the private VPN URL, so visual login acceptance remains for the user's browser.

**Automatic search and RSS update verified.** Both apps report automatic search
and RSS enabled at 15-minute intervals, with imports still disabled. The 398-case
Usenet suite passed with eight opt-in skips. Encrypted supplemental snapshot
`20260911T210232Z-ae56b33b7f0488c7` was uploaded, fetched and decrypted successfully.
The source changes and receipt are included in the September 11 automation and
NAS/Plex checkpoint; no newer complete secrets/state drill has been performed.

**Automatic publication and NAS/Plex layout deployed.** The publisher processed
all four completed movies, verified remote bytes/manifests and reclaimed cloud
scratch; free space rose from 55.1 to 123.7 GiB. The NAS catalog's existing tab
now refreshes automatically. Its cache was renamed on the same volume from
`/share/Usenet/usenet-cache` to `/share/FromDrobo/Movies`, alongside `loljk` and
the new `TV Shows` directory; zero media bytes were copied by that move. Private
inventory and live Compose bindings agree. Plex libraries `Movies (NAS)` and
`TV Shows (NAS)` use separate roots. The `Movies & TV` managed profile sees
only those libraries; direct private-library access returned 403. The original
5,258 entries, media path and directory inode were preserved. Plex home/search
visibility excludes the private library, partial scans and hourly fallback are
enabled, and automatic trash emptying is disabled. The owner's PIN and TV-client
profile selection still require the user's private/client-side setup.

The first real movie NAS pull completed and passed SHA-256 verification;
Plex automatically indexed `media-003` in `Movies (NAS)`. The 13.5 GiB copy
took approximately 30 minutes with variable throughput. Actual TV-client
playback remains untested. Native Arr imports and remote Plex mounts are not
deployed; do not run another file mover against
the automatic publisher's sources. See `usenet-infra/docs/nas-plex-layout.md`
and `usenet-infra/docs/media-workflow-review.md`. Latest local validation ran
406 cases (398 passed, eight opt-in skips); source/index secret scanning passes,
while the full test recipe still fails on the known historical RSA-key findings
described above. A new supplemental backup was refused by the existing
empty-SAB-queue requirement (three jobs remain paused); the previous verified
snapshot remains available. Do not empty or resume that queue just for a backup.

Next: pilot a real mounted library with native Arr completed imports, coordinating
file ownership with the publisher; validate remote-read performance before
exposing a remote Plex library. Keep NAS copying selective. Test Apple TV/Roku
playback and startup using the restricted profile. Repeat supplemental cloud/NAS
backups when their existing idle checks permit; preserve the original bound
recovery snapshot. Do not claim the new Plex state is covered by the old backup.

**New app-state backup is verified on the NAS.** Supplemental snapshot
`20260911T201003Z-bcb62179eb783aef` contains 601 files and four SQLite databases;
13,315,460 ciphertext bytes, SHA-256
`84ece70d8f020b48fbe353e174f7e2755f469d500aa484a11f0e702b5432bd98`.
Capture, decryption, NAS upload/download and repeat decryption all passed.
The downloaded copy also decrypted with the cloud-admin key restored by the
earlier clean-clone drill. This supplemental cloud-config archive uses that
escrowed key; restore it with `usenet-backup-verify` / `usenet-backup-restore`,
not the master-bundle verifier. Preserve the original SOPS-bound inventory and
full-clone baseline. Public evidence lives in
`usenet-infra/recovery/application-backups/20260911T201003Z-bcb62179eb783aef.json`.
`just usenet-discovery-backup` repeats this operation without needing the master
or changing the bound inventory; retention remains manual.

Discovery validation: the final Usenet run executed 397 cases (389 passed,
eight optional runtime skips); all 13 isolated proxy tests passed separately,
including the eight runtime cases. Compilation, ShellCheck, JSON/YAML and four
Ansible syntax checks passed. Current source/index secret scanning passes; the
whole-history step still fails only on the two documented old RSA keys.
The final `just test` also passed all repository tests and all seven add-on
container checks. The user explicitly approved staging, committing and pushing
the discovery checkpoint and its public recovery evidence to `origin/usenet`.

From repository root use `just usenet-test`, `just usenet-cloud-health`, and
`just usenet-qnap-health`. Catalog reads use `just --justfile usenet-infra/Justfile
--working-directory usenet-infra catalog-list` (or `catalog-status`). On this workstation `just` is
`/opt/homebrew/bin/just`; use the repository runtime wrappers. The ignored
`usenet-infra/.env` supplies exact SSH targets, dedicated identities and host pins.
For a reviewed cloud command use `just --justfile usenet-infra/Justfile
--working-directory usenet-infra --command ./scripts/cloud-command <arguments>`.
Never fall back to arbitrary SSH-agent identities for cloud/NAS access.
Ansible's actual deployment values are in ignored `usenet-infra/ansible/inventory.yml`.

The legacy USG needs the checked-in `usenet-infra/unifi/config.gateway.json`
installed on Cloud Key at `/data/unifi/data/sites/default/config.gateway.json`
(`unifi:unifi`, 0644). The UI alone incorrectly generated IKEv1 and a printer
tunnel. The override creates dedicated crypto groups, uses only main LAN
`192.168.1.0/24` ↔ `10.77.0.0/30`, and disables the printer tunnel. Only cloud
`10.77.0.1:18080/19696` is permitted. WAN is currently `100.1.188.109`; WAN or
LAN/VLAN changes require selector/peer/firewall revalidation. See
`usenet-infra/docs/lan-ui.md` for rebuild/rollback. Do not reboot the gateway or NAS.

Cloud Key SSH uses the existing 1Password agent; do not export that private key.
USG public-key login still fails; the existing UniFi-managed device login was
used in memory for read-only inspection, with the preexisting pinned host key.
Do not assume old browser handles, temporary SSH sockets, or ignored `build/`
inspection scripts survive a fresh session. Cloud Key pin:
`SHA256:mokbmi/Llxd7MGWd+/XUzBf4xHW8MNofYHkSrfUVfJI`; USG ED25519 pin:
`SHA256:kMYrptArIjGa62CAcE/5RSvxwgZXXRqffFRkIdTnIMQ`. NAS approved first-use RSA
pin: `SHA256:jXVysXlhzn80Tk2BYg8CGNkfMCqjCEpyu0PyyHJX5RA`. Preserve actual
known-host files and reject unexpected changes. Home Assistant has its separate
repository identity and mandatory failure procedure in `AGENTS.md`.

### Acceptance and remaining limits

Verified: official 100 MB Eweka diagnostic through canonical promotion and NAS
download/hash/removal; QNAP read-only enforcement; dashboard authentication and
restart persistence; isolated cloud/QNAP application restore drills; LAN login
to both cloud UIs; anonymous denial; blocked backend/public ports; exact IKEv2
selectors; explicit PFS14 rekey; automatic reconnection after cloud-only
strongSwan restart; unchanged default route/old site VPN configuration; cloud
Ansible repeat convergence with zero changes. Before this state/archive increment,
the Usenet suite had 292 cases: 285 pass, seven opt-in skips; those seven proxy runtime cases
previously passed separately during LAN implementation. Prior checkpoint `just test` also passed:
Talos 118 tests (11 slow deselected), grid dashboard 102, printer 225 including
browser tests, snapshot 7, tinyurl 16, Sonos tests/builds, and all seven add-on
container checks. That earlier `just usenet-test` run passed compilation, ShellCheck,
JSON/YAML, three Ansible syntax checks and secret scans. Independent security
review found no concrete commit blocker; this is not a guarantee against all
vulnerabilities. Historical counts later in this file reflect earlier stages.

Remaining independent work: historical-key authorization review; backup
freshness, scheduling and retention; optional LAN HTTPS
and Home Assistant navigation/status; full machine replacement drills. The
external public-IP test of NAS port 1337 was rejected by automatic approval
review and still needs explicit approval; do not retry it under VPN authorization.
SAB has seven historical setup/Direct Unpack warnings, with current storage,
Prowlarr and catalog health passing. Legacy USG uses AES-256/HMAC-SHA1/DH14/PFS;
replace with modern cryptography when hardware supports it. No secrets were reset
to resolve the two-stage Prowlarr login.

The work is on branch `usenet`, remote `origin` is
`git@github.com:rtimmons/smarthome.git`. Only this task's `Justfile`, `plan.md`, and
`usenet-infra/` changes belong in its commits. The unrelated untracked
`grid-dashboard/ExpressServer/src/public/mobile-layout-mockups.html` is user work;
preserve it separately before deleting the checkout. Do not silently commit or
remove it. Ignored evidence is supplemental; the verified outcomes and backup
paths/checksums necessary for recovery are recorded in this document.

Checkpoint: implementation and handoff commit `1c359f6`. Both required test
recipes and the staged-content secret scan passed before commit. The user
explicitly approved publication to `origin/usenet`; the branch was pushed
successfully, including checkpoint notes commit `61f50be`. Clone with
`git clone --branch usenet git@github.com:rtimmons/smarthome.git`, then read this
file first. This is a published feature branch, not a merge into the default
branch. It preserves source, not the ignored recovery material described above.

GitHub's push response reported 53 dependency alerts on the repository's default
branch (30 high, 23 moderate). Their applicability to this branch/Usenet was not
established by the functional tests or this focused code review. Add a separate
dependency-alert triage before claiming repository-wide security readiness;
inspect actual affected packages, reachable paths and available fixes rather
than doing blind major-version upgrades. This handoff does not certify the
whole smarthome repository free of vulnerabilities.

## Completed milestone — master-key secrets and clean-clone recovery

Requested outcome: delete this checkout only after a fresh clone plus one
independently held recovery master can restore the required secrets and retrieve
state backups. The Usenet secrets/state portion passed the clean-clone drill
recorded above. Whole-checkout deletion has separate unresolved prerequisites.
The following notes retain the implementation history and original constraints.

### Inventory increment — September 11, 2026

Implemented the public, versioned exact-path inventory at
`usenet-infra/recovery/inventory.json` and the repository-root/infrastructure
`just secrets-check` recipes. The initial review covers 42 local file entries
(39 present, three optional configurations absent), eleven retained Usenet
archives, both independent Terraform states and their live inputs, all five
Usenet keypairs, and Home Assistant's dedicated keypair. Each file records its
restore destination, owner, mode, format, consumers, current backup/key dependency,
rotation procedure and path-rebasing policy. Twelve external dependency groups
record live state and unresolved recovery prerequisites across smarthome.

The read-only checker inspects metadata, committed repository ignore coverage and
bounded discovery roots without reading secret/archive bytes. It rejects unsafe
paths, special/hard-linked files, excess permissions and unclassified files.
`--manifest-only` works without any ignored inputs; `--json` produces a sanitized
metadata report. Use Just's `--no-dotenv` flag to bypass its global environment
file loading before the checker starts. Passing means inventory checks passed, never deletion safety.
The current local metadata check passes. Two local host-pin files and the
historical Z-Wave NVM backup were tightened from 0644 to 0600, without content
changes. No keys were generated/rotated, no master was stored, and no live
service or account was changed.

Latest validation passed: full `just usenet-test` with 292 cases (285 passed,
seven existing opt-in skips), compilation, ShellCheck, JSON/YAML, all three
Ansible syntax checks and the source/history secret scan. The actual metadata
check and root/infrastructure recipes also passed. Independent coverage and
implementation review informed the manifest and safety tests. The public SOPS
configuration, recipient, and encrypted vault are committed.

Independent coverage review identified additional prerequisites: authoritative
Home Assistant `/config/secrets.yaml`, Core `.storage` state and ESPHome files
need supported consistent encrypted capture; the documented native add-on export
is unencrypted and excludes Core, and its retained archive location is unverified.
`new-hass-configs/secrets.yaml` is tracked and contains a nonempty value not
certified as a placeholder. Privately establish its sensitivity and authority;
do not emit its value or use it to overwrite live HA secrets. Historical plaintext
HA backup trees also need exact-file classification, and the August 21 NVM
snapshot predates intentional node removals. See the new recovery runbook for
the full findings and source references.

The current increment completed the password-manager-first SOPS boundary.
`SOPS_AGE_KEY` is the only accepted private identity input; it is briefly held
in a private temporary file only for reviewed native `age-keygen` to derive the
public recipient, then removed. `just --no-dotenv usenet-recovery-master-init
second-copy-planned` wrote the committed public recipient and narrow
`.sops.yaml`; no private identity is stored in the checkout or output. The
encrypted, committed `usenet-infra/vault/secrets.sops.json` contains only
inventory `vault` entries. `setup-secrets` validates/decrypts the entire bundle
before publication, restores through the inventory allowlist, rebases only
checkout-path boundaries, refuses unsafe files/symlinks, and preflights conflicts.

The September 11 clean-clone drill restored all 24 present vault entries into
`/Users/rtimmons/scratch/2026-09-11/smarthome`; byte-equivalence was verified
under the recorded rebase policy and every restored mode matched the inventory.
The three optional local application files were absent as expected. The clone
has no external Git object alternates and points to the GitHub origin. This is
evidence for the small-vault path only. It did not retrieve the master from its
independent second copy, restore Terraform state, or authenticate/decrypt the
14 required non-vault state/archive entries; twelve external dependencies also
remain. **Deleting this checkout remains unsafe.**

### State/archive and NAS increment — September 11, 2026

Implemented `recovery-capture`, `recovery-store`, `recovery-verify`,
`recovery-restore`, and `recovery-drill` in both Justfiles. Capture holds both
current Terraform files under Terraform-compatible POSIX locks, detects source
changes/replacements, preserves lineage/serial and resource IDs byte-for-byte,
and excludes plans. Verification authenticates the entire outer age package,
binds it to the exact inventory/vault/recipient and the Git-carried snapshot
receipt (not just NAS-supplied metadata), verifies all six SSH keypairs,
then validates every entry before any state/archive installation. Restore
preflights all existing destinations, refuses divergent files and safely resumes
with identical files. Failures use private temporary directories, scrub child
environments and avoid plaintext diagnostics. New recovery commands use the
repository-pinned Python wrapper without exposing the master to bootstrap children.

The first snapshot receipt is tracked at
`usenet-infra/recovery/snapshots/20260911T191749Z-5150bea3423e3707.json`.
Ciphertext SHA-256:
`8f6d2835f08fb7466db0a0dfebe5f143dc5b0bb1f76817833840a791a6e83eaa`.
Local capture: `build/recovery-20260911`; independently downloaded NAS copy:
`build/recovery-nas-retrieved-20260911`. Receipt source checkpoint is
`0b910b316c5627e50e0003c8f78e3b6b7de2b55d` (the pre-increment Git revision).
The actual user-run verification reported 15 entries, six keypairs,
`new_files_restored: 0`, `master_decryption_verified: true`, and
`deletion_safe: false`. This was an authentication/content drill, not a state
installation into a fresh clone. Both original and retrieved ciphertext remain.

Vault hardening fixes two concrete recovery hazards: replacing ciphertext now
stages and authenticates the new bundle before atomic publication, and explicit
replacement of local files retains private prior versions beneath
`build/recovery-prior/`. Identical restores are idempotent and repair modes.
SOPS now rejects non-age provider metadata, uses an empty private HOME/XDG config,
and receives only the supplied key. A real native-SOPS regression demonstrated
that the previous ambient-key fallback could accept a wrong injected key; the
hardened implementation refuses it. Native age/SOPS fixture tests also exercise
wrong keys, truncation, tampering, unsafe paths, lock contention, interruptions,
existing-file conflicts and cleanup.

The inventory JSON remains the exact policy snapshot bound into the existing
SOPS vault and recovery package. Its external-dependency status text describes
the earlier inventory; the current facts above supersede those statuses. Any
future inventory modification requires deliberate vault re-encryption and a new
state/archive capture. No credentials or inventory policies were silently changed.
Legacy inner archive encryption still uses the escrowed SSH identities; future
native-recipient migration and retention remain pending. Keep both old keys.

Validation for this increment: the final full `just usenet-test` run executed
386 cases (379 passed, seven existing opt-in skips), followed by successful
compilation, ShellCheck, JSON/YAML validation, inventory schema and all three
Ansible syntax checks. The final whole-repository history scan intentionally
returned failure for the two historical RSA keys above. `just test` also passed
all repository tests and all seven add-on container checks before publication.
Current source/index scans, the actual local inventory check, and diff whitespace
checks pass. Real native age/SOPS negative tests run with fresh synthetic keys,
not skipped mocks. The retrieved real NAS package also passed the exact
Git-receipt binding check without changing ciphertext or requiring the user to
repeat decryption. A final clone-mode regression confirms public Git metadata
can use private mode 0600 without weakening exact secret-file permissions.
The Usenet recipe is not entirely green: its security audit failure is preserved.

1. **Inventory before migration.** Build an explicit, reviewed allowlist from
   ignored-file metadata and deployment references, never dump secret values.
   Each entry needs an owner/service, exact restore destination, sensitivity,
   mode, format, consumers, current backup/key dependency and rotation procedure.
   Cover `.ssh/id_ed25519_codex_smarthome`, Home Assistant secret/configuration
   inputs and other add-on credentials as well as the Usenet paths below. Do not
   recursively encrypt the whole checkout, caches, SSH sockets or Downloads.

   | Material | Current source / recovery requirement |
   | --- | --- |
   | Deployment inputs | `usenet-infra/.env`, `secrets/hetzner.env`, `ansible/inventory.yml`, `ansible/files/catalog.env`, `ansible/files/rclone.conf`; restore exact values but render checkout-relative paths for the new location |
   | Dedicated identities | `usenet-infra/secrets/ssh/{cloud-admin,cloud-ui,qnap-admin,qnap-reader,storage-writer}` plus matching public keys; Home Assistant's root `.ssh/` identity is separate |
   | Authentication | `secrets/dashboard-auth.json`, `secrets/unifi-cloud-vpn.psk`; provider/indexer and application secrets in live SAB/Prowlarr configuration and consistent database backups |
   | Trust and topology | Verified cloud/QNAP/Storage Box `ansible/files/secrets/` host pins, NAS paths and UID/GID, cloud/storage resource IDs; omit untrusted `.candidate` files and expiring sockets |
   | Terraform | Independent `usenet-infra/terraform/{cloud,storage}/terraform.tfstate` and live `.tfvars`; states include passwords, lineage and serial; preserve both roots and checked-in provider locks |
   | Stateful backups | Verified cloud, QNAP, VPN, UniFi Network/System and actual USG/config-override archives listed below; canonical media remains on Storage Box |
   | External identity | UniFi's 1Password-managed RSA key, human account passwords, MFA/recovery codes and Git access require an independent password-manager/account recovery path; never export them implicitly |

2. **Use SOPS with a dedicated native age recovery identity.** The random X25519
   age identity is independent of every SSH login key and is injected only as
   `SOPS_AGE_KEY` by the password manager. It needs a second independently
   retrievable copy outside this checkout and the systems being recovered. Commit
   only the public recipient and narrow `.sops.yaml` rules. A random age private
   identity is the recovery master, not an ordinary memorable password.
   Pin and verify SOPS/age binaries in the bootstrap recipe. Use the requested
   `SOPS_AGE_KEY` environment input for one process; never persist a master-key
   file in the checkout or recovered systems.
   Never store the master in repository `.env`, shell history, logs, CI artifacts,
   or a vault decryptable only by that same master. Clear it from child
   environments after the decryption step. A private prompt or password-manager
   injection should avoid typing an actual key into a command line.

3. **Track only the encrypted small vault.** Implemented at
   `usenet-infra/vault/secrets.sops.json`, outside the existing ignored `secrets/` directory, with
   fully encrypted SOPS values and exact-byte binary handling for key/config
   files. Keep all existing plaintext/state ignore rules. Extend the secret scan
   with a narrowly scoped ciphertext exception that validates the SOPS envelope;
   continue rejecting raw keys, tokens, plaintext `.env`/inventory/state and
   accidental decrypted files. Do not enable automatic decrypted Git diffs.
   Store a versioned restore manifest; path metadata should not contain secrets.

4. **Break the current archive-key dependency before rotating anything.**
   Existing cloud/VPN/UniFi/USG backups use the exact existing `cloud-admin`
   private key; QNAP backups use the exact existing `qnap-admin` private key.
   Escrow BOTH old identities under the new master, then prove the restored
   identities authenticate and decrypt their respective retained archives.
   Changing an SSH key must never destroy the only way to read an old backup.
   Future backup helpers should accept the dedicated age public recipient
   directly; deploy no private master to the VM, QNAP or controller. Keep old
   decryption keys until all retained archives have a tested alternative path.

5. **Make ciphertext independently retrievable.** Local ignored `backups/` is
   insufficient. The user selected a versioned QNAP directory on September 11, overriding
   the originally proposed off-NAS destination. It is outside this checkout,
   the cloud VM and canonical Storage Box, but shares the NAS disk failure
   domain. Do not purchase a new service without approval. Store retrieval credentials in the master-encrypted vault
   and record archive location, revision, timestamp, recipient fingerprint,
   ciphertext SHA-256 and expected content in a recovery manifest. Bootstrap
   must not need credentials that exist only inside the archive it is fetching.
   Capture consistent encrypted snapshots of BOTH Terraform states, preserving
   lineage/serial and resource IDs, with no concurrent apply. Retain application
   databases as verified backups rather than treating a static secrets vault as
   an application backup. Exclude saved `.tfplan` files; regenerate fresh plans.
   Publish the reviewed Git branch and verify its remote revision so re-cloning
   actually retrieves the recovery implementation. Git/account access remains
   an external prerequisite if the repository is private.

6. **Implement safe, idempotent recipes.** `just secrets-check`,
   `just setup-secrets`, and `just secrets-encrypt` are implemented for the
   small vault. `just recovery-capture`, `just recovery-verify`, `just recovery-restore`,
   `just recovery-store`, and `just recovery-drill` are now implemented for
   state/archive material (see current increment above). Authenticate all ciphertext
   before installation, validate schema/path allowlists, reject symlinks and
   traversal, use private temporary directories, atomic writes, 0700 directories
   and 0600 secret files. Refuse divergent existing files unless an explicit
   restore/overwrite option was requested; preserve a recoverable prior version.
   Never `source`/`eval` decrypted content; parse environment data and pass only
   required values to each consumer. Prefer temporary file/descriptor delivery
   for commands that need no persistent secret. Suppress subprocess output that
   could contain secrets, and clean up on errors/signals. Rebuild local absolute
   paths safely instead of restoring this workstation's checkout prefix.

7. **Run the deletion-safety acceptance drill.** The vault-only portion passed
   in a new clone at a different path: 24 present entries restored with policy
   equivalent bytes and inventoried modes. The full drill remains incomplete.
   Use a new clone at a different
   path with no access to original ignored files, ambient SSH agent, application
   sessions or live services. Supply only the master and independently available
   ciphertext (with documented Git/backup retrieval access). Restore all
   allowlisted files, verify identity/public-key matches and permissions,
   authenticate/decrypt every required archive, check SQLite integrity, and
   start pinned application images with no network or published ports. Inspect
   Terraform state offline; do not apply or destroy anything. Exercise missing
   and wrong keys, tampering/truncation, missing archive, unsafe path, interrupted
   restore, existing-file conflicts and cleanup. Use fixtures for failure cases;
   never corrupt actual recovery material. Record sanitized hashes/counts and
   the exact Git revision. The operator has confirmed the same master is held on paper outside
   1Password; count the independent-copy requirement as satisfied. Only then mark deleting the original checkout safe.

8. **Add rotation and ongoing maintenance.** Add a new recipient, verify recovery,
   update encrypted data-key recipients, then rotate SOPS data keys as appropriate.
   Removing a recipient cannot revoke old Git revisions or archives already
   obtained; a compromise also requires rotating the underlying service tokens,
   passwords and SSH keys and updating their consumers. Keep MFA and human login
   recovery in the password manager: password hashes preserve logins but cannot
   recover the original password. Schedule capture/verification/retention only
   after this workflow passes; record freshness and failed-backup alerts.

Official references checked for this design:
[SOPS age identities](https://getsops.io/docs/usage/identities/age/),
[SOPS formats](https://getsops.io/docs/reference/),
[process integration](https://getsops.io/docs/usage/advanced/),
[key management](https://getsops.io/docs/usage/key-management/),
[age usage](https://github.com/FiloSottile/age#usage).

## Implementation progress

Last updated: 2026-09-11

- [x] Dedicated `usenet` branch and implementation plan created.
- [x] Cold-state repository review completed; implementation lives in `usenet-infra/`.
- [x] Fresh official-source research completed for Hetzner, Usenet providers/indexers,
      application versions, and QNAP/Container Station behavior.
- [x] Material architecture decisions confirmed; Hetzner account setup is ready to provision.
- [x] Reproducible Terraform, Ansible, Compose, catalog tooling, tests, and operational
      documentation scaffolded and locally validated where installed tooling permits.
- [x] Hetzner token stored and validated without exposing it; dedicated SSH keys and
      ignored mode-0600 Terraform inputs generated.
- [x] Live Terraform plans validated: cloud is 5 additions and storage is 2 additions,
      with no changes or destroys and no existing project servers.
- [x] Provision protected CX43 cloud infrastructure, BX11 Storage Box, and
      server-enforced read-only QNAP subaccount; post-apply plans show no drift.
- [x] Bootstrap and harden the cloud VM; deploy healthy loopback-only SABnzbd and
      Prowlarr containers; connect and verify Storage Box writer access.
- [x] Install the QNAP reader public key and prove with a disposable sentinel that
      the server-enforced read-only subaccount can read but cannot overwrite/delete.
- [x] Provision Usenet provider/indexer accounts and complete their application setup.
- [x] Eweka credentials saved privately; primary configuration and authenticated
      SABnzbd server test independently verified.
- [x] SABnzbd scratch paths, 30 GiB reserves, repair/unpack defaults, and disabled
      automatic scripts/watched folders applied and read back successfully.
- [x] Official SABnzbd 100 MB NNTP diagnostic downloaded through Eweka, verified,
      unpacked, and promoted to the canonical Storage Box with provenance.
- [x] Implement manual encrypted service-configuration backup; capture the live
      cloud settings and verify their off-VM archive and database integrity.
- [x] NZBGeek account created and $12 USD one-year purchase confirmed by the
      user; active membership and September 13, 2027 expiry verified in the account.
- [x] NZBGeek API key saved privately; enabled Prowlarr entry and live API test
      independently verified with strict certificate validation.
- [x] Prowlarr's internal SABnzbd connection configured, saved-credential test
      passed, and repeat configuration verified to make no changes.
- [x] Reconnoiter and bootstrap the QNAP without disturbing existing services.
- [x] Implement and locally verify the authenticated OliveTin dashboard,
      shared catalog backend, and reproducible QNAP deployment integration.
- [x] Add and validate the authenticated catalog dashboard on the QNAP's private LAN address.
- [x] Run the authorized end-to-end test and document the implemented system.
- [ ] Complete the external dashboard reachability test; explicit approval pending.
- [x] Make cloud search/download UIs available by default on the LAN; UniFi VPN,
      automatic recovery, and user logins to both SABnzbd and Prowlarr verified.

LAN access architecture review (2026-09-10): the repository's August 31 network
inventory identifies a USG 3P gateway and a separate Cloud Key Gen2 Plus, with an
existing IPsec site-to-site connection. Prefer evaluating a narrowly scoped
UniFi-to-cloud IPsec connection for permanent LAN routing. Native UniFi WireGuard
client requires a next-generation gateway, and Site Magic excludes legacy USG
models; do not assume these features from the UniFi brand alone. Home Assistant
can provide navigation and SABnzbd status after connectivity exists. QNAP remains
the storage/cache host; an application-only NAS tunnel is a fallback if the
supported USG configuration is impractical.

The user authorized proceeding, and private SSH authorization is now restored.
Live checks confirm UniFi OS 5.1.31, Network 10.6.101, USG 3P firmware
4.4.57.5578372, Default LAN 192.168.1.0/24, printer 192.168.6.0/24, existing
remote site 192.168.8.0/24, and no static routes. The saved UniFi VPN
`usenet-cloud-ui` is restricted to Default through the verified override below. The controller rejects a /32 remote
subnet, so it uses 10.77.0.0/30; only 10.77.0.1 is assigned on the cloud VM,
with authenticated private ports 18080 (SABnzbd) and 19696 (Prowlarr).

The supported UI offers IKEv2/AES-256 but only SHA1 or MD5. The deliberate
compatibility configuration uses SHA-1 exclusively as HMAC in IKE/ESP,
AES-256, DH14, PFS, a random 256-bit PSK, and no weak-algorithm fallback.
strongSwan documents this option for systems without SHA-256. This legacy
constraint and the future migration path are documented in
`usenet-infra/docs/lan-ui.md`. Existing application loopback bindings, normal
Internet routes, the other site VPN, and QNAP services remain unchanged.

Pre-change backups are encrypted and authenticated-decryption/checksum verified:
- Cloud: `usenet-infra/backups/cloud-20260911T001750Z-UCxzKhOY.tar.age`,
  589 files, two SQLite databases, ciphertext SHA-256
  `c7871385ec9de9d82530accd87b0384016298855b6bb5e64f143529bc0a8309d`.
- UniFi Network: `usenet-infra/backups/unifi-network-20260911T004042Z.unf.age`;
  original 71,344 bytes, plaintext SHA-256
  `565f79f3b56eb17dc36249a9e82e4ff91257d18a0bee02627eceaa72bcca1062`.
- Fresh all-applications System Config export:
  `usenet-infra/backups/unifi-system-20260911T004201Z.unifi.age`;
  original 210,752 bytes, plaintext SHA-256
  `56b993411768f6727a474a2494c604d6698d9270d41dc7de5479c8fc31b056e3`.
The exact System export in Downloads is retained with mode 0600. Evidence is
under ignored `build/unifi-*-backup-*.json`; no 1Password private key was exported.

The cloud firewall update is applied: only UDP500/4500 from the verified home
WAN was added; existing rules were preserved, no resources created/destroyed.
The new cloud_vpn/cloud_ui_proxy roles use root-owned /etc configuration,
ordered persistent services, IPsec-policy checks, and exact local health-probe
exceptions. The separate encrypted VPN backup covers four canonical root-owned
configuration files. Full validation passed: 224 tests (217 passed, seven
opt-in runtime cases skipped in the normal suite), compilation, ShellCheck,
YAML/JSON, all three Ansible entry-point syntax checks, and secret scan. The
seven actual proxy runtime cases also passed separately. Independent isolated
Ubuntu/firewall tests verified first/repeat install, IPsec match syntax,
protected local HTTP health, denied plaintext traffic, and UFW reload behavior.
Cloud service deployment passed (42 tasks, 20 changed, zero failures); repeat
convergence passed (39 tasks, zero changed, zero failures). All four VPN/proxy
services are active. Verified listeners are only 10.77.0.1:18080/19696 and
existing 127.0.0.1:8080/9696; both private endpoints return HTTP401 without
credentials. Storage/Prowlarr/scratch health pass; SAB reports seven warnings
identified as historical setup/Direct Unpack notices predating this change. The new four-file root configuration
backup was encrypted and verified:
`usenet-infra/backups/cloud-vpn-20260911T005548.069572Z.tar.age`,
4,435 source bytes, ciphertext SHA-256
`e72cb53f590cc9b8ae11455930531680bf358371506b6df28b181d7965eac27a`.
Public IPv4 checks for 8080, 9696, 18080 and 19696 all timed out as expected;
a fresh Terraform plan reports no changes. The original external NAS:1337
reachability test remains separate and was not attempted.
The user completed the private UniFi PSK entry/save on September 11. Live checks
then found two issues that service-active checks had missed: Ubuntu AppArmor
blocked swanctl's custom configuration path, and the USG received legacy IKEv1
and both LAN selectors despite the UI's IKEv2/main-LAN settings. The cloud fix
grants swanctl read access to exactly its root-only configuration and verifies
that the connection, child, and credential actually load. The deployed loader
uses the installed strongSwan 6.0.4 command syntax. All 231 tests run successfully
(224 passed, seven opt-in skips), with the supplementary checks passing.

A narrow controller override is deployed and verified at
`usenet-infra/unifi/config.gateway.json`. It creates dedicated IKEv2/AES-256
groups for only the new peer and disables its autogenerated printer tunnel.
Before applying it, the live gateway configuration and exact UniFi VPN record
were encrypted and verified in
`usenet-infra/backups/usg-unifi-vpn-pre-fix-20260911T171125.028168Z.tar.age`
(ciphertext SHA-256 `75666d0490f26fe83edb4f23d7d6976bb4f2955d015c9bf09cd8eaaaf88dba6c`).
The actual gateway configuration now contains only the intended active new
tunnel (192.168.1.0/24 to 10.77.0.0/30), with IKEv2, AES-256/HMAC-SHA1, DH14,
and PFS14. The existing site VPN configuration is unchanged. Only the UniFi
Network service was restarted; neither the gateway nor NAS was rebooted.
Live cloud negotiation and increasing traffic counters passed. An explicit
CHILD-SA rekey verified PFS14. Restarting only the cloud strongSwan service
automatically restored the tunnel and private proxy, followed by successful
LAN HTTP401 checks on both ports. Direct backend ports 8080/9696 time out.
The workstation default route remains the UniFi gateway. Final cloud convergence
passed with 42 tasks, zero changes, zero failures. The user confirmed both
SABnzbd and Prowlarr open successfully. Prowlarr requires the catalog credentials
in the browser popup, then its existing credentials on the Forms login page;
using these two logins resolved the reported rejection. No credentials reset.

The verified post-change encrypted backup is
`usenet-infra/backups/usg-unifi-vpn-post-fix-20260911T173623.167151Z.tar.age`
(ciphertext SHA-256 `b958a55ff27eebeaca973d96577011bb57c753df932271bab1dfa8f0e879752a`).
It contains the actual gateway configuration (66,027 bytes), exact saved VPN
record (1,204 bytes), and installed override (991 bytes), and passed authenticated
decryption/checksum verification. Future LAN/VLAN or WAN changes require scope
and peer-policy revalidation as documented in `usenet-infra/docs/lan-ui.md`.

References: [UniFi IPsec](https://help.ui.com/hc/en-us/articles/360002426234-UniFi-Gateway-Site-to-Site-IPsec-VPN),
[WireGuard requirements](https://help.ui.com/hc/en-us/articles/16357883221015-UniFi-Gateway-WireGuard-VPN-Client),
[Site Magic compatibility](https://help.ui.com/hc/en-us/articles/16750417515159-UniFi-Gateway-Setting-Up-SD-WAN-with-UniFi-Site-Manager-and-Fabrics),
[Home Assistant SABnzbd integration](https://www.home-assistant.io/integrations/sabnzbd/).

Resume work on 2026-09-10 implemented the OliveTin dashboard, shared catalog
operation/state safety, and QNAP deployment integration in parallel. The full
local validation recipe now passes 153 unit tests, compilation, ShellCheck,
JSON/YAML parsing, pinned Ansible syntax, and source/history secret checks.
An additional 51 isolated Linux checks verified the rendered QNAP transfer
templates' exact bytes, atomicity, idempotence, permission repair, failure
handling, and private-address/path gates. Fresh read-only Terraform plans again
report no changes for both protected states. Cloud health again passes Storage
Box, SABnzbd, and scratch checks, with only the expected missing-indexer error.
The private cloud UI tunnel was smoke-tested and closed afterward.

An isolated arm64 container/browser test verified authentication, category search,
generated item actions, SHA-256-verified download, explicit local-removal
confirmation, canonical fixture preservation, and a throttled 16.5 MiB pull that
continued after closing the browser. Container restart preserved the login
session and execution history. The dashboard runs as a non-root numeric identity
with a read-only root filesystem and no Docker socket. Its temporary test
container is removed after validation.

Eweka account existence and successful private credential entry were confirmed
by the user on 2026-09-10. Its actual charged tier and renewal details have not
been independently verified. Saved SABnzbd settings were independently checked:
`news.eweka.nl`, TLS port 563, Strict certificate verification, 20 connections,
enabled, priority 0, Required on, Optional off, and retention 0. The authenticated
SABnzbd server test passed using the saved password without returning credentials.
A separate VM connection verified TLS 1.3 and an NNTP 200 greeting. Primary
Required pauses acquisition on primary connection failure to protect fill quota.
The helper preserves existing credentials and quota and verifies saved settings.
No password has been requested in chat. NAS access remains unconfigured. The new QNAP code
has not been deployed to the NAS, and these isolated checks do not substitute
for the required provider-to-NAS acceptance test. See
`usenet-infra/docs/validation.md` for detailed evidence and remaining gates.

SABnzbd now uses `/data/incomplete` and `/data/complete` on the intended VM
scratch mounts, with `30G` free-space floors for both. Default processing is
repair/unpack with archive cleanup; direct unpack, watched folders, and automatic
scripts are disabled. The fresh wizard had not created any categories, so the
helper initialized only `*` while the queue and post-processing were empty.
All settings were read back with no remaining differences. Reconcile these
non-secret defaults with `just usenet-sab-settings inspect` / `apply`.

The official `https://sabnzbd.org/tests/test_download_100MB.nzb` diagnostic was
submitted once with normal priority and a durable private receipt. SABnzbd
reports completed, 107,455,358 downloaded bytes, successful verification and
unpack stages, no failure, and the requested processing policy. Its one-second
download counter is coarse evidence, not a formal throughput benchmark.
The two resulting files were promoted and remotely byte-checked with zero
differences under catalog ID `sabnzbd-official-100mb-2026-09-10`; its manifest
records SHA-256 values and official-test provenance. Inspect the existing job
with `just usenet-sab-smoke-test status`; `start` never re-enqueues an existing
receipt. The actual NAS/dashboard and indexer acceptance remain pending;
secondary-provider acceptance is deferred by the user's decision below.

Manual configuration backup is now implemented and verified. The backup-only
Ansible play installs pinned, checksum-verified age 1.3.2, the snapshot helper,
and only the administrator's public encryption recipient, without restarting
applications. `just usenet-backup-cloud` encrypted on the idle VM, transferred
only ciphertext to the ignored workstation `usenet-infra/backups/` directory,
and decrypted/verified 589 files and two SQLite databases in private temporary
storage. The archive includes service credentials, Storage Box writer identity,
catalog state, and remote manifests; bulk objects/downloads are excluded.
Temporary plaintext was removed and the remote encrypted copy was removed only
after verified local publication. The archive is
`cloud-20260910T214707Z-NCk4sDjo.tar.age`, SHA-256
`564a105201c8910b3448c791f061bc03e25fb611ac8a0fee5d8c4203c137d42b`.
The backup deployment rerun had `changed=0`. Repeat the manual backup after
remaining account configuration. Scheduling, QNAP backup, independent recovery
of the decryption key, and a restored application startup drill remain pending.

Material decisions made:

- Use the now-supported first-party Terraform resources for the Storage Box and
  read-only subaccount, isolated in a protected state from the replaceable VM.
- Start with BX11 (1 TB) at $4/month, warn at 80%, and upgrade in place before
  90% utilization through BX21 (5 TB), BX31 (10 TB), or BX41 (20 TB).
- Start with the x86 CX43 (8 shared vCPU, 16 GB RAM, 160 GB NVMe); benchmark before
  paying for a much more expensive compute tier.
- Pin SABnzbd 5.1.3, Prowlarr 2.5.2.5491, and rclone 1.75.1.
- Pin OliveTin 3000.19.0; its image supports amd64/arm64, with actual NAS
  compatibility still subject to preflight and image smoke tests.
- Use Eweka alone initially. On 2026-09-10 the user deferred UsenetExpress
  until/unless actual completion gaps establish a need for a fill provider.
- Use NZBGeek plus NZBFinder because DrunkenSlug registration is closed.
- Require deliberate manifest-backed promotion and server-enforced read-only QNAP
  credentials; no unattended acquisition path is enabled.
- Make a declaratively configured OliveTin dashboard the primary cache-management
  interface. Keep the existing catalog commands as its tested backend and as the
  recovery/automation interface; do not replace the safety semantics with raw file copies.
- Treat QNAP HybridMount as an optional compatibility experiment, not a dependency.
  Never weaken the server-enforced read-only credential to make HybridMount work.

Current checkpoint: the approved $23.09/month Hetzner infrastructure is live and
the cloud bootstrap is complete. One protected CX43 VM, protected Primary IPv4
and IPv6, one firewall, one SSH-key record, one protected BX11 Storage Box, and
one protected server-enforced read-only QNAP subaccount exist. Post-apply
Terraform plans report no changes. Live authenticated pricing for this account
is $18.49/month for CX43, $0.60/month for IPv4, and $4.00/month for BX11 in
Helsinki, with a $0 setup fee and 0% VAT reported.

The VM accepts only the dedicated non-root administrator key, denies direct root
and password login, and allows inbound SSH only from the currently approved
source CIDR. SABnzbd and Prowlarr are container-healthy on VM loopback only.
Ansible automatically reads their locally generated API keys into the protected
health environment without printing or returning them. Earlier checks verified
Storage Box access, catalog failure state, SABnzbd, and VM scratch. NZBGeek is
now enabled; a fresh complete health report is being verified after updating
credential-safe error handling.

### Cold-agent resume checkpoint

Do not recreate, replace, or destroy the live Hetzner resources, and do not ask
the user to restate the already-stored Hetzner token or any generated key. Start
by reading this file and `usenet-infra/README.md`, then inspect the current Git
and ignored local state. `just usenet-terraform-plan` should remain no-change;
never apply a plan containing a destroy or replacement of the Storage Box.

Eweka setup is complete and independently verified; do not ask for signup or
credentials again. `just usenet-sab-provider inspect`, `configure`, and `test`
inspect, reconcile, or test its existing saved server through the dedicated SSH
identity. They return only approved non-secret fields. The recommended offer was
€104.85 prepaid for 15 months, but the actual charge/renewal remains unverified.
For subsequent private account entry, open `just usenet-cloud-ui` and use SABnzbd
at `http://127.0.0.1:8080` or Prowlarr at `http://127.0.0.1:9696`.

The user explicitly deferred UsenetExpress on 2026-09-10 until/unless needed.
Use Eweka alone; a secondary provider is not a current purchase, setup, cost,
or acceptance prerequisite. Revisit a fill block only after evidence of actual
article availability/completion gaps, with fresh provider/terms research and a
new purchase decision. Preserve Eweka's verified TLS/Required settings. Historical
UsenetExpress research remains in account-setup.md for reference only.

The provider and both indexer connections are complete. Continue with QNAP
bootstrap below. NZBGeek is paid and active: the user completed the official
$12 USD one-year Stripe checkout, and the account independently shows expiry
2027-09-13 22:01:53 UTC. Do not ask for signup or payment again. Daily API/grab
quotas and automatic rebilling remain unverified; the advertised 100 API results
per request is pagination, not a daily quota.

NZBGeek is now configured and enabled in Prowlarr. The user privately created
Prowlarr's Forms login and saved the indexer key. The agent enabled the existing
entry only after a successful credentialed API test, then verified saved state
and retested. HTTPS, global strict certificate validation, priority 25, and
unchanged/unset provider quotas are verified. No additional NZBGeek signup,
payment, login-creation, or key-entry prompt is needed.
`just usenet-prowlarr-indexer inspect`, `test`, and `enable` return only approved
settings and connection outcomes; `prepare-disabled` preserves an existing entry.
The internal SAB download-client connection is configured and independently
verified. It uses `sabnzbd:8080` on the private Docker network and category
`prowlarr` with repair/unpack, no script, and inherited normal priority. Only the
literal `sabnzbd` was added to SAB's existing hostname allowlist, preserving its
other entries. Candidate and persisted-credential tests passed; repeating
configuration returned no changes. Use
`just usenet-prowlarr-download-client inspect`, `test`, or `configure`.

The latest encrypted backup is `cloud-20260910T225152Z-SIfVfDwC.tar.age`,
SHA-256 `07df7ddf0ec8153b5ba5c99f458bce609c6439a2ff1bfd6b34a04c5b43d07088`;
589 files and two SQLite databases verified. It includes the saved Prowlarr
login, both indexer keys, rotated Prowlarr API key, SAB client, and hostname
configuration, including the restored `direct_unpack=false` setting. Prior
archives remain intact. Health reporting omits raw application/exception text and
uses credential-safe request handling; the tested helper was deployed without
restarting services. The tested catalog module was also installed atomically to
satisfy the health helper imports; schema 1 is unchanged and no migration runs.
All 159 tests and the complete Usenet validation recipe pass.

The user confirmed NZBFinder signup and purchase of Pro on 2026-09-10.
The authenticated home page independently showed Pro membership, advertised
`$30/year` (`$2.50/month` equivalent), 20,000 API requests, unlimited downloads,
and rolling 24-hour request counters. Dollar currency code, actual receipt,
expiry, and automatic renewal remain unverified. Do not ask for signup or
purchase again. NZBFinder's saved key, enabled entry ID 2, HTTPS, strict
certificates, priority 25, and unset quotas are verified; its live API test
passed. `just usenet-prowlarr-indexer enable nzbfinder` returned unchanged
because the user had already enabled it. Both indexers were retested successfully
after the internal Prowlarr API-key rotation. Do not read form values or emit full browser
accessibility trees: Prowlarr RSS links embed its application API credential.

Completed security follow-up: the browser tool's automatic Prowlarr page output
included an RSS link containing the Prowlarr API credential. Do not repeat the
link or credential. The supported ResetApiKey command rotated that application
key; the old key now returns HTTP 401 and the new one HTTP 200. Its protected
health environment reference was synchronized with mode 0640 and ownership
preserved. Other XML settings were unchanged. Indexer/client tests and refreshed
encrypted backup passed. No application restart was needed. Older backups must
have their restored Prowlarr key rotated before use; prefer the latest archive.

QNAP deployment and dashboard/CLI acceptance are complete. The user supplied the web address
`https://rynapqnap.local/cgi-bin/`, then signed in privately in Firefox after the
in-app browser rejected the NAS certificate. Use native Firefox controls via
CUA; do not retry the in-app browser or change certificate trust. Observed:
TS-451D2, QTS 5.2.10.3577, Intel Celeron J4025 (2 cores/2 threads), 4 GB RAM,
Container Station 3.1.2.1742 and HybridMount 1.17.5691 are installed. Dedicated
SSH access is enabled on port 22; Telnet remains disabled.

The user approved and created `usenet-deploy`, description "Dedicated Usenet
catalog deployment", with administrators/everyone membership; its enabled row
was independently verified. QTS requires administrator membership for SSH.
The password was entered privately and must not be inspected. Dedicated login,
repository public-key installation, SSH enablement, host-key pinning, and NAS
reconnaissance are complete; do not repeat those human setup requests.
The user confirmed "NAS login ready" after applying SSH settings and signing in
as `usenet-deploy`; that dedicated QTS login is independently verified. SSH now
answers on port 22. Its SSH Keys page initially had zero keys. The Add form
was completed by the user as `usenet-qnap-admin`. Its saved MD5 fingerprint
`2d:be:d6:24:51:cb:0a:a6:e3:a0:c2:a3:1c:0e:e0:00` matches the repository public
key. Keep the existing ED25519 key: official
QTS 5.2.1 release notes added ED25519/ECDSA support; the form's RSA placeholder
does not restrict modern QTS to RSA user keys.

The workstation has no prior trusted `rynapqnap.local` known-host entry. The
candidate public RSA host key (3072 bits) is in ignored
`usenet-infra/ansible/files/secrets/qnap-known-hosts.candidate`; its fingerprint
is `SHA256:jXVysXlhzn80Tk2BYg8CGNkfMCqjCEpyu0PyyHJX5RA`. The user explicitly
authorized first-use trust for this exact key; this is user-approved TOFU, not
independent console verification. The key is pinned in ignored mode-0600
`qnap-known-hosts`; future changed keys must fail strict checking.
The first dedicated public-key SSH login succeeded with no agent/password
fallback: `usenet-deploy@rynapqnap.local`, UID 1004, primary GID 100, supplementary
groups 0 (administrators) and 100. Kernel is Linux 5.10.60-qnap, x86_64. Protected
workstation `.env` now has the exact target/key/known-hosts paths. A parallel
agent completed read-only Docker, resource, and share reconnaissance. Container
Station is 3.1.2.1742, Docker 27.1.2-qnap8, Compose 2.29.1-qnap2, overlay2, and
memory/swap limits are supported. About 2 GB RAM is available. The only existing
container is `iperf3-1`, using roughly 1 MiB RAM. Docker is absent from the SSH
PATH; the preflight and recovery wrapper now discover its absolute executable
through Container Station metadata, without changing the NAS PATH or symlinks.
`just usenet-qnap-recon` repeats privacy-filtered read-only metadata checks.

The dashboard login was created privately by the user; its ignored Argon2id
authentication file and mode 0600 were verified without displaying credentials.
The agent created the empty `Usenet` shared folder through QTS on `GPvQNAP`,
with only `usenet-deploy` Read/Write, other listed users No Access, and guest
access denied. `/share/Usenet` resolves to `/share/CACHEDEV2_DATA/Usenet`; that
volume has about 1.37 TB free and is 69% used. The application directory
`/share/Container/usenet` is precreated with owner 1004:100 and mode 0750 on the
Scratch volume (about 42 GB free). No existing share or container was altered.
Protected inventory now selects `/share/Usenet/usenet-cache`, a 100 GiB free-space
floor, and the available LAN address `192.168.1.66:1337`. The read-only Storage
Box credentials come from the existing protected Terraform outputs/key files.
The first deployment transferred configuration but could not build images because
Docker tried to write client state in QNAP's protected package home. The fix scopes
Docker/Buildx state to `/share/Container/usenet/state/docker-client` (1004:100,
0700), with no global NAS permission changes. The retry built both pinned images
and passed actual x86_64 NAS image smoke tests; final service health is verified.
The first authenticated refresh exposed an unsupported single-upstream rclone
union. The deployment now uses the supported `catalog:` alias to the same
server-enforced read-only subaccount; an alias is not itself a permission control.
The fallback launcher also inherited QNAP ACL metadata through Docker COPY despite
mode 0555. Its build now writes a fresh inode, and prestart checks exercise the
real launcher plus a remote catalog listing. The combined deployment retry passed.
The user signed into the dashboard successfully. Runtime checks verified UID/GID
1004:100, no administrator supplementary groups, read-only container roots, dropped
capabilities, no Docker socket, only LAN port 192.168.1.66:1337, no global IPv6,
and unchanged preexisting iperf3 uptime. Actual kernel page size is 4096 bytes.
The full validation recipe now passes 183 tests, including Mac system Bash 3.2
compatibility for the fallback wrapper. Full dashboard/CLI acceptance with the
already-promoted official test object passed; external reachability is unverified.
The ignored dedicated `qnap-admin` keypair is installed and verified. Exact host,
versions, shares, and numeric identity are recorded in the protected inventory.
Do not use the Storage Box `qnap-reader` key as the NAS login key.
Do not reboot the QNAP. The QNAP implementation must include the OliveTin dashboard
described in sections 18-19; do not stop after making the fallback commands work.

Last verified on 2026-09-10:

- The corrected QNAP deployment completed with 44 tasks successful, 3 changed,
  zero failed. Dashboard and rclone are healthy; no existing services changed.
- Live dashboard acceptance: category search found the official test item;
  Download ran from 23:33:28 to 23:34:13 UTC, survived closing/reopening the browser,
  and retained progress, SHA-256 verification, atomic publication, and Completed
  output. Local state became 1 item / 95.4 MiB. Removal required the explicit
  remote-preservation checkbox; it completed at 23:37:07 UTC, returning to
  remote-only with zero local objects or transfer failures.
- NAS direct reader access read a disposable writer-created sentinel; overwrite
  and delete both failed with server SFTP SSH_FX_FAILURE, contents remained
  unchanged, and the writer independently verified SHA-256 before exact cleanup.
- The latest cloud backup passed isolated startup of both pinned applications,
  saved-key API authentication, enabled indexers/client, Forms login, empty queue,
  retained history, database integrity, and preserved credential/configuration
  values. The drill had no network or published ports; temporary plaintext,
  containers, and volumes were removed.
- CLI parity passed with the dashboard stopped: list/status/pull/evict operated
  through the shared backend. Both files (100,000,019 bytes) were independently
  hashed locally and remotely before/after, and the canonical manifest SHA stayed
  unchanged. Both services are healthy again, the login and completed output
  survived restart, and the unrelated iperf3 container is unchanged.
- Anonymous dashboard, entities, history, and action-detail API calls returned
  HTTP 403. Both services use about 108 MiB combined RAM at idle. An external
  reachability test still awaits explicit user approval after automatic approval
  review rejected the public-IP probe; private binding is not proof against NAT.
- Live QNAP encrypted backup captured and verified 32 files including dashboard
  authentication, sessions, execution output/history, and reader credentials;
  media and Docker build/client state are excluded. Archive:
  `qnap-20260910T234609Z-gr0zzbi0.tar.age`, SHA-256
  `6858b4a9127ce0860acb226fa3f7592ab1bcadfd50cd6bf607b59f284df78a20`.
  Its isolated application-startup restore drill passed: all three persisted
  results loaded, guest history was denied, and authentication/session bytes and
  six history/output files were unchanged. Test containers, volumes, and private
  plaintext were removed. This used an isolated arm64 runtime, not NAS replacement.

- `just test` in `usenet-infra/` passes 183 unit tests, Python compilation,
  ShellCheck, JSON/YAML parsing, pinned Ansible syntax checking, and secret scan.
- The cloud Ansible play converges with `changed=0` and proves a fresh non-root
  SSH login before retaining SSH hardening; managed UFW rules are reconciled.
- The live read-only sentinel test allowed list/read, rejected overwrite/delete,
  preserved the SHA-256 hash, and the writer removed the disposable fixture.
- Fresh cloud health exits successfully: Storage Box, catalog, Prowlarr, and
  scratch checks pass. Seven retained SABnzbd warnings were classified as six
  setup hostname refusals and one automatic Direct Unpack enablement notice;
  there are no provider/authentication/certificate failures. The disk autotest
  caused real `direct_unpack` drift; `just usenet-sab-settings apply` restored
  it to false while idle and verified all settings, without other changes.

## 1. Goal

Build this architecture:

```text
                         INTERNET

             Discovery metadata and curated lists
        (TMDb / TVDB / Trakt; optional request UI)
                           │
                           ▼
          Radarr / Sonarr; Jellyseerr or Overseerr
                           │
              deliberate interactive selection
                           │
                           ▼
                  Prowlarr + Usenet indexers
                           │
                           ▼
                     Usenet Provider
                           │
                       NNTP/TLS
                           │
                           ▼

                HETZNER CLOUD SERVER
               ┌─────────────────────┐
               │ SABnzbd             │
               │ Prowlarr            │
               │ local SSD scratch   │
               │ upload tooling      │
               └──────────┬──────────┘
                          │
                     rclone/SFTP
                          │
                          ▼

                HETZNER STORAGE BOX
                 ~20 TB canonical
                    content store
                          │
                     read-only
                    credentials
                          │
                          ▼

                       QNAP NAS
               ┌─────────────────────┐
               │ local selective     │
               │ content cache       │
               │                     │
               │ catalog dashboard   │
               │ browse/pull/evict   │
               │ verified CLI backend│
               └─────────────────────┘
```

Expected operating pattern:

- Approximately 20 TB maximum remote catalog.
- Approximately 1 TB/month transferred from Hetzner Storage Box to my NAS.
- The remote Storage Box is canonical.
- The QNAP contains only things I deliberately make local.
- Removing something from the QNAP must never delete it from the Storage Box.
- Acquisition and post-processing happen on the Hetzner VM, not the NAS.
- The QNAP should not need to be online for acquisition to continue.
- Normal cloud-to-NAS transfers should go directly Storage Box → QNAP rather than Storage Box → VM → QNAP.
- Day-to-day remote-versus-local decisions should be point-and-click; copying item
  IDs between terminal commands is a supported fallback, not the primary workflow.
- Discovery may provide a richer curated browsing experience.

This is a private system for content I am authorized to obtain and store.

## 2. Guiding principles

Optimize for:

1. Reproducibility.
2. Simplicity.
3. Declarative configuration.
4. Minimal externally exposed attack surface.
5. Easy disaster recovery.
6. Secrets never committed to Git.
7. Safe handling of the canonical remote copy.
8. Clear observability when something fails.
9. Avoiding unnecessary SaaS components.
10. Keeping recurring infrastructure cost near the previously estimated ~$75–90/month range unless there is a compelling reason otherwise.

Prefer:

- Terraform for Hetzner Cloud infrastructure.
- Ansible for Linux host provisioning.
- Docker Compose for application deployment.
- Docker Compose on QNAP wherever practical.
- rclone over SFTP for Storage Box transfers.
- A small, authenticated OliveTin web dashboard over building a bespoke catalog UI.
- Declarative, least-privilege UI actions that call the same verified catalog backend
  used by the command-line wrappers.
- Git as the source of truth for non-secret configuration.
- sops + age, or an equivalently simple encrypted-secret mechanism, if secrets need to exist alongside the repository.

Do not use mutable GUI configuration when a reasonable declarative alternative exists.

Document unavoidable one-time GUI/bootstrap steps.

## 3. Do fresh research before purchasing anything

Current date is September 2026.

Verify current information from official sources rather than relying on this prompt for pricing, versions, plan names, retention, or registration availability.

In particular verify:

- Hetzner Cloud server types/pricing.
- 20 TB Hetzner Storage Box pricing and features.
- Current Hetzner Terraform provider.
- Current SABnzbd stable release/container image.
- Current Prowlarr stable release/container image.
- Eweka pricing, retention and NNTP settings.
- Suitable secondary Usenet block-provider options.
- NZBGeek pricing and registration.
- DrunkenSlug registration status.
- At least one good alternative if DrunkenSlug registration is closed.
- Current QNAP Container Station / Docker Compose behavior relevant to my NAS.
- Current OliveTin stable release, container architecture support, authentication,
  access-control, validated arguments/entities, and long-running action behavior.
- Whether this exact QNAP and a Hetzner server-enforced read-only subaccount can use
  HybridMount File Cloud Gateway caching over WebDAV without write access. Hetzner
  warns that many WebDAV clients cannot mount its read-only mode; do not assume this works.

Prefer provider/operator documentation over blogs, Reddit, affiliate review sites, or forum folklore.

Briefly tell me if anything material has changed from the architecture described here before proceeding.

## 4. Account setup

Guide me through the accounts one at a time rather than throwing a giant checklist at me.

### Hetzner

Create or verify:

- Hetzner account.
- Hetzner Cloud project dedicated to this system.
- Cloud API token suitable for Terraform.
- 20 TB Storage Box.
- SSH/SFTP access for the Storage Box.
- SSH public keys.

Do not put the Hetzner API token in Git.

If the Storage Box cannot currently be provisioned with a supported first-party Terraform mechanism, treat ordering it as a documented manual bootstrap step rather than inventing brittle automation.

### Usenet provider

Default starting choice:

- Eweka as primary unlimited provider.

Before purchase, verify whether it is still a strong choice and show me:

- current effective monthly cost,
- commitment period,
- retention,
- connection count,
- TLS support,
- renewal pricing if different.

Configure NNTP using TLS.

Do not configure plaintext NNTP.

### Secondary Usenet provider

Deferred by the user on 2026-09-10 until/unless needed. Start with Eweka alone.
Do not buy or configure UsenetExpress or another secondary provider now.
If real article availability/completion gaps justify revisiting this decision,
research a useful alternative backbone and non-recurring block terms afresh.
UsenetExpress 500 GB was the historical candidate. Only after a new purchase
decision, configure any future block at lower priority for missing articles.

### Indexers

Start with two reputable Newznab-compatible indexers.

Prior candidates:

- NZBGeek
- DrunkenSlug

Check current signup availability.

If DrunkenSlug is closed, recommend another well-established indexer instead. Do not seek invite bypasses, buy shady invitations, or use scraped/stolen API credentials.

For each indexer record:

- account tier,
- annual cost,
- API limits,
- API endpoint,
- API-key location,
- renewal behavior.

Secrets must go into the chosen secret-management mechanism, not documentation or Git.

### Curated discovery (selected September 11, 2026)

Prowlarr is the indexer/search broker, not a recommendation or editorial-browse
application. Retain the indexers' own authenticated web UIs (for example,
NZBFinder's browse and Spotweb experiences) for direct browsing. Add this
private discovery layer using the user's selected Radarr and Sonarr:

- **Radarr** for curated movie discovery and **Sonarr** for curated TV discovery.
- **Jellyseerr** or **Overseerr** as an optional authenticated request/discovery
  front end. Select exactly one if a request-oriented UI is wanted; do not run
  both by default.
- TMDb, TVDB, and/or deliberately selected Trakt lists and calendars provide
  the curation metadata. These sources suggest titles; they are not acquisition
  authorities and do not replace the per-item authorization record.
- Prowlarr remains the single manager for NZBGeek and NZBFinder. It may sync
  those indexer definitions to Radarr/Sonarr after a deliberate compatibility
  check, while direct interactive Prowlarr search remains available.

The required flow is:

```text
curated list / calendar -> choose and monitor a title
-> automatic search / RSS match (or interactive selection) -> SABnzbd
-> inspect completed output
-> explicit manifest-backed catalog promotion
```

Configure the discovery tools with these non-negotiable safeguards:

- Give each service only the credentials it needs. Keep indexer and SAB API keys
  on the cloud host; never embed Prowlarr/SAB credentials in browser-side code
  or an external bookmarklet.
- Bind every new service to loopback or the approved private LAN/VPN path,
  authenticate it, and add it to encrypted configuration backups, health checks,
  version pinning, update testing, and recovery documentation.
- Do not expose a public request portal, invite arbitrary users, or infer that a
  metadata-list entry is authorized material.

Before implementing this optional phase, research the current official
documentation, supported Prowlarr sync behavior, container image versions,
and the manual-only controls for each selected tool. Record the outcome and
obtain an explicit decision on which tools to deploy.

This gate was completed September 11: the user explicitly chose Radarr/Sonarr,
the official-source review is recorded in `usenet-infra/docs/discovery.md`, and
the current deployment/acceptance evidence is in the authoritative handoff above.

## 5. Content policy

Prowlarr may be installed for index/search management, but default to a conservative configuration where an arbitrary index result cannot silently become a permanent catalog entry.

Create a small provenance mechanism for permanent catalog items.

A useful per-item manifest would contain fields conceptually like:

```yaml
id:
title:
category:
source:
acquired_at:
remote_path:
size:
checksum:
notes:
```

Use sensible schemas rather than slavishly following this example.

For integration testing, use content that is clearly authorized, public-domain, freely redistributable, generated specifically for the test, or an official provider/client test mechanism.

## 6. Repository

Create a dedicated directory in this repository, something along these lines:

```text
usenet-infra/
├── README.md
├── Makefile
├── .gitignore
├── .sops.yaml
│
├── terraform/
│   ├── versions.tf
│   ├── providers.tf
│   ├── variables.tf
│   ├── main.tf
│   ├── network.tf
│   ├── firewall.tf
│   ├── outputs.tf
│   └── terraform.tfvars.example
│
├── ansible/
│   ├── inventory.example.yml
│   ├── site.yml
│   ├── cloud.yml
│   ├── qnap.yml
│   └── roles/
│
├── compose/
│   ├── cloud/
│   │   └── compose.yaml
│   └── qnap/
│       ├── compose.yaml
│       └── olivetin/
│           └── config.yaml
│
├── config/
│   ├── catalog.schema.*
│   └── examples/
│
├── scripts/
│   ├── catalog-list
│   ├── catalog-pull
│   ├── catalog-evict
│   ├── catalog-status
│   ├── catalog-promote
│   └── healthcheck
│
└── docs/
    ├── account-setup.md
    ├── architecture.md
    ├── qnap-bootstrap.md
    ├── operations.md
    ├── recovery.md
    └── costs.md
```

Change this structure where there is a concrete engineering reason.

The repository should ultimately be good enough that six months from now I can understand and reproduce the system without relying on this chat.

## 7. Terraform: Hetzner Cloud

Use the official/current Hetzner Cloud Terraform provider.

Provision at minimum:

- cloud server,
- SSH key,
- appropriate primary IP,
- Hetzner firewall,
- any useful labels,
- optionally a private network if it provides actual value.

Start with an appropriately sized general-purpose VM.

Prior thinking favored something around:

- 8 vCPU,
- 16 GB RAM,
- ~160 GB local SSD,

because PAR repair and decompression can be CPU/I/O intensive while the actual 20 TB library lives elsewhere.

Re-evaluate the current Hetzner offerings and choose the best price/performance instance.

Avoid attaching hundreds of GB of expensive cloud block storage merely to warehouse completed content.

Local VM storage is primarily:

- application state,
- SABnzbd incomplete downloads,
- completed-download staging,
- PAR repair,
- decompression,
- temporary transfer staging.

Terraform should not destroy the canonical Storage Box as an incidental consequence of rebuilding the VM.

Use Terraform version constraints and provider lock files.

Do not commit Terraform state containing secrets.

## 8. Cloud security

The cloud VM should have a deliberately tiny external attack surface.

Target:

```text
Internet:
    SSH -> allowed only as needed

Not Internet-exposed:
    SABnzbd UI
    Prowlarr UI
```

Prefer binding administrative HTTP services to localhost or an internal Docker network.

For interactive administration, SSH port forwarding is acceptable, e.g. conceptually:

```text
localhost -> SSH tunnel -> localhost:SAB
localhost -> SSH tunnel -> localhost:Prowlarr
```

Do not publish SABnzbd or Prowlarr directly to the public Internet merely for convenience.

Use:

- SSH keys,
- no SSH password login where practical,
- no root SSH login,
- sane host firewalling,
- automatic security updates if appropriate.

If restricting SSH to my current public IP is practical, make that a Terraform variable so changing networks does not require hand-editing resources.

## 9. Cloud configuration with Ansible

Provision the VM declaratively.

Ansible should install/configure at least:

- Docker Engine,
- Docker Compose V2/plugin,
- rclone if used on the host,
- required filesystem directories,
- users/groups,
- permissions,
- application directories,
- update policy,
- log rotation where appropriate.

Do not manually SSH into the machine and perform undocumented snowflake configuration unless diagnosing something.

If you temporarily make a manual change while debugging, incorporate the final version into Ansible/Compose afterward.

## 10. Cloud Docker Compose

Run at least:

- SABnzbd
- Prowlarr

Use well-maintained images and pin versions intentionally rather than blindly depending forever on `latest`.

Persist application state outside the containers.

Use a directory structure roughly like:

```text
/srv/usenet/
├── config/
│   ├── sabnzbd/
│   └── prowlarr/
├── downloads/
│   ├── incomplete/
│   └── complete/
├── scripts/
└── logs/
```

Make UID/GID ownership explicit.

Use `restart: unless-stopped` or the appropriate equivalent.

Add meaningful health checks where the applications support them.

Do not expose more ports than required.

## 11. Configure SABnzbd

Configure:

- primary NNTP provider,
- TLS,
- appropriate connection count,
- a lower-priority secondary block only if later justified and approved,
- incomplete directory,
- completed staging directory,
- PAR verification/repair,
- unpacking,
- sensible free-space thresholds.

Do not simply max out provider connection counts. Determine enough connections to saturate the useful bandwidth without pointless overhead.

Make sure a large download cannot casually fill the VM's root filesystem and destabilize the server.

Configure clear categories only where useful for organization, not for automatic acquisition.

## 12. Configure Prowlarr

Configure the selected indexers and verify their API connectivity.

Do not initially configure broad unattended acquisition rules.

If Prowlarr is connected to SABnzbd, ensure that deliberate human action is still required to initiate an acquisition.

## 13. Storage Box layout

Design a clean canonical hierarchy.

For example:

```text
catalog/
├── movies/
├── television/
├── audio/
├── books/
├── software/
├── archives/
└── other/
```

Do not assume these exact categories are ideal; choose something maintainable.

Each permanent catalog object should be associated with provenance metadata.

Avoid relying exclusively on filenames for identity.

## 14. Storage Box credentials and QNAP safety

I want the QNAP unable to accidentally delete the canonical catalog.

Take advantage of Hetzner Storage Box sub-account restrictions/read-only support if currently available.

A desirable pattern is:

```text
Storage Box main account
    full write access
    used only by cloud ingestion

catalog directory
    populated by cloud VM

QNAP-specific subaccount
    restricted to catalog directory
    READ ONLY
```

If Storage Box sub-account directory semantics require a slightly different layout, adapt accordingly.

The result that matters is:

**credentials present on the QNAP must not have permission to modify or delete the canonical remote catalog.**

Use SSH-key authentication where supported.

Verify server fingerprints rather than blindly accepting them.

## 15. Moving completed acquisitions to Storage Box

Do not download directly into an SFTP/rclone mount.

SABnzbd should:

1. download locally,
2. verify,
3. repair if needed,
4. unpack locally,
5. finish locally,
6. then transfer the completed object to Storage Box.

Implement a robust promotion mechanism.

Possible approaches include:

- SAB post-processing script,
- host-side transfer queue,
- small transfer service.

Choose the least fragile implementation.

Requirements:

- partial uploads must not appear as complete catalog entries;
- failed uploads remain recoverable;
- a successful transfer is verified before local staging is removed;
- retries are safe/idempotent;
- promotion updates catalog metadata;
- failure is obvious in logs/status.

Avoid a polling monstrosity if SAB's supported post-processing mechanism handles the workflow cleanly.

## 16. QNAP reconnaissance

Before changing the NAS, discover:

- exact QNAP model,
- CPU architecture,
- QTS vs QuTS hero,
- OS version,
- Container Station version,
- Docker version,
- Compose V2 availability,
- OliveTin image compatibility with the exact CPU architecture and kernel,
- HybridMount version, available mount modes, free-license availability, and whether
  reserved cache is supported on this model/OS,
- existing shares,
- relevant filesystem paths,
- available local storage,
- intended destination share for cached content,
- NAS LAN address.

Do not assume `/share/CACHEDEV1_DATA/...` or another model-specific physical path.

Prefer stable QNAP shared-folder paths such as `/share/<ShareName>/...` when appropriate.

Do not interfere with unrelated containers or NAS services.

## 17. QNAP bootstrap

Minimize non-declarative setup.

Human/manual steps may include:

- installing/updating Container Station,
- temporarily enabling SSH,
- confirming an administrative account that can SSH,
- creating a dedicated QNAP shared folder if QTS requires GUI/API management for it.
- approving a stable LAN-only address and local account for the catalog dashboard.

Document each unavoidable step precisely in `docs/qnap-bootstrap.md`.

After bootstrap, application configuration should come from the repository.

Current QNAP systems use Compose V2 syntax:

```text
docker compose
```

not legacy:

```text
docker-compose
```

Verify on this particular NAS.

## 18. QNAP implementation

The QNAP does NOT need SABnzbd or Prowlarr.

Its job is selective caching and providing the primary catalog-management UI.

Prefer a containerized rclone implementation under Container Station so QNAP firmware updates do not erase miscellaneous packages installed into the base OS.

Create a QNAP Compose stack using the current official/well-maintained rclone image
and a pinned OliveTin image. OliveTin is the user-facing control surface; the
existing manifest-aware catalog tool remains the implementation of list, status,
pull, evict, verification, and failure recording.

Conceptually it needs access to:

```text
/share/Container/usenet/
    configuration/scripts/UI configuration

/share/<LOCAL_LIBRARY>/
    local cached content
```

The Storage Box credential on the QNAP must be read-only remotely.

Do not put that private key or rclone secret in Git.

Run the dashboard with least privilege:

- bind it only to the NAS LAN address or loopback behind an already trusted private
  access path; do not expose it directly to the Internet;
- require authentication even on the LAN;
- expose only predefined catalog actions with validated arguments, never a general
  shell or arbitrary rclone command field;
- give it only the catalog scripts, read-only Storage Box configuration/key material,
  catalog state, transfer staging, and local cache paths it requires;
- do not mount the Docker socket into the dashboard container;
- run as the dedicated numeric QNAP UID/GID with a read-only root filesystem where
  practical; and
- keep the UI configuration declarative and versioned in Git, with credentials kept
  in ignored runtime files or the chosen encrypted-secret mechanism.

The dashboard must invoke the same catalog backend as the CLI. It must not implement
raw remote-to-local copies that bypass manifest resolution, free-space checks, hidden
staging, SHA-256 verification, atomic publication, retry behavior, or failure records.

## 19. QNAP catalog dashboard and fallback commands

The authenticated OliveTin dashboard is the primary interface for normal cache
management. It should be usable from a desktop or phone without copying item IDs or
shell commands.

The main view should show at minimum:

- remote item count and total size;
- local item count and total size;
- available NAS capacity and configured reserve;
- transfers in progress and recorded failures;
- one row or card per catalog item with title, category, size, and state;
- clear states such as `remote only`, `downloading`, `local`, and `failed`; and
- only the action valid for the current state, such as **Download**, **Retry**, or
  **Remove local copy**.

Generate the dashboard's item choices/cards from structured catalog output rather
than requiring a free-form item ID. Refresh that data on demand and after each action.
Display long-running pull progress or, where exact byte progress is unavailable,
provide an unambiguous running state plus accessible execution output/history.

Required interactions:

### Browse and inspect

- Search or filter by title and category.
- Distinguish remote-only content from verified local content at a glance.
- Show useful failure text without requiring an SSH session for the first diagnosis.
- Provide a compact status/capacity summary on the same dashboard.

### Download to QNAP

- Select an item and press **Download**; do not require copying its ID.
- Validate that the item exists remotely and that sufficient local free space remains.
- Copy directly from Storage Box to QNAP through hidden staging.
- Support safe retry, verify all manifest SHA-256 values, atomically publish the local
  object, update local state, and refresh the dashboard.

### Remove the local copy

- Show a confirmation that explicitly says the canonical remote copy will remain.
- Delete only the QNAP object and local state record.
- Refresh the item to `remote only` after success.
- Never issue an rclone delete or other remote-mutating operation.

OliveTin execution history should provide a simple audit trail of who initiated each
operation, its arguments, status, and output. Configure timeouts so large transfers
can remain active without becoming orphaned merely because a browser closes.

Keep very simple `just` recipes for recovery, automation, testing, and advanced
operation. They are not the primary day-to-day interface.

I want recipes conceptually like:

```text
catalog-list
catalog-status
catalog-pull <item>
catalog-evict <item>
```

Behavior:

### catalog-list

Show remote catalog items with useful information such as:

- title/path,
- size,
- category,
- whether present locally.

### catalog-status

Summarize:

- remote catalog size,
- local cache size,
- transfers in progress,
- failed transfers,
- available NAS capacity.

### catalog-pull

Example:

```text
catalog-pull "some/catalog/item"
```

It should:

- validate the item exists remotely,
- verify sufficient local free space,
- copy it from Storage Box to QNAP,
- support safe resume/retry,
- verify successful completion,
- update local status.

### catalog-evict

Example:

```text
catalog-evict "some/catalog/item"
```

It should:

- delete only the QNAP copy,
- leave the remote Storage Box copy untouched.

Because the NAS credential is read-only, even a bug in this tooling should not be able to erase the canonical copy.

Do not use rclone's general-purpose Web GUI as the primary interface: it can initiate
raw transfers that bypass catalog invariants. It may be enabled temporarily for
administrative diagnosis only, bound to loopback and authenticated, then disabled.

During QNAP reconnaissance, run a time-boxed HybridMount compatibility experiment if
the installed version supports File Cloud Gateway with generic WebDAV storage:

1. use only the existing server-enforced read-only Storage Box subaccount;
2. verify that the mount can browse and read without any write permission;
3. verify the cloud/local/downloading icons and reserved-cache behavior;
4. attempt overwrite and delete against a disposable writer-created sentinel and
   require both to fail remotely; and
5. record the result in `docs/qnap-bootstrap.md`.

HybridMount is optional. If it cannot mount the read-only account, requires a writable
credential, obscures integrity/failure state, or cannot preserve the manifest-aware
workflow, stop the experiment and retain OliveTin. Do not adopt ordinary two-way sync,
an automatic bidirectional mount, or a writable remote credential as a workaround.

## 20. Transfer tuning

The expected remote-to-home traffic is around 1 TB/month.

Tune conservatively.

Make transfer concurrency and bandwidth limits configurable.

Consider:

- NAS disk performance,
- home WAN speed,
- Atlantic latency,
- Storage Box connection limits,
- ability to resume interrupted transfers.

Do not optimize benchmarks at the expense of reliability.

Use rclone transfer/check settings appropriate to SFTP and verify what checksums the Storage Box backend actually supports instead of assuming.

## 21. Catalog metadata

Implement the lightest-weight catalog that solves the problem.

I do not need Kubernetes or a distributed database.

SQLite, structured JSON/YAML manifests, or another simple format is acceptable.

I should be able to answer:

```text
What exists remotely?
What exists locally?
How large is it?
Where did it come from?
What is its authorization/provenance?
When was it acquired?
Has its integrity been checked?
```

The remote files remain the source of truth for bytes.

Catalog metadata should itself be backed up.

## 22. Secrets

Never commit:

- Usenet passwords,
- indexer API keys,
- Hetzner Cloud tokens,
- Storage Box passwords,
- SSH private keys,
- rclone cleartext credentials.

Use:

- SSH keys,
- restrictive file permissions,
- environment files excluded from Git,
- and/or sops+age.

Produce `.env.example` or equivalent showing required variable names without values.

At the end, explicitly scan the Git working tree/history for accidentally committed secrets.

## 23. Backups

Infrastructure source code is in Git.

Back up important application configuration separately from the 20 TB catalog:

- SABnzbd settings,
- Prowlarr settings/database,
- OliveTin authentication/runtime state and execution history where it is not
  reproducible from Git,
- catalog metadata,
- critical scripts/configuration.

Do not confuse Storage Box snapshots with an independent backup of the 20 TB collection.

I am primarily concerned with being able to rebuild the service configuration. The bulk content itself does not initially need an expensive second 20 TB replica unless we decide otherwise.

## 24. Observability

Create a useful health/status backend and surface the QNAP-relevant results in the
catalog dashboard. Retain the command for automation and recovery.

At minimum detect:

- VM unavailable,
- SABnzbd unhealthy,
- Prowlarr unhealthy,
- provider authentication failure,
- indexer API failure,
- Storage Box unavailable,
- Storage Box approaching capacity,
- VM scratch storage approaching capacity,
- failed remote promotions,
- QNAP local storage approaching capacity,
- catalog dashboard unavailable or unhealthy, and
- failed or stalled QNAP pulls visible in both health output and the dashboard.

Avoid deploying Prometheus/Grafana just because they exist.

Simple health scripts and container logs are enough unless monitoring requirements justify more.

## 25. Updating

Document a safe upgrade workflow:

```text
git pull
terraform plan
ansible-playbook ...
docker compose pull
docker compose up -d
healthcheck
```

Pin versions sufficiently that upgrades are deliberate.

If using Dependabot/Renovate or similar, configure it to propose changes rather than silently upgrading production.

## 26. Recovery drills

Document how to rebuild from:

### Lost cloud VM

Expected outcome:

```text
terraform apply
ansible-playbook
restore app config
docker compose up
reconnect Storage Box
```

Canonical library survives.

### Lost QNAP configuration

Recreate QNAP Compose/configuration and reconnect with read-only Storage Box credentials.

Canonical library survives.

### QNAP disk failure

Replace/restore NAS storage and selectively pull desired material again.

Canonical library survives.

### Lost Terraform state

Document the recovery/import procedure.

## 27. Testing

Do not declare success merely because containers show `running`.

Perform an end-to-end integration test with unquestionably authorized test content.

Verify:

1. Primary Usenet TLS connection succeeds.
2. Secondary provider: deferred; not required for the current Eweka-only baseline.
3. Both indexers' API tests succeed.
4. SAB can process an authorized/test NZB or equivalent provider-supported test.
5. Verification/unpacking works if applicable.
6. Promotion to Storage Box succeeds.
7. Provenance/catalog record exists.
8. The catalog dashboard sees the remote item and shows it as `remote only`.
9. The item can be selected and downloaded in the dashboard without copying its ID.
10. The dashboard shows a running state and retains useful success/failure output.
11. The underlying pull stages safely and checks every manifest SHA-256 value.
12. Local status and the dashboard report the verified item as `local`.
13. The dashboard requires confirmation and removes only the NAS copy.
14. The dashboard returns the item to `remote only`, and the remote item still exists.
15. The fallback `catalog-list`, `catalog-status`, `catalog-pull`, and `catalog-evict`
    commands operate through the same backend and preserve identical safety behavior.
16. QNAP read-only credentials cannot delete or overwrite the remote item.
17. The dashboard requires authentication and is unreachable from the public Internet.
18. Restarting the relevant containers does not break configuration or execution history.
19. Git contains no credentials.

Do not reboot the entire QNAP without asking me first.

## 28. Cost verification

At the end, produce an updated recurring-cost table.

Include:

- Hetzner VM,
- IPv4 if separately charged,
- Storage Box,
- primary Usenet provider,
- secondary/block provider amortization only if later purchased (currently deferred),
- indexer subscriptions,
- any other recurring service you added.

Separate:

- monthly recurring,
- annual subscriptions converted to monthly equivalent,
- one-time purchases.

Flag anything that has pushed expected recurring cost materially beyond ~$90/month.

## 29. Documentation to leave behind

The finished repository must explain:

### `README.md`

Very short overview, primary dashboard URL/access method, and fallback commands.

### `docs/architecture.md`

Architecture, trust boundaries, data flow, dashboard-to-catalog-backend boundary, and
why the UI has neither a Docker socket nor remote write authority.

### `docs/account-setup.md`

What accounts exist, why each exists, subscription tier, renewal information and where credentials are stored.

Never include actual passwords/API keys.

### `docs/qnap-bootstrap.md`

Any manual QNAP setup required before IaC takes over, dashboard authentication/access,
and the result of the optional HybridMount read-only compatibility experiment.

### `docs/operations.md`

Normal operations:

- searching,
- intentional acquisition,
- catalog promotion,
- browsing and filtering the catalog in the dashboard,
- downloading to and removing from the NAS through dashboard controls,
- reading transfer output/history and diagnosing a failed pull,
- using listing, pull, status, and eviction commands as a fallback,
- checking failures,
- updating software.

### `docs/recovery.md`

Rebuild/recovery steps, including recreating the dashboard and using the CLI backend
while it is unavailable.

### `docs/costs.md`

Current recurring costs with date checked. Record OliveTin as no recurring software
cost and include any QNAP license only if an optional HybridMount feature is actually
adopted after testing.

## 30. How to interact with me

Work incrementally.

At the beginning:

1. Briefly restate the target architecture.
2. Research/verify the current products.
3. Tell me if you recommend changing any material architectural choice.
4. Then begin account setup.

During account signup, give me only the immediate human actions required.

For example:

```text
I need you to create the Eweka account now.

Choose: <specific verified plan>
Price: <verified price>
Reason: <one sentence>

When finished, do not paste the password here.
Tell me only that the account exists, and I will continue.
```

Do not make me manually transcribe configuration values that you can discover or apply yourself.

Once SSH/API access is available, do the implementation rather than turning the rest into a tutorial.

Before destructive actions, show me exactly what will be deleted/replaced.

Do not repeatedly ask me questions whose answers can be obtained by inspecting the existing systems.

If an implementation choice is minor, choose a sensible default and proceed.

## 31. Completion criteria

The project is complete when I can do all of the following:

- open the authenticated catalog dashboard through its private LAN access path;
- browse or filter catalog items and distinguish `remote only`, `downloading`,
  `local`, and `failed` states;
- select **Download** without copying an item ID and see its execution status;
- select **Remove local copy**, confirm the action, and see the item return to
  `remote only`; and
- perform the same operations with the recovery CLI when the dashboard is unavailable.

The underlying infrastructure and recovery interface must also support:

```text
# inspect infrastructure
terraform plan

# rebuild/configure cloud
ansible-playbook ...

# inspect containers
docker compose ps

# see catalog
just catalog-list

# make an item local
just catalog-pull <item>

# inspect status
just catalog-status

# remove only the local copy
just catalog-evict <item>
```

and the following statements are true:

- Hetzner Storage Box is the canonical content store.
- Acquisition continues even if the QNAP is offline.
- Completed cloud acquisitions are safely promoted to Storage Box.
- The QNAP can pull selectively through a point-and-click dashboard.
- Dashboard actions use the same manifest-aware, verified catalog backend as the CLI.
- The dashboard requires authentication, is not Internet-exposed, provides no general
  shell, has no Docker socket, and has no remote write authority.
- QNAP credentials cannot destroy remote content.
- Administrative web UIs are not exposed publicly.
- NNTP uses TLS.
- Infrastructure is substantially reproducible from Git.
- Secrets are not in Git.
- A complete rebuild procedure exists.
- End-to-end authorized-content testing has succeeded.
- Current operating cost is documented.
- No unattended piracy-oriented acquisition automation has been enabled.

When finished, give me a concise system handoff containing:

1. architecture actually implemented,
2. repository location,
3. dashboard and service endpoints/private access methods,
4. normal dashboard workflow plus five or fewer fallback commands,
5. recurring monthly cost,
6. known remaining limitations.
