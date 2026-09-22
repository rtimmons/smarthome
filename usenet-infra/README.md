# Usenet acquisition and selective NAS copies

Start with the [current plan](../plan.md), its
[cutover acceptance criteria](../plan.md#one-time-cutover--no-library-migration-or-replay), and the
[agent guide](AGENTS.md). This README is an operating entrypoint; dated receipts
record what was tested. Account setup and infrastructure bootstrap are complete.

## Current workflow

September 20: the approved [storage expansion](docs/storage-expansion-20260920.md)
is deployed: BX21 and a [300 GB repair volume](docs/repair-spool.md). Capacity
preflight passes. The [Arr ownership cutover](docs/native-cutover.md) uses the
user-approved native import and cleanup policy for new requests; direct carts and legacy workers are disabled. Native
requests use separate categories and a 100 GiB download limit. Release polling
remains off to preserve the pre-existing missing-media backlog.

Radarr/Sonarr provide discovery and explicit native searches using Eweka
and the configured NZBGeek/NZBFinder indexers. SAB downloads and processes on cloud
scratch; Arr imports into the synchronous Storage Box library and owns completed
client cleanup. The retired publisher stays disabled. Preserve the five legacy
objects/manifests and their native hard-linked adoptions; never run a second mover
against Arr scratch.

New requests start in Radarr or Sonarr. Use add-and-search or an explicit search
for the selected movie or episode; check the intended episode scope before
submitting. Each application owns its own SAB category. Wait for completed
import and cleanup before requesting another large release. The 100 GiB limit
and 30 GiB reserves remain active. Prowlarr supplies indexers; its direct download
client and the old cart feeds are disabled. Historical feed state, journals,
verification receipts and all three held requests remain preserved.

Plex runs on the QNAP with separate NAS/remote Movies and TV libraries. OliveTin
provides explicit per-title NAS copy/removal actions for both native titles and
legacy catalog entries. Copies use the server-enforced read-only Storage Box
account, capacity admission, private staging, SHA-256 verification and atomic
publication. Native publication additionally refuses destination replacement.
The NAS retains a 100 GiB reserve; no whole-library sync runs.
See [native media](docs/native-media.md), [NAS/Plex layout](docs/nas-plex-layout.md)
and [download status](docs/download-status.md).

Native copying is deployed and [accepted for one selected movie](recovery/drills/native-copy-live-20260913.json):
media-002 was verified, automatically indexed in Movies (NAS), and safely
repeated without recopying. The authenticated Downloads graph, browser reconnect,
verification and completed states passed live checks. TV publication uses
`TV Shows/library`, with `.staging` outside Plex's source and the TV gate enabled.
A real selective TV transfer to NAS remains unverified. Native movie/episode
imports and source cleanup passed September 20; see the cutover receipt.
Apple TV/Roku playback and startup privacy are deferred by the user.

## Access and routine operation

| Interface | Private address |
| --- | --- |
| Radarr | `http://10.77.0.1:19696/radarr/` |
| Sonarr | `http://10.77.0.1:19696/sonarr/` |
| Prowlarr | `http://10.77.0.1:19696/` |
| SAB | `http://10.77.0.1:18080/` |
| NAS copy dashboard | `http://192.168.1.66:1337/` |
| Filex staging portal | `https://10.77.0.1:5213/` |
| Usenet field guide | `http://192.168.1.66:8090/` |
| Plex | `http://192.168.1.66:32400/web` |

The existing LAN route and private logins are already configured. Connection
inputs in ignored `.env` and Ansible inventory select dedicated identities and
verified host keys. Recover missing inputs through the documented vault/snapshot
chain; do not repeat setup, replace credentials or deploy merely to inspect state.

Read-only checks from the repository root:

```sh
just usenet-discovery-health
just usenet-cloud-health
just usenet-qnap-health
just usenet-filex-status
just native-list
just native-status
just catalog-status
```

For an explicitly selected native title, `just native-pull "native-<id>"` copies
and verifies it; `just native-evict "native-<id>"` removes only its owned NAS copy.
Legacy commands are `catalog-list`, `catalog-pull`, and `catalog-evict`. These
catalog/native recipes have the same names inside this directory and at the
repository root. Use [operations](docs/operations.md) for deployment and recovery
commands; preserve active transfers and manual SAB pauses.

The [private Filex portal](docs/filex.md) provides verified copies, recoverable
moves/deletes and read-only canonical browsing. Its dedicated staging roots
exclude active acquisition files and application state. The runbook covers its
separate operator login, private CA and emergency disable procedure.

The private [Usenet field guide](docs/wiki.md) is a static, source-controlled
reference with no application credentials, API integration, media listing or
control actions. Its deployment is isolated from the acquisition and copy stacks.

## Privacy, recovery and acceptance

The `Movies & TV` profile has exactly library IDs 2/3/4/5 and is denied private
library ID 1. Its files/root remain unchanged and it is excluded from home/global
search. General Plex roots never include the share root or staging. These server
checks do not prove a device starts in the restricted profile; do not browse
private content while inspecting settings.

[Scheduled encrypted backups](docs/scheduled-backups.md) run on the hosts and
cover cloud/QNAP/Plex configuration. The deployed NAS helper includes native
ownership receipts; [a fresh archive verified the published receipt](recovery/drills/native-receipt-backup-20260913.json).
The [published clean-clone drill](recovery/drills/20260911T194408Z.json) and
[checkout restore](docs/checkout-recovery.md) passed at their recorded checkpoints.
Preserve the original bound evidence and the existing recovery master. A later
checkout deletion requires a fresh readiness check; NAS-loss protection and whole
machine replacement remain separate.

[Validation](docs/validation.md) distinguishes accepted behavior, pending evidence
and user-deferred work. Run `just test` inside this directory after implementation
changes. The last recorded suite passed its functional/syntax checks, but the full
recipe still fails on two documented historical RSA keys; current-source/index
scanning passes. See [security findings](docs/security-findings.md). Do not waive
those findings or infer overall closure or merge authorization from a passing test.
