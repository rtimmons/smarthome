# Utility services

## TinyURL and MongoDB

`tinyurl-service` maps short links to their destinations. MongoDB stores persistent mappings; it is a dependency, not a user-facing website. An HTTP service restart cannot recover missing database data.

Use short links through the applications that create them. If a link fails, separate an unavailable TinyURL service from a missing or invalid mapping, then check database connectivity. Do not expose database administration on the LAN as a troubleshooting shortcut.

Configuration belongs to the respective add-on manifests and service sources. Local development ports do not establish production exposure. Keep database credentials in the existing private configuration stores.

For recovery, restore the relevant add-on/database state backup before declaring old links restored. Repository source can rebuild the service, but it cannot reconstruct all historical mappings.

Read [TinyURL](../../tinyurl-service/README.md), [MongoDB](../../mongodb/README.md), and [add-on backup procedures](../../docs/operations/addon-state-backups.md).
