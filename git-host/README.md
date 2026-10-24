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
The household AD/Authelia rollout preserves this account and its user ID. The
HTTPS route is preparation for OIDC; registration stays closed, and existing
local authentication remains until the existing account is explicitly linked
and browser sign-in is verified. See the
[identity rollout](../docs/operations/household-identity.md).

From the repository root, run `just git-host status` to check service health.
`just git-host deploy` reconciles only this service. `just git-host bootstrap`
creates the first administrator and refuses an existing user database or receipt.
`just git-host credentials` writes the initial login into ignored
`build/git-host/admin-login.txt` with mode 0600. Change that password at first login,
then add your public SSH key in account settings. The receipt is then obsolete.
Never use the infrastructure administration key as a Git client key.

State lives under `/share/Container/home-git/data` on the NAS's local
filesystem, separate from existing media services. The deployment uses the
existing dedicated NAS identity and pinned host keys through the infrastructure
environment wrapper. It never uses the SSH agent or changes host trust.
This image stores its generated configuration at `data/custom/conf/app.ini`;
the separate mounted `config` directory is reserved but currently unused.

On October 24, 2026, deployment and the database/cache health checks passed.
Idle memory was approximately 117 MiB. Administrator creation and web login
passed, including the forced password-change redirect; the SSH listener answered.
No existing repositories were imported. Git push/clone with the user's SSH key
remains to be checked after adding that key in account settings.

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
SQLite integrity, restore ownership 1004:100, then use the recorded image and
isolated ports to test login and repository access. Restore data/config together.
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
