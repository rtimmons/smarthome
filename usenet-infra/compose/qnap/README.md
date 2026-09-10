# QNAP rclone runtime

This Compose project runs the official `rclone/rclone:1.75.1` image as an
optional resident diagnostic runtime and builds a hardened one-shot catalog
tools image. The tools image starts with the exact same official rclone binary
and adds Python 3 for the repository's dependency-free catalog scripts. Neither
service publishes or exposes a port. The resident process listens only on the
container's loopback address, so its remote-control API is not reachable from
the host or LAN.

`CATALOG_REMOTE` is fixed to the root of the `catalog:` rclone union, whose only
upstream is marked read only. The QNAP launcher also refuses to run the
cloud-only `catalog-promote` command. Those are useful defenses in depth, but
they are not the security boundary: the Storage Box account configured here
must itself be a Hetzner read-only subaccount. The underlying `storagebox:`
remote remains addressable by a process inside the container, so client
configuration alone cannot protect canonical content.

## NAS reconnaissance

Record the exact model, QTS or QuTS hero version, and Container Station version
from their About screens. With SSH temporarily enabled, also record:

```sh
uname -m
getconf PAGESIZE
id REPLACE_WITH_DEDICATED_USER
docker version
docker compose version
docker info
df -h /share/REPLACE_WITH_LOCAL_LIBRARY
```

Confirm that `docker compose` is available; do not assume the legacy
`docker-compose` command exists. QNAP warns that several older 32-bit ARM models
use a 32 KiB memory page size that can make otherwise architecture-matched
images fail. Test the exact upstream image and build the Python tools image
before configuring credentials:

```sh
docker run --rm rclone/rclone:1.75.1 version
cd /share/Container/usenet/repository/usenet-infra/compose/qnap
docker build --pull -f Dockerfile.catalog \
  -t usenet-catalog-tools:rclone-1.75.1-python-3.14.7 .
docker run --rm --entrypoint sh \
  usenet-catalog-tools:rclone-1.75.1-python-3.14.7 \
  -c 'python3 --version && rclone version'
```

The tools Dockerfile uses the exact Docker Official Image tag
`python:3.14.7-alpine3.24` and copies `/usr/local/bin/rclone` from
`rclone/rclone:1.75.1`; its build fails if that binary does not report exactly
`1.75.1`. Both upstream images publish multiple architectures, but an image tag
does not prove compatibility with a particular QNAP kernel or memory page size.
Do not force a `platform:` value until the NAS architecture is known. A
successful pull, build, and version command are the compatibility checks that
matter. Pin platform-specific image digests after the NAS architecture is
known if byte-for-byte image immutability is required.

## Bootstrap

Keep the repository in a stable shared-folder path, for example
`/share/Container/usenet/repository`, with this project at
`usenet-infra/compose/qnap`. The catalog build context is this QNAP directory,
so `Dockerfile.catalog` and `catalog-run` remain available to Compose. Set
`QNAP_CATALOG_SCRIPTS_DIR` to the repository's absolute
`usenet-infra/scripts` path; it is mounted read-only.

Create the cache and state directories on their intended shares, then make them
writable by the dedicated numeric UID/GID. The host cache directory is mounted
at `/data/library`. Transfer staging lives at `/data/library/.staging` inside
that same bind mount, not under the separately mounted state share. This is
intentional: `catalog-pull` publishes with `os.replace`, which requires staging
and the final library to share a filesystem and mount. Keep the private key
outside the repository, owned by the dedicated user and mode `0600`.

Fetch the Storage Box host key, compare its fingerprint with Hetzner's
independently published fingerprint or the value shown in the Hetzner Console,
and only then save the matching public key line in the configured `known_hosts`
file. Do not disable host-key checking and do not use a Storage Box IP address;
Hetzner documents that the address may change.

Copy `.env.example` to `.env` and replace every placeholder. The `.env` file
contains no passwords or private-key material, but it is ignored because it is
host-specific. Validate before starting:

```sh
cd /share/Container/usenet/repository/usenet-infra/compose/qnap
docker compose config
docker compose pull rclone
docker compose build --pull catalog
docker compose up -d rclone
docker compose ps
docker compose exec -T rclone rclone version
docker compose exec -T rclone rclone lsd catalog:
docker compose exec -T rclone rclone backend features storagebox:
```

Inspect the final command's `Hashes` result to verify that the read-only
subaccount detected `SHA-256` through Hetzner's port 23 restricted shell. If
that capability is not available, catalog integrity still comes from the
SHA-256 manifest created at ingestion and verified against local bytes; do not
mistake a matching size for checksum verification.

Normal catalog operations use a fresh one-shot container. They do not depend on
the resident `rclone` service and accept the same arguments as the checked-in
wrappers:

```sh
docker compose run --rm catalog catalog-list
docker compose run --rm catalog catalog-list --json
docker compose run --rm catalog catalog-status
docker compose run --rm catalog catalog-status --json
docker compose run --rm catalog catalog-pull "some-catalog-item-id"
docker compose run --rm catalog catalog-evict "some-catalog-item-id"
docker compose run --rm catalog healthcheck
docker compose run --rm catalog healthcheck --json
```

The `catalog` service belongs to the `tools` profile so a normal
`docker compose up -d` does not leave it running; explicitly targeting it with
`docker compose run` enables it for that invocation. The scripts bind is read
only, the root filesystem is read only, and only `/data/library`, `/data/state`,
and the private `/tmp` tmpfs are writable. The SSH private key and verified
`known_hosts` file are read-only binds. The launcher permits only QNAP-safe
list, status, pull, evict, and health-check operations.

Use `catalog:` only as a source. `catalog-pull` downloads into
`/data/library/.staging`, validates every file against the catalog's SHA-256
manifest, and renames it into `/data/library` only after validation. Rclone
safely retries completed files, but it does not resume the interrupted bytes of
one partially downloaded file. Do not pass `--inplace`.

## Choose one lifecycle owner

CLI ownership is recommended: keep this directory as the source of truth and
perform lifecycle operations only with `docker compose` from this project
directory. Container Station can still display and inspect the resulting
container.

If Container Station GUI ownership is required, keep the full repository at its
stable shared-folder path so the local build files and absolute scripts bind
remain available. First render the project with
`docker compose --env-file .env config`, then paste or upload that resolved YAML
as an application named `usenet-cache`. Verify that the Container Station
release can build the local `catalog` image from the resolved context before
choosing this mode. Container Station does not document its internal project
path as a stable interface, and it does not watch this source file. Apply every
later change through **Recreate Application** using a newly rendered file. Do
not also run CLI lifecycle commands for the GUI-owned project.

All host bind sources are deliberately absolute `/share/...` paths. Relative
bind sources in a GUI-imported application resolve under Container Station's
managed project directory, which is not a suitable or stable location for
configuration, state, secrets, or cached media.
