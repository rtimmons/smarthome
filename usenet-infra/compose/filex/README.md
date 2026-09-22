# filex deployment boundary

An isolated read-only pilot, deployed only by `ansible/filex.yml` through
`just usenet-configure-filex`. It is absent from normal cloud startup.

The image is pinned to a reviewed version **and digest**. It starts directly as
its dedicated non-root identity with all capabilities dropped. Host-prepared
binds expose only portal state, its private server configuration and a new
read-only staging directory. HTTP is published only on `127.0.0.1:5212`.

Do not run this Compose project manually before preparing its private inputs and
host directories. See [the runbook](../../docs/filex.md) for credentials, private
TLS routing, bootstrap, acceptance and rollback. The manifest example is at
`config/examples/filex.json`; real inputs belong in ignored mode-0600 files.

Remote SFTP storages require dedicated server-restricted read-only accounts and
verified host public keys. The helper refuses unreviewed roots, writable storage
configuration and unsafe host-key options. The ordinary browsing login is a
viewer; the admin account is only for restricted loopback maintenance.

Filex's current native cross-storage move checks size and deletes permanently,
and its queued admin API does not enforce every read-only storage flag. The
pilot therefore relies on kernel/server restrictions and does not enable write,
delete or move. These are documented acceptance gaps, not accepted substitutes
for the plan's verification and deletion rules.

Use `just usenet-filex-disable` to stop/disable only this portal. Preserve
`/srv/usenet-filex/data`, its configuration and staging during review; rollback
must consider database compatibility as well as the image pin.
