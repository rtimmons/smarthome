# Usenet acquisition and selective cache

This directory defines a private, deliberately operated system for content the
owner is authorized to obtain. SABnzbd and Prowlarr run on a replaceable Hetzner
VM. A protected Storage Box is the canonical byte store: it starts as a 1 TB
BX11 and grows in place through BX21 and BX31 to the eventual 20 TB BX41 target.
The QNAP has a separate server-enforced read-only Storage Box identity and holds
only selected, locally cached items.

OliveTin is the primary catalog interface: browse items, download a verified
local copy, or confirm removal of only the NAS copy. Its predefined actions use
the same manifest-aware backend as the recovery commands below.

The cloud infrastructure is live. Eweka's saved settings, authenticated
connection test, and official 100 MB download/processing pass. The resulting
two files are promoted to the Storage Box with verified bytes and provenance.
Eweka's final charged tier/renewal details remain unverified.
Eweka is the sole provider for the current baseline. UsenetExpress is deferred
unless real missing articles or a completion gap warrants optional fill.
NZBGeek's one-year subscription is paid at $12 USD and independently reads
active through 2027-09-13 22:01:53 UTC. It is saved and enabled in Prowlarr,
and its credentialed connection test passed with strict certificate validation.
NZBFinder Pro is paid according to the user, with the Pro badge independently
observed. It is now saved and enabled in Prowlarr, with a successful live
credentialed test under strict certificate validation. Both indexer connections
and the internal SABnzbd client are complete. The QNAP is confirmed as a
TS-451D2 running QTS 5.2.10.3577 with 4 GB RAM; the user created its enabled
`usenet-deploy` account and dedicated-key SSH login passed. The exact NAS host
key is pinned under user-authorized first-use trust. Runtime discovery, shares,
private credentials, and NAS deployment are complete as of 2026-09-10. The
dashboard runs at `http://192.168.1.66:1337` and authenticated login works.
Private binding, restricted runtime identity, and server-enforced read-only NAS
access are verified. Dashboard download/reconnection/confirmed eviction, CLI
parity with the dashboard stopped, remote preservation, restart persistence,
and both cloud/NAS isolated configuration-startup restore drills passed.

The remaining required acceptance check is external dashboard reachability;
it awaits explicit approval after automatic review rejected the probe. The
private LAN listener alone does not prove Internet isolation. Follow
[QNAP bootstrap](docs/qnap-bootstrap.md) for actual paths, trust, and access,
and [validation](docs/validation.md) for evidence and remaining limits.

Administrative web interfaces bind to cloud loopback only. Acquisition does not
depend on the QNAP, and no unattended search-to-permanent-catalog automation is
enabled. Promotion is a deliberate command that hashes locally, uploads beneath
`.incoming`, verifies the remote bytes, publishes the object, then publishes its
provenance manifest last.

Start with [account setup](docs/account-setup.md), then follow the
[QNAP bootstrap](docs/qnap-bootstrap.md). Architecture, routine operation, and
recovery are documented under `docs/`.

For checkout-loss recovery, follow [secrets and state recovery](docs/secrets-recovery.md).
The Git-hosted SOPS vault holds the small inputs; versioned master-encrypted
state/archive packages live on the QNAP outside the app/cache directories.
Inject the existing `SOPS_AGE_KEY` to restore. The operator keeps the same master
in 1Password and on paper. The [full published-source secrets/state drill](recovery/drills/20260911T194408Z.json)
passed: 24 vault entries, 15 bundle entries and six keypairs; repeat restoration
added zero files. HA/UniFi and full machine recovery remain unproven, and checkout
deletion is still unsafe. `just --no-dotenv secrets-check` alone checks metadata.

Capacity is reviewed at an 80% warning and upgraded before 90%; expansion is a
deliberate, reviewed Terraform change, not an automatic purchase. See
[costs](docs/costs.md) and [operations](docs/operations.md).

Recovery commands, run from this directory after the NAS is configured:

```sh
just catalog-list
just catalog-status
just catalog-pull "authorized-test-example"
just catalog-evict "authorized-test-example"
just qnap-health
```

`just usenet-qnap-recon` at the repository root repeats read-only NAS metadata
checks. It discovers Container Station's Docker path without changing the host
environment.

Copy `.env.example` to `.env` for non-secret SSH targets. Secrets, private keys,
Terraform state, live inventory, runtime configuration, and backups are ignored
by Git. Open the cloud applications with `just cloud-ui` (from the repository
root: `just usenet-cloud-ui`), then use `http://127.0.0.1:8080` for SABnzbd and
`http://127.0.0.1:9696` for Prowlarr while the tunnel is open. Run `just test`
before applying changes.

Prowlarr's Forms login was configured privately. From the repository root,
`just usenet-prowlarr-indexer inspect` reads approved NZBGeek settings and
`just usenet-prowlarr-indexer test` repeats the saved credentialed test without
returning the API key. An optional second argument selects `nzbgeek` (default)
or `nzbfinder`; `just usenet-prowlarr-indexer test nzbfinder` retests Finder.
NZBGeek uses priority 25 and its HTTPS API endpoint;
daily quotas remain unknown and unset. The internal SABnzbd download client
is enabled and passed its credentialed tests; inspect or retest it with
`just usenet-prowlarr-download-client inspect` or
`just usenet-prowlarr-download-client test`.
The Prowlarr application API key was rotated and its protected dependants
synchronized; the old key is rejected and post-rotation tests passed.
Cloud health exits successfully. Seven historical SABnzbd warnings were
classified as six setup hostname blocks and one Direct Unpack autotest notice;
none were authentication, provider, or TLS failures. Direct Unpack was restored
to disabled and all intended settings read back correctly with no active jobs.

From the repository root, `just usenet-sab-provider inspect`,
`just usenet-sab-provider configure`, and `just usenet-sab-provider test`
inspect Eweka, apply the documented primary settings while preserving saved
credentials, and repeat its built-in connection test. Output excludes credentials.
SABnzbd's cloud download paths, 30G free-space thresholds, and processing
defaults are also applied and verified. Use `just usenet-sab-settings inspect`
or `just usenet-sab-settings apply` for those bounded settings. Use
`just usenet-sab-smoke-test status` to inspect the completed official 100 MB
test; `start` will not enqueue a second job when its saved receipt exists.
The promoted catalog ID is `sabnzbd-official-100mb-2026-09-10`. Its NAS
dashboard download, reconnect-during-transfer, verified local state, and
confirmed eviction back to remote-only passed. The remaining acceptance
checks are tracked in [validation](docs/validation.md).

The latest encrypted cloud configuration backup includes both indexer keys,
the rotated Prowlarr application key, login/client settings, restored Direct
Unpack setting, and current cloud catalog/health scripts. It verified 589 files
and two SQLite databases locally. From the repository root:

```sh
just usenet-backup-cloud
just usenet-backup-verify /absolute/path/to/archive.tar.age
just usenet-backup-restore /absolute/path/to/archive.tar.age /absolute/path/to/new-recovery-directory
```

The latest verified cloud and QNAP archives are identified in
[recovery](docs/recovery.md);
the previous archives are preserved as historical recovery material.

These capture, verify, or restore into a fresh private directory without
restarting applications. See [recovery](docs/recovery.md)
for scope and key retention. An isolated offline restore-startup drill passed
for both pinned cloud applications, preserving configuration and database rows;
test containers and plaintext copies were removed. First live QNAP capture,
verification, and isolated startup restore also passed, preserving
authentication/session/history. Backups are manual; rerun them after
configuration changes. These isolated drills did not replace the VM or NAS.
