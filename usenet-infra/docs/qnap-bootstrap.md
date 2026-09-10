# QNAP bootstrap

Do not deploy the cache stack until this reconnaissance is complete. Do not
reboot the NAS, alter unrelated containers, or assume a model-specific physical
path.

## Manual reconnaissance

From the QNAP UI, record:

- exact model and CPU architecture;
- QTS versus QuTS hero and OS version;
- Container Station version;
- LAN hostname/address;
- existing shares, free capacity, and the intended cache share; and
- the non-administrator account that will own this stack.

Install or update Container Station from App Center if needed. Temporarily enable
SSH, then run these read-only commands with the chosen account:

```sh
uname -m
getconf PAGESIZE
id
docker version
docker compose version
docker info
df -h /share/REPLACE_WITH_LOCAL_LIBRARY
docker run --rm rclone/rclone:1.75.1 version
```

Container Station 3 uses Compose V2, but the exact engine/plugin and Compose
feature set vary by NAS release. Older 32-bit ARM QNAP models with 32 KiB pages
can reject otherwise architecture-matched images; the image smoke test is the
acceptance gate.

## One-time folders and identity

Use stable shared-folder paths, for example:

```text
/share/Container/usenet/
├── compose/qnap/
├── secrets/storagebox/
└── state/

/share/<LOCAL_LIBRARY>/usenet-cache/
└── .staging/
```

Create a dedicated non-administrator NAS user, install the generated
`qnap-admin.pub` key for it, and give it read/write permission only to these local
paths. Precreate `/share/Container/usenet` through the supported QNAP UI so the
user never needs write access to the broader `/share/Container` root. If QTS
requires the UI to create the library share, that is the one unavoidable GUI
step. Record the numeric UID/GID. Do not use
`CACHEDEV*`, `ZFS*`, `.qpkg`, or Container Station's private application path.
Staging must stay under the cache root so the final publish is a same-filesystem
atomic rename.

## Read-only Storage Box identity

Terraform creates a subaccount rooted at `catalog` with server-enforced read-only
access. Place only that subaccount's private key on the QNAP with mode `0600`.
Using the Storage Box main account, install the matching public key in the
subaccount home `.ssh/authorized_keys` before testing it.

Fetch the host key for the Storage Box hostname, compare the fingerprint with an
independent value from Hetzner, then save the verified line to the QNAP
`known_hosts` file. Never disable verification and never pin the changeable IP.

The QNAP must not receive the main Storage Box password or writer private key.

## Deploy

Copy the repository-managed `compose/qnap` directory and catalog scripts into
the stable project directory using `ansible/qnap.yml`. Copy `.env.example` to
`.env`, set absolute share paths and numeric UID/GID, then validate:

```sh
cd /share/Container/usenet/compose/qnap
docker compose config
docker compose build --pull catalog
docker compose pull
docker compose up -d rclone
docker compose ps
docker compose run --rm catalog list
```

Use CLI ownership for this project. Container Station may inspect it, but do not
also import and recreate the same project in the GUI. If GUI ownership is chosen
instead, upload only a fully rendered Compose file and apply every future change
through **Recreate Application**; do not mix lifecycle owners.

## Acceptance checks

With a disposable sentinel created by the writer account, prove that the QNAP
identity can read it but cannot overwrite, rename, or delete it. Confirm the
writer still sees the same SHA-256 afterward. Also confirm `rclone about catalog:`
and remote SHA-256 commands work on port 23. If remote SHA-256 is unavailable,
local verification against the ingestion-generated manifest remains mandatory.

Rclone safely retries already completed files but cannot resume the interrupted
bytes of a single large file. It uses temporary partial files and renames on
completion; never add `--inplace`.
