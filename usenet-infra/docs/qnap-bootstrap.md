# QNAP bootstrap

Status as of 2026-09-10: the user provided
[the local QNAP administration URL](https://rynapqnap.local/cgi-bin/) and opened
a trusted Firefox session signed in as an existing administrator. The in-app
browser rejected the NAS certificate; that did not verify its trust. Read-only
UI inspection confirms a **TS-451D2**, **QTS 5.2.10.3577**, **Celeron J4025
(2 cores/2 threads)**, and **4 GB RAM**. Container Station and HybridMount icons
are present. SSH reconnaissance verifies Container Station 3.1.2.1742,
Docker 27.1.2-qnap8, Compose 2.29.1-qnap2, and HybridMount 1.17.5691
(QPKG `CacheMount`). The dashboard runs and authenticated login works; dashboard
download/reconnect/local-eviction checks passed. CLI parity, restart persistence,
and isolated configuration restoration also passed. External reachability was
unverified at that checkpoint; the [September 14 probe](../recovery/drills/nas-exposure-20260914.json)
later passed dated direct TCP/1337 acceptance, with alternate static
forwarding/proxy paths remaining unaudited.

SSH now works on port 22 through the dedicated public key; Telnet remains
disabled. Initially five users were observed, with no dedicated deployment
account. The user approved
and created `usenet-deploy` from the prepared form with administrator
membership required by QTS SSH. Its enabled account row and description,
"Dedicated Usenet catalog deployment", were independently verified.
QTS login as `usenet-deploy` and the first dedicated-key SSH login both
succeeded. NAS deployment has started. HybridMount's optional wizard was
inspected and the route was not adopted; no remote mount was created.

The dedicated workstation `qnap-admin` keypair exists. Its public-key
fingerprint is `SHA256:0+i6AsBSNhJGljv/EI2Yt3uLnRZeNroT5b5ObX/WYB8`.
The user installed its public key through QTS; the displayed MD5 fingerprint
matches the local key: `2d:be:d6:24:51:cb:0a:a6:e3:a0:c2:a3:1c:0e:e0:00`.
These identify the deployment login key, not the NAS SSH host key.

The user explicitly authorized **trust on first use** for the NAS's 3072-bit
RSA host key, `SHA256:jXVysXlhzn80Tk2BYg8CGNkfMCqjCEpyu0PyyHJX5RA`.
It is pinned in the ignored known-hosts file with mode `0600`, and SSH uses
strict checking. This is authorized first-use trust, not independent host-key
verification. The first SSH login used only the repository's `qnap-admin`
identity, with no agent or password fallback, to
`usenet-deploy@rynapqnap.local` on port 22.

Live readback reports UID `1004` (`usenet-deploy`), primary GID `100`
(`everyone`), NAS supplementary groups `0` (`administrators`) and `100`,
Linux `5.10.60-qnap`, and `x86_64`. The three QNAP SSH connection fields in
ignored `.env` are set and the file remains mode `0600`. Read-only discovery
found about 2 GB available RAM, overlay2 storage, memory/swap cgroup support,
and only the tiny existing `iperf3-1` container. The selected LAN interface is
`eth0`, `192.168.1.66/24`; port 1337 was unused at preflight.

The new QTS `Usenet` shared folder and application directory are prepared,
protected inventory/environment settings are populated, and the user-created
Argon2id dashboard credential file was verified with mode `0600`. Deployment
started through `just usenet-configure-qnap`; authenticated dashboard login
works at `http://192.168.1.66:1337`. Both services run as 1004:100 with a
read-only root filesystem, all capabilities dropped, no new privileges, no
privileged mode, and no Docker socket. The dashboard process has only group
100. The listener is confined to 192.168.1.66:1337, with no global IPv6
addresses observed. The official fixture's dashboard download, browser reconnection during transfer,
and confirmed local eviction passed. CLI parity, restart persistence, and isolated configuration restoration also
passed. The [September 14 external probe](../recovery/drills/nas-exposure-20260914.json)
later passed direct TCP/1337 acceptance; alternate static forwarding/proxy paths
remain unaudited.

The first build failed because Docker/Buildx tried to create client state in
Container Station's unwritable package home. Helpers now scope that state to
`/share/Container/usenet/state/docker-client`, owner `1004:100`, mode `0700`,
using explicit Docker and Buildx configuration paths. Scoped Compose validation
and default-driver Buildx inspection passed. No stack service started during
the failed attempt or the scoped-state probe. Subsequent live checks also
identified an inherited QNAP ACL on the copied launcher and two rclone path
issues. The launcher now uses a fresh inode; the one-upstream catalog uses a
supported alias and preserves home-relative SFTP paths. Server-side read-only
enforcement remains the credential boundary; transfer acceptance follows the
updated deployment.

Do not reboot the NAS, alter unrelated containers, or assume a model-specific
physical path. Complete discovery before deploying the cache stack.

## Supported one-time access setup

Use a dedicated NAS account with SSH and Container Station/Docker access. QTS
5.2 and QuTS hero h5.3 document that SSH login requires administrator membership;
a non-administrator SSH account is therefore not assumed. Do not use the
built-in `admin` account or UID/GID zero for this stack. Sources:
[QTS SSH setup](https://docs.qnap.com/operating-system/qts/5.2.x/en-us/enabling-ssh-on-the-nas-61C229CD.html),
[QuTS hero SSH setup](https://docs.qnap.com/operating-system/quts-hero/5.3.x/en-us/enabling-ssh-on-the-nas-61C229CD.html).

The human bootstrap is:

1. In QTS/QuTS hero, create or select the dedicated deployment account and grant
   only the host privileges required by this firmware for SSH/Docker access.
2. Log in to the NAS web UI as that account. In current QTS, open the username
   menu, **Login and Security**, then **SSH Keys**. On older 5.0 releases the
   equivalent tab is under **Options**. Choose **Add** / **Add an SSH Public
   Key**, paste only `usenet-infra/secrets/ssh/qnap-admin.pub`, and give it a
   recognizable name. Do not copy the private key onto the NAS. If the UI differs,
   use the installed firmware's Help rather than editing firmware-owned files.
3. In **Control Panel > Network & File Services > Telnet/SSH**, enable SSH on
   the approved LAN interface/port if necessary. Keep Telnet disabled and do not
   create router forwarding or a public NAS exposure.
4. Record the exact `user@LAN-host` and port. Independently verify the NAS SSH
   fingerprint in an already trusted local/admin session before pinning it in
   ignored `ansible/files/secrets/qnap-known-hosts`. A network key scan alone is
   not verification. For this bootstrap the user explicitly authorized
   first-use trust of the exact RSA fingerprint recorded above; record that
   basis without calling it independently verified. Never accept a changed
   host key blindly.
5. Confirm that a fresh login using only `qnap-admin`, `IdentitiesOnly=yes`, and
   that pinned host-key file succeeds. Record `id -u` and `id -g`, both nonzero.

The account-specific SSH Keys UI is documented in the
[QTS task-bar guide](https://docs.qnap.com/operating-system/qts/5.2.x/en-us/task-bar-33FA3D49.html)
and demonstrated in QNAP's
[QTS/QuTS hero 5.0 SSH-key walkthrough](https://www.qnap.com/s3/qutube/slides/NBsPPmmXrAU.pdf).
Exact labels must be checked against the installed firmware. The Storage Box
`qnap-reader` key is a different identity and must not be used for NAS login.

The default deployment uses the dedicated account's numeric UID and primary
GID for file ownership and containers. Even if that SSH account belongs to the
NAS administrators group, the containers receive only the configured UID/GID,
no host supplementary groups, no Docker socket, and no added capabilities.
Creating a separate runtime owner would require an explicit ownership workflow
and is not currently the default.

## Reconnaissance record

Record the following in the ignored deployment inventory/notes, then summarize
non-secret acceptance evidence in [validation.md](validation.md):

| Fact | Current result |
| --- | --- |
| Local administration URL | `https://rynapqnap.local/cgi-bin/`; user-opened trusted Firefox session; login as `usenet-deploy` verified |
| Model and CPU architecture | TS-451D2; Celeron J4025, 2 cores/2 threads; 4 GB RAM with about 2 GB available at reconnaissance; runtime architecture `x86_64` verified by SSH |
| QTS or QuTS hero, firmware and kernel | QTS 5.2.10.3577, build 20260731; Linux 5.10.60-qnap |
| Kernel page size | 4096 bytes, verified through the running image; base NAS lacks `getconf` |
| Container Station, Docker Engine, Compose V2 versions | Container Station 3.1.2.1742; Docker 27.1.2-qnap8; Compose 2.29.1-qnap2; overlay2 and memory/swap cgroups supported |
| Existing containers and private port | Only `iperf3-1`, about 1.16 MiB RAM and 0% CPU at observation; `eth0` 192.168.1.66/24 is the default LAN interface, port 1337 unused before deployment. Existing `iperf3-1` has remained running since 2026-08-18 with restart count 0 |
| Stable deployment and cache shares, free bytes | `/share/Container/usenet` created UID 1004/GID 100, mode 0750; Container volume about 42 GB free. Exact cache root `/share/Usenet/usenet-cache`; share on GPvQNAP volume resolves to `/share/CACHEDEV2_DATA/Usenet`, about 1.37 TB free and 69% used; 100 GiB cache free-space floor configured |
| Dedicated account, numeric UID/GID, SSH port and host-trust basis | `usenet-deploy@rynapqnap.local:22` dedicated-key login passed; UID 1004, primary GID 100, NAS supplementary groups 0/100. Exact RSA host fingerprint above pinned under user-authorized first-use trust; not independently verified. Telnet disabled |
| Dashboard private address, authentication and SSH/private access path | `http://192.168.1.66:1337`; authenticated login passed, exact private listener verified. Argon2id credential file privately created and verified mode 0600. Dashboard/CLI transfer and eviction, restart persistence, and isolated restore passed. September 14 direct external TCP/1337 acceptance passed; alternate static forwarding/proxy paths remain unaudited |
| HybridMount version, modes, license availability and cache support | HybridMount 1.17.5691 (QPKG `CacheMount`); File Cloud Gateway and WebDAV Cloud/Server available in inspected wizard; free-license availability unverified. Password-only WebDAV form observed, closed without credentials/mount/cache creation; route not adopted |

From the repository root, `just usenet-qnap-recon` reads NAS versions, resource
headroom, container metadata, network details, and share capacity through the
dedicated pinned SSH connection; it does not inspect personal files or mutate
the NAS. From `usenet-infra/`, use `just qnap-recon`. Noninteractive QNAP SSH
does not include Docker on `PATH`: repository helpers discover Container
Station's actual Docker executable dynamically and invoke its absolute path.
Do not change the NAS host `PATH` to compensate. The Ansible preflight uses the
same discovery approach. Preserve sanitized metadata output for acceptance.
Docker client state is likewise scoped to the application's private state
directory through `DOCKER_CONFIG`, `BUILDX_CONFIG`, and Docker's `--config`.
Recovery helpers derive that directory from the standard Compose path;
`QNAP_DOCKER_CONFIG_DIR` is an optional override for a custom deployment path.

Container Station's capabilities vary by NAS/firmware. Verify Compose V2 and
smoke-test the exact pinned rclone, catalog-tools, and OliveTin images on this
NAS before rollout. CPU architecture alone does not prove image compatibility;
kernel page size and runtime behavior also matter. Do not upgrade firmware or
reboot to make an image pass as part of this bootstrap.

## Stable paths and ownership

The QTS shared-folder UI created `Usenet` on the GPvQNAP volume, with
`usenet-deploy` granted read/write, every other listed user set to No Access,
and guest access denied. The stable share is `/share/Usenet`; its observed
physical target is `/share/CACHEDEV2_DATA/Usenet`. Use the stable share in
configuration. The application directory `/share/Container/usenet` was created
with owner `1004:100` and mode `0750`. Inventory uses those numeric IDs and a
100 GiB cache free-space floor. Subdirectories are populated by deployment:

```text
/share/Container/usenet/
├── compose/qnap/
├── scripts/
├── secrets/storagebox/
└── state/

/share/Usenet/usenet-cache/
└── .staging/
```

Precreate `/share/Container/usenet` so deployment need not make the broader
`/share/Container` root writable. Use stable `/share/<ShareName>` paths, never
hard-coded `CACHEDEV*`, `ZFS*`, `.qpkg`, or Container Station's private directory.
Staging stays below the cache root so publication is a same-filesystem rename.

Populate ignored `ansible/inventory.yml` using the supplied example, including
the dedicated SSH key and verified NAS known-hosts file, actual numeric IDs and
share paths. Populate workstation `.env` from `.env.example` for the recovery
commands. Never put passwords or private-key contents in either example file.

The current deployment preflight accepts `x86_64` or `aarch64` and requires
Compose V2 2.18 or newer; it does not install packages into the NAS base OS.
Unsupported NAS architectures remain a compatibility stop until a verified
pinned build exists. Do not override this gate by guessing a container platform.

## Read-only Storage Box identity

Terraform has created the `catalog`-rooted, server-enforced read-only subaccount.
The writer installed its public key and a live read/overwrite/delete sentinel
test already passed from the cloud. Repeat the proof from the NAS after
bootstrap; the earlier result does not prove this NAS has the correct key.

Deploy only `qnap-reader` to the NAS, mode `0600`, with its independently verified
Storage Box `known_hosts` file. The subaccount home requires its own
`.ssh/authorized_keys`, installed through the main writer identity, as documented
in the [Storage Box overview](https://docs.hetzner.com/storage/storage-box/general/).
Pin the hostname, not the changeable IP. The NAS must never receive the main
Storage Box password or writer key.

## Deployment and private dashboard access

`just configure-qnap` from `usenet-infra/` runs the repository's preflight and
QNAP application roles. Use the checked-in Compose and OliveTin configuration,
ignored runtime authentication material, and pinned image versions. Follow the
[QNAP Compose runbook](../compose/qnap/README.md) for the exact build, startup,
private address, and login-secret setup. Do not use a sample credential.
The repository-root equivalent, `just usenet-configure-qnap`, is currently
used against this NAS. Runtime security and authenticated login are verified;
the acceptance matrix records completed transfer/recovery checks and the
dated direct external TCP/1337 acceptance.

Create the login privately with `just dashboard-credentials`; the helper prompts
without echo, saves an Argon2id hash in ignored `secrets/dashboard-auth.json`
with mode `0600`, and refuses to overwrite an existing file. Set
`qnap_dashboard_auth_source` to that actual file in ignored inventory. Do not
paste the password or hash into chat. Choose `qnap_dashboard_bind_address`
explicitly: the Ansible default is intentionally unset, and only loopback or
an RFC1918 IPv4 address is accepted. The default unprivileged port is `1337`.
For this deployment the user has already created the private credential file;
inventory selects `192.168.1.66:1337` for direct LAN HTTP. No new credential
creation step is pending. Authenticated login and anonymous dashboard/entity/
history/action-binding denial passed. The September 14 external audit recorded
three public TCP/1337 timeouts with a successful same-WAN NAS TCP control, no
dashboard UPnP mapping and no global NAS IPv6. This is dated direct-port evidence;
alternate static forwarding or proxy paths were not audited. Private LAN binding
alone does not prove Internet isolation.

Use CLI ownership for this Compose project. Container Station may inspect it,
but do not import/recreate the same project in the GUI as well. If GUI ownership
is deliberately selected later, upload a fully rendered Compose file and use
**Recreate Application** consistently for future changes.

Authentication is required even on the LAN. Keep the dashboard on the explicit
private bind address, or loopback through an approved private access path. The
implemented service speaks HTTP; the default secure access path is loopback
through the SSH tunnel documented in the Compose runbook. No TLS proxy or public
TLS service is deployed. An existing trusted private TLS access path can be used
if available; direct LAN HTTP remains an explicit operator choice. Do not publish
the dashboard through router forwarding, myQNAPcloud public sharing, or a public proxy.
The dashboard container must have no Docker socket or writer credential.

For SSH access to the currently selected LAN bind and port, open a workstation
tunnel from `usenet-infra/` after deployment succeeds. `.env` already selects
the dedicated identity and strictly pinned NAS host:

```sh
set -a
. ./.env
set +a
ssh -N -T -o BatchMode=yes -o IdentitiesOnly=yes \
  -o StrictHostKeyChecking=yes -o ExitOnForwardFailure=yes \
  -i "$QNAP_SSH_KEY" -o "UserKnownHostsFile=$QNAP_SSH_KNOWN_HOSTS" \
  -L 127.0.0.1:1337:192.168.1.66:1337 "$QNAP_SSH_TARGET"
```

Then open [the local dashboard](http://127.0.0.1:1337) and sign in. Keep the
tunnel terminal open. If deployment is deliberately changed to a loopback bind,
change the forwarding destination to `127.0.0.1:1337`. Use the discovered SSH
port if it differs from 22, and adjust forwarding if the approved dashboard
address or port changes.
The example URL is the access pattern, not evidence of a deployed NAS service.

## Optional HybridMount experiment

The bounded UI inspection was completed on 2026-09-10 in the existing signed-in
Firefox session. The introductory dialog was dismissed and enhancement
telemetry declined. **Create File Cloud Gateway → WebDAV Cloud/Server** was
available. The wizard showed **Server URL**, **Account**, **Password**,
connection name, all-folders destination, conflict-check/rename upload policy,
proxy settings, and scheduled file-list options. No SSH-key option was present.

The wizard was closed without entering remote credentials, saving a connection,
or allocating a cache. The current reader uses key-only SFTP; no WebDAV password
or write-capable credential was provisioned for this optional path. Hetzner's
documented read-only GET-only restriction does not provide reliable WebDAV
listing, so the route was **not adopted**. This is a design decision after UI
inspection, not an observed authentication or mount failure. Browsing state
icons, reserved-cache behavior, and write denial were not tested. The installed
HybridMount version is 1.17.5691, verified from QPKG `CacheMount`.

The following research and procedure are retained only for a deliberate future
revisit, limited to 20 minutes. HybridMount is not a deployment dependency.

QNAP's [HybridMount 1.11+ quick-start guide](https://www.qnap.com/en-us/how-to/tutorial/article/hybridmount-quick-start-guide)
lists generic **WebDAV Cloud/Server**, File Cloud Gateway caching, a minimum
20 GB cache per gateway, and two free third-party gateway connections. Confirm
all of these on the installed version and model before allocating any cache.
A Network Drive Mount is not an equivalent test of File Cloud Gateway caching.
Hetzner warns that most clients cannot mount its read-only WebDAV endpoint
because that mode allows only HTTP GET. That makes compatibility uncertain,
not permission to relax read-only mode. See
[Hetzner WebDAV limitations](https://docs.hetzner.com/storage/storage-box/access/access-webdav/).

The documented UI starts at **Create Remote Mount**, then **File Cloud Gateway**,
and the generic **WebDAV Cloud/Server** provider. Use the subaccount's assigned
HTTPS hostname and its username/password; an SSH private key cannot
authenticate this WebDAV connection. The installed wizard's actual labels
were confirmed above.
The [detailed QNAP tutorial](https://www.qnap.com/en-us/how-to/tutorial/article/hybridmount)
then documents connection name, selected remote folders, upload policy,
optional file-list refresh, storage pool/capacity, read/write/reserved cache
allocation, and automatic-download behavior. Select disabled automatic download
for this bounded experiment. Its documented upload policies both describe
writing; neither proves support for a server-enforced read-only gateway.
No official source found in the bounded check guarantees that compatibility.
Listing/authentication failure with the unchanged read-only subaccount is an
acceptable unsupported result if a future connection test is authorized. No
such failure was produced by this UI-only inspection.

1. Confirm the NAS offers File Cloud Gateway with generic WebDAV, a free license,
   and sufficient unused cache space. If not, record **unsupported** and stop.
2. Use only the existing read-only subaccount at its HTTPS hostname. WebDAV
   uses that subaccount's password, not its SSH key; enter it privately through
   the protected runtime setup. If WebDAV is disabled on the Box, review the
   protocol-setting change explicitly before enabling it; do not grant writes.
3. Choose the smallest supported dedicated test cache, disable automatic
   download, and browse/read only the writer-created disposable fixture.
4. Observe cloud-only, downloading, locally cached, and reserved-cache behavior.
   QNAP documents **Always Keep in Reserved Cache** for eligible mounted items;
   verify whether this installed version actually offers it. See
   [QNAP reserved-cache behavior](https://www.qnap.com/en-ca/how-to/faq/article/how-do-i-configure-the-maximum-write-cache-size-for-a-hybridmount-file-cloud-gateway).
5. Attempt overwrite and delete only against the disposable sentinel. Require
   remote rejection and compare the original SHA-256 using the writer. Do not
   test a real catalog object. Do not mistake a cached local error for proof
   of remote rejection.
6. Record model/versions, mount mode, errors, license/cache allocation, observed
   icons, hash/write-denial results, and elapsed time here. Disable the test
   mount afterward; remove its test-only cache only after identifying precisely
   what will be removed.

Stop if mounting requires writes, integrity/failure state is unclear, or the
experiment cannot retain the manifest-aware workflow. Retain OliveTin and direct
SFTP; never substitute two-way sync, a writer credential, or raw-copy actions.
WebDAV does not reliably report Storage Box free space, so SFTP health checks
remain authoritative for capacity.

Experiment result: **UI inspected; not adopted; no credentials entered, mount
created, or cache allocated. Live browsing/cache/write-denial behavior untested.**

## Acceptance gate

Use [validation.md](validation.md) for the complete acceptance record. The NAS
must prove image startup, authentication, private exposure, direct verified
pull, visible running/failure state, confirmed local-only eviction, recovery
CLI parity, and read-only remote access before handoff. Check representative
large-file throughput and free-space reserve before tuning concurrency.

Rclone retries completed matching files, but cannot resume the interrupted bytes
of one large file. Preserve hidden staging, retry the catalog action, and never
add `--inplace` or expose staging as a complete local item.
