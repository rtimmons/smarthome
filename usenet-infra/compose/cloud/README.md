# Cloud applications

SABnzbd and Prowlarr bind only to host loopback. Keep provider TLS and the private
proxy/tunnel; never expose application ports publicly. `.env` contains only
numeric UID/GID, timezone and ports. Credentials belong in protected application
configuration and encrypted backups.

SAB uses the dedicated repair-volume bind at `/data/incomplete` and completed
Storage Box staging at `/data/complete/remote/complete`. Start it only through
`usenet-sab-remote.service`, which requires the actual mounts. Its Docker restart
policy is disabled. Do not create writable fallback directories or start SAB
with a direct `docker compose up`.

Prowlarr runs independently and supplies indexers to Arr. Its direct SAB download
client remains disabled. Restore accepted app state rather than replaying initial
configuration. Bootstrap cloud packages with `cloud_start_compose: false` until
mounts and app state are restored; normal deployment then starts Prowlarr through
Compose and SAB through systemd.

Image versions are pinned. See the current [native workflow](../../docs/native-media.md),
[storage recovery](../../docs/repair-spool.md), [access](../../docs/lan-ui.md) and
[operations](../../docs/operations.md) guides.
