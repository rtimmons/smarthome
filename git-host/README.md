# NAS Git hosting

Forgejo 15.0.10 LTS runs as the isolated `home-git` Compose project on the QNAP.
It uses SQLite and one non-root container limited to 512 MiB and one CPU.
The web interface is `https://git.home.rytim.com/`, through the household LAN proxy;
numeric recovery is `http://192.168.1.66:3003/`. Git SSH connects directly to
`git-ssh.home.arpa` on port 2222. No router forwarding or public DNS is configured.
The old `http://git.home.arpa/` alias redirects to HTTPS. The certificate is
publicly trusted and requires no private root on clients. Numeric HTTP recovery
is appropriate only on the trusted LAN; use an SSH tunnel on untrusted networks.

Repository browsing requires login. Registration, Actions, packages, OpenID and
email delivery are disabled. New repositories default to private. Issues and pull
requests are available. The RSA minimum is explicitly 2048 bits for the user's
existing 1Password key; other key-size checks retain Forgejo defaults.
The administrator is `ryan`, initially with the local-only
placeholder email `ryan@home.invalid`; update it in account settings if desired.
The household AD/Authelia rollout preserves this account and its user ID.
“Sign in with authelia” uses the linked `ryantimmons` AD identity with MFA and
the `git-users` group. Explicit account linking and a fresh browser sign-in
passed; registration stays closed and local recovery login remains available.
The post-link encrypted backup restored the same user, repository, SSH key and
one OIDC link. SSH Git access continues to use the existing SSH key. See the
[identity rollout](../docs/operations/household-identity.md).

From the repository root, run `just git-host status` to check service health.
`just git-host deploy` reconciles only this service. `just git-host bootstrap`
creates the first administrator and refuses an existing user database or receipt.
`just git-host credentials` writes the initial login into ignored
`build/git-host/admin-login.txt` with mode 0600. Change that password at first login,
then add your public SSH key in account settings. The receipt is then obsolete.
Never use the infrastructure administration key as a Git client key.

State lives under `/share/forgejo/data` on the NAS's local
filesystem, separate from existing media services. The deployment uses the
existing dedicated NAS identity and pinned host keys through the infrastructure
environment wrapper. It never uses the SSH agent or changes host trust.
The named share must already exist; management and capture refuse an absent or
mismatched QTS path. Deployment resolves the QTS-local `svc-forgejo` UID/GID by name and requires
`data` and `config` to be provisioned for that identity first. Compose requires
`FORGEJO_UID` and `FORGEJO_GID`; there is no fallback to the deployment account.
The runtime has no archive mount or backup/cloud grant. Account provisioning,
ownership migration and path relocation are separate checkpoints tracked in the
[NAS migration plan](../docs/plan-nas-storage-and-access.md).

This image stores its generated configuration at `data/custom/conf/app.ini`;
the separate mounted `config` directory is reserved but currently unused.

On October 24, 2026, deployment and the database/cache health checks passed.
Idle memory was approximately 117 MiB. Administrator creation and web login
passed, including the forced password-change redirect; the SSH listener answered.
No existing repositories were imported. Git push/clone with the user's SSH key
remains to be checked after adding that key in account settings.

## Repository administration from the terminal

Use Forgejo's HTTPS API for repository creation and settings. Continue to use
Git over SSH for clone, fetch, and push. The API routes and request bodies are
in the [instance OpenAPI schema](https://git.home.rytim.com/api/swagger).

Provision a Forgejo access token for the repository owner. On Forgejo 15,
creating a personal repository with `POST /api/v1/user/repos` needs
`write:user` and `write:repository` and access to private repositories. Because
creation has no existing repository to select, use a token with **All** repository
access for that operation. Treat it as a short-lived administration credential.
For ordinary operations on existing repositories, prefer a token scoped to the
specific repositories and API operations you need. Some settings and access
changes require repository-admin privileges unavailable to repository-scoped
tokens. [Forgejo 15 token scopes](https://forgejo.org/docs/v15.0/user/authentication/token-scope/)

An operator can provision the token in **Settings → Applications** and store it in
1Password, or use `POST /api/v1/users/ryan/tokens` with the existing Forgejo local
password and the Forgejo OTP header if local MFA is enabled. This bootstrap
endpoint requires Basic authentication. The existing SSH key and Authelia
browser login do not authenticate API requests. [Forgejo API authentication](https://forgejo.org/docs/v15.0/user/api/usage/)

Run this in Bash with an authorized token. It passes the header to `curl` on
standard input and verifies the returned owner and privacy flag before pushing.

```bash
(
    set -euo pipefail
    set +x
    repo=example-infra
    read -rsp 'Forgejo API token: ' forgejo_token
    printf '\n' >&2
    printf 'Authorization: token %s\n' "$forgejo_token" |
        curl --silent --show-error --fail-with-body --max-time 30 \
          --header @- --json "{\"name\":\"$repo\",\"private\":true,\"auto_init\":false,\"default_branch\":\"main\"}" \
          https://git.home.rytim.com/api/v1/user/repos |
        jq -e --arg name "$repo" 'select(.full_name == ("ryan/" + $name) and .private == true) | .full_name'
)
```

For an existing repository, use `GET /api/v1/repos/ryan/<repo>` to inspect it
and `PATCH` on that route with the requested fields to edit settings. Read it
back after a change. After a failed or timed-out create, check the repository
with `GET` before retrying. Git push-to-create is disabled by default and is
unnecessary for this workflow. [Forgejo repository settings](https://forgejo.org/docs/v15.0/admin/config-cheat-sheet/#repository-repository)

## Encrypted off-host backups

The backup workflow uses the existing confined Hetzner Storage Box NAS-backup
account, with a separate `archives/forgejo/` directory. Archives include repository
objects, LFS/attachments, the raw SQLite database, application secrets and SSH host
keys, Compose configuration, and backup scripts. Initial bootstrap login receipts
are excluded. Encryption uses the existing NAS backup public recipient; recover
with the escrowed `qnap-admin` private identity. No private recovery key is placed
in Forgejo or in the scheduler.

`just git-host backup-deploy` installs source and the persistent QNAP cron job,
preserving unrelated jobs. It also installs a temporary once-per-minute probe;
verify `cron-probe.txt`, then run `just git-host backup-schedule` to remove only
that probe. Cron invokes `backup.sh` hourly at minute 23, skipping when the most
recent verified success is less than 23 hours old. Deployment requires explicit
approval of this backup destination before first use.

Active and persistent QNAP cron can differ. The installer saves both separately
in a private `cron-checkpoint-*` directory and reconciles only its own marked
entries in each; it refuses a detected concurrent edit before writing. Never
restore one entire cron file over the other. `just git-host backup-unschedule`
removes only the Forgejo job/probe from both files, preserving unrelated entries
and all archives. It does not stop Forgejo. Restoring the schedule can trigger
the stopped-service capture below and therefore needs an approved window.
See the [October 27 backup repair](../usenet-infra/docs/backup-repair-2026-10-27.md)
for the missing-entry diagnosis and current recovery checkpoint.

Capture currently uses a short-lived UID 0/GID 100 helper with only
`DAC_OVERRIDE`, no network, a read-only container filesystem and a read-only
Forgejo source mount. Its only persistent writable mount is the existing Forgejo
archive directory. It receives only the public encryption recipient, with no
Docker socket or private cloud/decryption credential. This bounded privileged
capture is an interim exception pending the separate `svc-forgejo-backup`
checkpoint; it does not grant backup access to `svc-forgejo`. The host scheduler
still owns lifecycle control and the existing uploader owns offsite credentials.

Only Forgejo stops during capture. The snapshot checks SQLite integrity, includes
any retained WAL/SHM files with the raw database, rejects symbolic links, and
streams directly into age encryption. A WAL can contain committed data and must
never be discarded to make a backup pass.
The service restarts before upload. Ciphertext lives in
`/share/Usenet/Backups/automatic/forgejo`, within the existing B2-selected settings
share as well, but Storage Box readback is the independently checked off-host copy.
Each Storage Box upload is downloaded and SHA-256 checked before success.
Failed uploads retain the pending archive for retry. Local retention preserves
at least seven generations and all archives younger than 90 days; off-host copies
are retained indefinitely. Monitor growth. A 100 GiB NAS reserve is enforced.

Run `just git-host backup` for a manual capture/retry and `just git-host backup-status`
for status. A failed run or success older than 36 hours is unhealthy. This is a
status command, not an email alert. Existing NAS/Plex backup schedules stay separate.
`just git-host backup-update` updates only the scripts without editing cron.
`just git-host backup-verify` independently downloads the latest successful
archive from Storage Box, decrypts with the local dedicated NAS identity, and
checks every restored file and the SQLite database. Its private restore tree and
sanitized receipt remain under ignored `build/git-host/restore-*`; this does not
test replacement-server startup. Run `just git-host-test` for offline checks.
Normal failure/signal cleanup restarts Forgejo. After a host crash or forced kill,
inspect `backup.lock` and `backup-resume-required`, verify no capture is active,
start Forgejo, then remove the stale lock/marker before retrying. Never remove an
active backup lock. Reconstruct scripts and cron from this checkout; persistent
host cron settings are also included in the native QTS settings backup.

Before upgrades, run a successful backup. For recovery, download an archive from
`nasbackup:archives/forgejo/`, decrypt with the existing NAS recovery identity,
verify every manifest SHA-256, and extract into a new private directory. Check
SQLite integrity, resolve the recovery host's `svc-forgejo` UID/GID and restore
ownership of `data` and `config` to those IDs. Export `FORGEJO_UID` and
`FORGEJO_GID` before Compose startup; old archives may record the former
1004:100 runtime and must not silently restore that shared identity. Use the
recorded image and isolated ports to test login and repository access. Restore
data/config together.
Do not downgrade a migrated database; restore its matching pre-upgrade archive.

### October 24, 2026 acceptance

The QNAP cron probe executed and its temporary entry was removed. The first
successful archive, `forgejo-20261024T180218Z.tar.age`, contains 90 entries and
5,725,764 encrypted bytes. Storage Box upload and independent ciphertext readback
passed. A separate download from Storage Box decrypted with the existing local
NAS identity; all file hashes, SQLite integrity, and one restored Git repository's
`git fsck --full` passed. Private restore evidence remains under ignored
`build/git-host/restore-1792864993276634000`. This proves archive retrieval and
file/database/object recovery, not a replacement server's startup or user login.

Both friendly aliases passed the paired resolver/gateway checks. The normal
`http://git.home.arpa/` login page advertises its canonical URL, and the health
endpoint passes through the proxy. The live RSA minimum was verified as 2048.
The existing dashboard route still returned 200, and unknown proxy hosts 404.

The pinned LTS release is supported until July 15, 2027; review upstream patch
releases for security fixes. See the [release list](https://forgejo.org/releases/)
and [Docker guide](https://forgejo.org/docs/v15.0/admin/installation/docker/).
