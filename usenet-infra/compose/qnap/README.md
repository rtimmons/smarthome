# QNAP catalog dashboard

This stack provides the authenticated OliveTin catalog dashboard, with the same
manifest-aware Python/rclone backend used by the recovery commands. It never runs
SABnzbd or Prowlarr on the NAS.

Ansible installs this directory at `/share/Container/usenet/compose/qnap` by default;
use the approved stable share paths from reconnaissance, not physical volume paths.
Create the private local login with `just dashboard-credentials` in `usenet-infra/`.
The helper requires an interactive terminal, never echoes passwords, hashes locally
using pinned Argon2id, and writes ignored `secrets/dashboard-auth.json` as mode 0600.
It refuses to overwrite an existing credential file. Copying and ownership are
managed by Ansible; no browser password setup or remote hashing service is used.

Set `QNAP_DASHBOARD_BIND_ADDRESS` deliberately to the NAS private LAN IPv4 address
or loopback. The primary URL is `http://<approved-NAS-LAN-IP>:1337`; for a loopback
binding, use the dedicated NAS SSH key to forward local port 1337 to NAS
`127.0.0.1:1337`, then open `http://127.0.0.1:1337`. Authentication remains required.
Do not configure router forwarding or expose the dashboard publicly. Deployment
preflight rejects a public/wildcard bind. The process also refuses public/wildcard
bind configuration. No actual NAS endpoint has been verified yet.

| Service | Purpose | Exposure |
|---|---|---|
| `dashboard` | OliveTin UI, catalog adapter, Python and rclone | Approved host address, TCP 1337 |
| `catalog` | Same backend through `docker compose run --rm catalog ...` | None; tools profile |
| `rclone` | Isolated read-only diagnostic daemon | Its own container loopback only |

Versions are pinned to OliveTin **3000.19.0**, rclone **1.75.1**, and Python
**3.14.7-alpine3.24**. `Dockerfile.dashboard` copies only the binary and web assets
from the official `ghcr.io/olivetin/olivetin:3000.19.0` image; it does not bring the
upstream Docker CLI or broad Fedora tooling into the runtime. The official image
manifest supports Linux **amd64 and arm64**. The combined image has been built and
run locally on arm64; the actual NAS architecture/kernel still requires preflight.
OliveTin's `-version` command deliberately exits 1 after printing its version.

The containers run with the chosen nonzero numeric UID/GID, no supplementary groups,
a read-only root filesystem, dropped capabilities, and no-new-privileges. Writable
mounts contain only cache/staging, catalog state, and dashboard runtime/history.
Versioned scripts/template and dedicated Storage Box key/known-hosts/auth files are
read-only. There is no Docker socket. The Storage Box subaccount is read-only at
the server. The `catalog:` rclone alias names that existing read-only remote;
the alias itself adds no permission boundary. The pinned rclone version does
not support a single-upstream union.

`CATALOG_STAGING_ROOT=/data/library/.staging` is inside the cache bind so final
publication is an atomic rename on one filesystem. `RCLONE_TRANSFERS`,
`RCLONE_CHECKERS`, `RCLONE_BWLIMIT`, and the free-space reserve remain configurable.
The dashboard never uses the rclone daemon to bypass the catalog implementation.

## Normal workflow

Open **Catalog** for remote/local counts and sizes, free NAS space, reserve,
running/stalled counts, failures, and item cards. Each card includes title,
category, size, and state. Use the header search for titles/categories, or the
**Entities** table's filter to inspect title, category, state, and failure text.

- **Download** appears for remote-only items; **Retry** for retryable failures.
- A downloading card has no mutation action. Open **Logs** for running status,
  transfer output and SHA-256/publication results.
- **Remove local copy** requires a checkbox stating that the canonical remote
  copy remains. A damaged existing local copy also requires removal before a
  fresh download. The adapter enforces the confirmation again on the server.
- **Refresh catalog** updates data on demand. The adapter refreshes after every
  operation and every 60 seconds while idle (every 30 seconds during a pull).
  Return to **Catalog** after the execution view; reload the browser if an
  already-open view retains an earlier snapshot.

Actions use immutable item-specific IDs and literal argument arrays. Free-form
item IDs, commands, paths, and shell inputs are never exposed in the dashboard.
Each action re-resolves the canonical manifest and validates its current state;
a stale tab cannot act on a different item. Presentation text is escaped for both
HTML and Go-template syntax. The read-only Entities list is for browsing only:
OliveTin entity positions are not used to identify destructive operations.

Pulls have a 30-day finite action timeout. Closing the browser leaves the server
process running. Timeout/container shutdown terminates the execution process
group; inherited backend locks prevent a concurrent retry from racing a surviving
transfer. Interrupted operations are reported as stalled/failed and remain
retryable; they are not reported as verified local content.

## Runtime state, health and recovery

The versioned `olivetin/config.yaml` is JSON-formatted YAML and is mounted read-only
at `/opt/usenet/olivetin/config.yaml`. The adapter merges it with generated cards
into `/data/dashboard/runtime/config.yaml`, mounted through `/config`. OliveTin
watches this primary file; upstream included config files do not reload on their
own. The runtime config contains environment placeholders, never password hashes.

Back up the dedicated dashboard auth JSON and `QNAP_DASHBOARD_STATE_DIR`, especially
`runtime/sessions.yaml` and `logs/{results,output}`. Logs retain initiator, action,
confirmation arguments, status and output, and are loaded again after restart.
The supervisor drops upstream startup debug messages (which otherwise include
interpolated authentication hashes) and redacts the known hash from other logs.

`status.json` contains `updated_at` (Unix time), `error`, and the catalog snapshot.
Metadata refresh runs in a separate process group with a 120-second default bound;
timeout kills the whole metadata process group. An authenticated stale/loading
page starts immediately even if Storage Box is unavailable. Refresh failures
retain the last snapshot, display the error, and remove all mutation actions.
The container healthcheck validates snapshot freshness/error plus OliveTin's
`/readyz`. The latter is readiness only, not proof of authentication or remote
availability. Recovery health also reads the shared status file read-only.

From this deployed directory, the fallback backend remains:

```sh
docker compose run --rm catalog catalog-list
docker compose run --rm catalog catalog-status
docker compose run --rm catalog catalog-pull <item-id>
docker compose run --rm catalog catalog-evict <item-id>
```

Prefer the repository's corresponding `just catalog-*` wrappers for routine
recovery. To update, let Ansible copy scripts/template and rebuild the images,
then inspect health and perform the generated-content test before normal use.
Do not infer NAS compatibility from the successful local image test.

## Official references (verified 2026-09-10)

- [OliveTin 3000.19.0 release](https://github.com/OliveTin/OliveTin/releases/tag/3000.19.0)
- [Local authentication](https://docs.olivetin.app/security/local.html)
- [Access control](https://docs.olivetin.app/security/acl.html)
- [Argument-vector execution](https://docs.olivetin.app/action_execution/shellvsexec.html)
- [Confirmation inputs](https://docs.olivetin.app/args/input_confirmation.html)
- [Entities and their trust boundary](https://docs.olivetin.app/entities/intro.html)
- [Action timeouts](https://docs.olivetin.app/action_customization/timeouts.html)
- [Persisted action logs](https://docs.olivetin.app/logs/saving.html)
