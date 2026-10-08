# Usenet and selective NAS copies

The working path is **Seerr → Radarr/Sonarr → SAB → Storage Box → Plex**.
Arr owns native imports and completed-source cleanup. Explicit NAS copies are
optional, SHA-256 verified and read from canonical storage with a server-enforced
read-only account. RSS, direct carts and the old publisher/import/admission workers
are disabled. Their executables and one-time migrations have been removed.

## Access

| Interface | Private address |
| --- | --- |
| Seerr requests | `http://10.77.0.1:15055/` — Plex sign-in |
| Radarr / Sonarr | `http://10.77.0.1:19696/radarr/` / `http://10.77.0.1:19696/sonarr/` |
| Prowlarr | `http://10.77.0.1:19696/` |
| SAB | `http://10.77.0.1:18080/` |
| NAS copy dashboard | `http://192.168.1.66:1337/` |
| Plex | `http://192.168.1.66:32400/web` |
| Filex | `http://127.0.0.1:15213/` while `just usenet-filex-ui` runs |
| Static field guide | `http://192.168.1.66:8090/` |

Use dedicated identities and pinned hosts from ignored private inputs. Recover
missing inputs through the vault/backup chain; do not repeat account setup or
change host trust policy. See [agent rules](AGENTS.md).

## Routine commands

Run from the repository root:

```sh
just usenet-native-ownership-status
just usenet-discovery-health
just usenet-cloud-health
just usenet-qnap-health
just usenet-filex-status
just usenet-seerr-status
just native-list
just native-status
```

`native-pull 'native-<id>'` copies a selected title; `native-evict 'native-<id>'`
removes only its owned NAS copy. `catalog-list`, `catalog-pull` and `catalog-evict`
serve existing catalog objects. Preserve active work, manual pauses, the 100 GiB
release limit, both 30 GiB SAB reserves and the 100 GiB NAS reserve.

## References

- [Operations](docs/operations.md): commands, component deployment and diagnostics.
- [Native workflow](docs/native-media.md), [storage](docs/repair-spool.md),
  [discovery](docs/discovery.md), [NAS/Plex layout](docs/nas-plex-layout.md) and
  [download status](docs/download-status.md): current behavior and boundaries.
- [Scheduled backups](docs/scheduled-backups.md), [recovery](docs/recovery.md),
  [secrets](docs/secrets-recovery.md) and [checkout recovery](docs/checkout-recovery.md).
- [Filex](docs/filex.md), [Filex recovery](docs/filex-recovery.md),
  [Seerr](docs/seerr.md), [LAN access](docs/lan-ui.md) and [wiki](docs/wiki.md).
- [Architecture](docs/architecture.md), [accounts](docs/account-setup.md),
  [Terraform](terraform/README.md) and [Ansible](ansible/README.md).
- [Validation](docs/validation.md): accepted cases and evidence limits.

Run `just --justfile usenet-infra/Justfile --working-directory usenet-infra test`
after implementation changes. The full-history scan has two documented
[historical key findings](docs/security-findings.md). Current source/index checks
are separate. Original recovery receipts remain immutable; Git history holds
superseded runbooks and implementations.
