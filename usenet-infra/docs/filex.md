# Private file-management portal

October 8: the user verified sign-in and browsing at
**http://127.0.0.1:15213/** through the encrypted, host-pinned SSH tunnel.
Run `just usenet-filex-ui` from the repository root and leave that command running
while using Filex. Restart it after closing the terminal or restarting the Mac.
The link works on the computer running the tunnel. No domain, certificate
installation or change to host trust policy is needed.

The saved operator login is the ignored mode-0600
`secrets/filex/operator-login.txt`. A truncated local password was corrected from
the existing server credential; the account password was not rotated. Encrypted
bootstrap escrow was refreshed. See [Filex recovery](filex-recovery.md).
Staging and media remain excluded from configuration backups.

## Deployment and scope

Filex runs separately from acquisition. The browser tunnel forwards local port
15213 to the restricted cloud proxy on loopback port 5214. This HTTP endpoint
uses the same operator restrictions as private HTTPS and rejects foreign browser
origins. The network connection between computers is encrypted by SSH.
The diagnostic HTTPS listener remains at **https://10.77.0.1:5213**, bound only
to the private VPN address; the backend also listens on loopback. The NAS endpoint is reachable from the cloud only through the existing
IPsec path. Neither service is part of normal acquisition startup.

| Portal root | Access | Host boundary |
| --- | --- | --- |
| Download staging | Read/write | `/srv/usenet-filex/staging` |
| NAS staging | Read/write through dedicated SFTP | `/share/FromDrobo/FilexStaging` |
| Storage Box | Read-only kernel binds and application policy | Canonical `Movies`, `TV`, and `.acquisition-staging/filex-portal` displayed as `Scratch` |

These are deliberate staging areas. Active SAB scratch, importer-owned files,
journals, application databases, legacy media outside the canonical roots,
Docker control and administrator credentials are excluded. In particular, the
portal does **not** expose the whole `.acquisition-staging` tree: it contains
acquisition metadata that must remain private. No remote writer key is given to
Filex; it reads the existing mounted library through read-only binds.

The ordinary account is an operator with file access, not an administrator.
Private login details are in the ignored mode-0600
`secrets/filex/operator-login.txt`; do not copy them into documentation or chat.
The separate administrator account is for loopback bootstrap only. The private
proxy rejects administration, executable plugins, tokens, public sharing,
archive extraction, external protocols and unreviewed write endpoints.

The private CA certificate is `secrets/filex/ca.crt`. Validate HTTPS against that
certificate in clients that support an explicit per-request CA file. Do not
install it in the host trust store, change host trust policy, retry a trust
prompt or disable certificate checking. The service certificate
contains the private IP address and passes strict chain validation.

## Reviewed source and build

Upstream is [Filex v0.41.4](https://github.com/BRF-Tech/filex/tree/v0.41.4), MIT
licensed. Official updates come from that repository and `ghcr.io/brf-tech/filex`.
The service uses a locally built, reviewed derivative, version
`0.41.4-smarthome.1`, rather than enabling writes on the unmodified image.

The accepted immutable image is:

```
sha256:e6b89d15606318a88675070e5fc5d6e1bfc133af43ae5a77a6b16ea9655b9a2e
```

`patches/filex/safety.patch` applies without fuzz to the checksum-pinned source
archive. `scripts/filex-build.py` runs the pinned Node environment, frozen pnpm
lockfile, production dependency audit, Go driver/operation/trash/server/handler
tests and reachable-code vulnerability scan before compiling a static Linux
binary. Its shell stops on any failed step. The runtime image starts from
`scratch`, containing only that binary, CA certificates and timezone data; it
has no shell or package manager. Self-updates and executable plugins are disabled.

```sh
just usenet-filex-build
```

The build needs Go 1.27.1 on PATH and uses repository-pinned Node 24.18.0 with
pnpm 9.12.0. It produces an ignored build context and hash receipt; it does not
publish, deploy or silently change the accepted image pin. Build the context on
the existing cloud Docker host, review the resulting image identity, then update
the explicit pin in the helper, Compose definition and private/example inputs
together. Re-run acceptance after changing it. Keep the prior image and private
portal state for rollback.

The September 20 review found zero reachable Go vulnerabilities in `cmd/filex`
and zero production npm audit findings after dependency updates. The unused SMB
driver was removed because of its unresolved dependency finding. These are dated
code/dependency scan results, not a promise that future advisories cannot apply.

## Transfer and deletion behavior

Unmodified Filex had two unacceptable behaviors: cross-storage moves checked
only size before permanent deletion, and queued operations could bypass a
storage's read-only flag. The narrow backend policy patch corrects these:

- A transfer hashes the source stream and independently reads/hashes the
  destination. It checks size and source metadata before declaring success.
- A cross-storage move verifies the entire destination tree, writes a durable
  per-operation SHA-256 receipt, then moves the source into its storage's trash.
  Failed transfer, verification or receipt writes leave the source in place.
- Queued writes check read-only/enabled status both at submission and execution.
  Storage Box destinations and moves/deletes from that source are denied.
- Delete uses recoverable trash. The direct permanent-delete path and scheduled
  purges are disabled. The upstream UI's retention label is not an enabled purge
  policy. Empty-trash requests are blocked by the proxy.
- Local paths reject traversal and symbolic-link components. NAS SFTP exposes
  only `/staging`; it rejects shell commands and verifies a pinned host key.
- An interrupted running operation is marked failed after restart. It is not
  silently replayed. Retain the source and partial destination, inspect the
  visible error, then submit an explicit new copy/move. Collision handling keeps
  the old partial output rather than overwriting it.

Allowed pairs are download staging ↔ NAS staging for copy/move, and Storage Box
→ either staging area for copy. Reverse writes into Storage Box are deliberately
unavailable. Same-root staging operations remain available. Copying canonical
media does not rename or modify the source.

Transfers run in a durable server queue, independent of a browser connection.
SHA-256 receipts are private under `/srv/usenet-filex/data/transfer-verification`.
The application database records progress and errors. Reconnecting shows recent
completions and retains failures until dismissed; an old failure remains in the
durable operation history after dismissal. Source trash also remains
inside the corresponding staging root, so restores use normal Filex controls.
Do not delete receipts or trash to make a failed operation look successful.

## Isolation and resource limits

The cloud service has a dedicated `filex` identity with no login shell or
acquisition group membership. It runs non-root with all capabilities dropped,
no-new-privileges, a read-only root filesystem, 0.5 CPU, 512 MiB RAM, 128 processes,
and a 64 MiB temporary filesystem. One operation worker limits concurrency.
SFTP writes use at most 16 packets in flight; independent verification still
precedes completion or source quarantine.

The NAS container uses the existing unprivileged deployment UID/GID because
QNAP maps unknown UIDs to a denied guest ACL. This does not expose that user's
host SSH identity: SFTP uses a new dedicated key and host key, and the container
mounts only new staging and its own read-only key configuration. It has no
Docker socket, host root or broader share mount. It is limited to 0.5 CPU,
256 MiB RAM, 64 processes and a 20 MiB/s ceiling. Actual throughput depends on
the private network and storage. The TLS proxy has separate 0.25 CPU/128 MiB limits.

Metadata polling runs every 15 minutes. Large copy verification adds a second
read of the destination; account for this when scheduling bulk transfers.

## Configure, inspect and disable

Use `config/examples/filex.json` as the schema, storing real inputs only in the
ignored `secrets/filex` directory with restrictive permissions. Inputs include
separate admin/operator passwords, the dedicated NAS private key and verified
Ed25519 host pin. The helper refuses unknown fields, wrong roots/hosts/ports,
changed privileges, weak credentials and image drift.

The ignored Ansible inventory specifies `filex_enabled`, `filex_config_source`,
`filex_secrets_dir` and `cloud_vpn_filex_nas_ip`. The private certificate directory
contains `server.crt`, `server.key` and `ca.crt`. Preserve these alongside the
private configuration; never regenerate credentials as a status check.

```sh
just --justfile usenet-infra/Justfile --working-directory usenet-infra \
  filex-validate /absolute/path/to/private/inputs.json
just usenet-configure-filex
just usenet-filex-status
just usenet-filex-disable
```

The isolated playbook prepares the dedicated NAS endpoint, then the cloud
portal. It requires the reviewed image already installed, checks mount and
configuration boundaries, enables only the narrow VPN firewall extension,
reconciles exactly three storage rows and the operator account, and checks
anonymous/admin denial plus HTTPS. Bootstrap is repeatable and refuses drift
before rewriting an existing storage. Failure stops the portal and preserves
its state. No acquisition, Plex or NAS-host restart is part of deployment.

Disable stops only `usenet-filex.service`, including its private TLS proxy. It
preserves state, staging and receipts. The NAS staging endpoint remains isolated
and available; to stop it as well, use only the `usenet-filex-sftp` Compose project
in `/share/Container/usenet/filex-sftp` through the repository's dedicated NAS
connection. Never use `down -v`, delete staging, or operate on the normal cloud
or NAS Compose projects as portal cleanup.

An image rollback needs compatible preserved portal state because database
migrations may not reverse. Stop the portal, preserve the current database and
receipts, restore the reviewed portal-only state/pin, and repeat acceptance.
There is no automatic database rollback.

Portal state is outside the existing cloud backup allowlist. This deployment
does not claim backup coverage or alter the deferred restore work.

## Acceptance evidence

Sanitized outcomes belong in `recovery/drills/filex-pilot-20260919.json` and the
current `../plan.md`. Exact credentials, operational names, hashes, API responses
and transfer receipts stay in private ignored evidence. Use synthetic fixtures
for browse/sort/download, restore, transfer, interruption and confinement checks.
Live coexistence passed during both native SAB postprocessing and importer
source hashing. The running image matches the reviewed patch/build receipt, and
14 durable transfer verification receipts were captured. These checks do not
waive the separately documented acquisition health warnings.
