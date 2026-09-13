# Usenet acquisition and selective cache

This directory defines a private, deliberately operated system for content the
owner is authorized to obtain. SABnzbd and Prowlarr run on a replaceable Hetzner
VM. A protected Storage Box is the canonical byte store: it starts as a 1 TB
BX11 and grows in place through BX21 and BX31 to the eventual 20 TB BX41 target.
The QNAP has a separate server-enforced read-only Storage Box identity and holds
only selected, locally cached items.

Start with the [current plan/handoff](../plan.md) and [agent guide](AGENTS.md).
Radarr/Sonarr provide discovery, acquisition and native imports; Plex on the QNAP
provides NAS and remote playback with separate general/private libraries.
OliveTin is the transitional selective-copy/removal interface. Native-title copy
support is prepared in source; deployment and live-copy acceptance remain pending.
The prominent [Downloads status panel](docs/download-status.md) is live for legacy
copies; its runbook records telemetry behavior, reproducible tests and limitations.
Real TV-client playback/privacy acceptance is deferred. See [native media](docs/native-media.md).

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

Backend web interfaces bind to cloud loopback; the authenticated proxy exposes
the existing private VPN listener. Acquisition does not depend on the QNAP.
Native Arr imports move completed scratch into the synchronous Storage Box
library; completed-client cleanup is enabled. The old publisher timer is disabled.
Legacy manual catalog promotion remains available only for independent items,
never for scratch owned by Arr.

Account setup and QNAP bootstrap are complete. Their runbooks are rebuild
references, not cold-agent starting tasks. Routine operation and recovery are
documented under `docs/`; the current handoff lists the next work.

For checkout-loss recovery, follow [secrets and state recovery](docs/secrets-recovery.md).
The Git-hosted SOPS vault holds the small inputs; versioned master-encrypted
state/archive packages live on the QNAP outside the app/cache directories.
Inject the existing `SOPS_AGE_KEY` to restore. The operator keeps the same master
in 1Password and on paper. The [full published-source secrets/state drill](recovery/drills/20260911T194408Z.json)
passed: 24 vault entries, 15 bundle entries and six keypairs; repeat restoration
added zero files. Separate [checkout recovery](docs/checkout-recovery.md) preserves
1,319 local files, Git history and five stashes; independent restoration and the
readiness check passed. Rerun that check against current local work and published
HEAD before deletion. HA/UniFi/full-machine recovery remains separate and NAS-loss
protection is deferred. `just --no-dotenv secrets-check` alone checks metadata.

[Radarr and Sonarr discovery](docs/discovery.md) is now deployed behind the
existing private catalog login at `http://10.77.0.1:19696/radarr/` and
`http://10.77.0.1:19696/sonarr/`. Interactive searches use the existing indexers
and SAB; automatic search and 15-minute RSS checks are enabled for monitored
titles. Native imports and completed-client cleanup are enabled.
[Scheduled backups](docs/scheduled-backups.md) protect current cloud/QNAP/Plex
configuration using existing recoverable identities.

Capacity is reviewed at an 80% warning and upgraded before 90%; expansion is a
deliberate, reviewed Terraform change, not an automatic purchase. See
[costs](docs/costs.md) and [operations](docs/operations.md).
The current [NAS/Plex layout](docs/nas-plex-layout.md) separates the existing
private collection from general movies/TV and documents the restricted profile.
The [workflow review](docs/media-workflow-review.md) explains which native
Radarr/Sonarr/Plex features replace the transitional catalog workflow.

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

Existing private connection inputs are in `.env`; recover them through the
vault/snapshot runbook in a new clone rather than overwriting them from an example. Secrets, private keys,
Terraform state, live inventory, runtime configuration, and backups are ignored
by Git. The normal LAN route uses `10.77.0.1` as documented in the handoff. An optional
administrative tunnel is `just cloud-ui` (root: `just usenet-cloud-ui`); then use `http://127.0.0.1:8080` for SABnzbd and
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

An earlier cloud configuration backup verified 589 files and two SQLite
databases. Current scheduled archives also cover Radarr/Sonarr and are documented
in [scheduled backups](docs/scheduled-backups.md). Manual recovery commands from
the repository root remain available:

```sh
just usenet-backup-cloud
just usenet-backup-verify /absolute/path/to/archive.tar.age
just usenet-backup-restore /absolute/path/to/archive.tar.age /absolute/path/to/new-recovery-directory
```

The verified scheduled cloud, QNAP and Plex archives are identified in
[the committed receipt](recovery/drills/scheduled-backups-20260911.json);
the previous archives are preserved as historical recovery material.

These capture, verify, or restore into a fresh private directory without
restarting applications. See [recovery](docs/recovery.md)
for scope and key retention. An isolated offline restore-startup drill passed
for both pinned cloud applications, preserving configuration and database rows;
test containers and plaintext copies were removed. First live QNAP capture,
verification, and isolated startup restore also passed, preserving
authentication/session/history. Host-owned daily backups now run with hourly
retry; an intentional manual capture can protect a new configuration checkpoint.
These isolated drills did not replace the VM or NAS.
