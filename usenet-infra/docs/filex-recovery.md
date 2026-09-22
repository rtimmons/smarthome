# Filex encrypted recovery

Filex recovery capture is deployed as of September 22, 2026. Run
`just configure-filex-backups` inside `usenet-infra` to install the bounded
capture helper and timer. It does not restart Filex or media services.

The root-owned hourly timer captures daily, with retry while operations are
unfinished. It includes `/etc/usenet-filex`, the Filex SQLite database,
transfer-verification receipts, its systemd service and VPN network definition.
SQLite uses an online, integrity-checked snapshot; changing configuration or
unfinished Filex operations refuse capture. Staging files, recoverable trash,
media and logs are excluded.

Only ciphertext and a checksum receipt are published beneath
`/srv/usenet/config/filex-recovery`. Encryption uses the existing cloud
administrator recipient. The ordinary cloud backup includes this directory and
rejects a current Filex bundle older than 36 hours or with a mismatched digest.
The capture timer runs independently of SAB; the outer cloud backup still waits
for an idle or fully paused queue with no post-processing.

`latest.tar.age` contains current portal state. A separately verified
`bootstrap.tar.age` escrows the operator's CA private key, original connection
keys and login material, encrypted locally before upload. The original private
key files and immutable SOPS snapshot were not replaced. Refresh this escrow
after intentionally rotating bootstrap material; daily server snapshots cannot
capture a CA private key that exists only on the operator Mac.

The NAS configuration archive now includes Filex SFTP configuration and its
server identity under `filex-sftp`. A deployed marker requires all connection
configuration and keys to be present. NAS staging/media remain excluded.

## Restore procedure

1. Independently decrypt the chosen outer cloud archive into an absent private
   directory using `backup-restore`. Verify its manifest and the nested Filex
   bundle checksum against `latest.json`.
2. Run the same `backup-restore` command on the nested `latest.tar.age`, using
   another absent directory and the existing cloud administrator identity. The
   `filex-config` scope checks its own required files and fixed path allowlist.
   Restore the bootstrap bundle separately when operator keys are needed.
3. Restore the NAS archive with `backup-qnap-restore` into a separate directory.
   Preserve current share paths and inspect existing host identities before
   installing its `filex-sftp` configuration. Do not regenerate host keys during
   ordinary recovery.
4. On a replacement or stopped Filex instance, install configuration and the
   standalone database with restrictive modes and ownership mapped to the new
   host’s `filex` account; do not blindly reuse an old numeric UID.
   Rebuild the reviewed image from source, restore service/mount/network
   dependencies, then verify strict private-CA HTTPS and backend identities.
   Review restored operation records before allowing writes; excluded staging
   payloads cannot be recreated from configuration receipts.
5. Keep operator CA keys private. The user prohibits host trust-policy changes;
   do not install the CA or retry the canceled macOS trust prompt. Recovery checks
   may use an explicit CA file without changing the host trust store. Browser
   access must work within the existing trust policy; it remains unverified.

The first independent restores verified 26 server files and one database,
40 files in bootstrap escrow, and 63 NAS settings files including five Filex
SFTP files. These are archive recovery checks, not a replacement-host startup
or a backup of the media collection. See the current closure receipt for the
subsequent off-host checkpoint and any remaining acceptance gaps.

The same four verified archives (Filex server, Filex bootstrap, NAS settings and
Plex settings) were uploaded as ciphertext to the existing Storage Box under
`catalog/.backups/closure-20260922`. Every remote readback matches the exact
archive independently restored on the Mac. This is also a one-time off-host NAS
settings checkpoint; the recurring NAS off-host schedule and original-file scope
remain open. The daily Filex bundle continues through the normal cloud schedule.

The final outer archive `cloud-20260922T215403Z.tar.age` passed remote readback
and independent restore, including a second independent restore of both nested
Filex bundles. The full checkpoint contains 752 files and five application
databases; the nested Filex database is verified separately.
