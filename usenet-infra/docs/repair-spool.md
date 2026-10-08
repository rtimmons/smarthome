# Repair storage and mount recovery

The CX43 host uses an existing 300 GB ext4 volume for incomplete downloads.
Completed staging and canonical media share the BX21 Storage Box. Preserve
`repair_spool_enabled = true`, `storage_box_type = "bx21"`, provider deletion
protection and Terraform `prevent_destroy` in current private inputs.

| Host path | Backing storage / purpose |
| --- | --- |
| `/srv/usenet/repair` | Existing repair volume, mounted by filesystem UUID |
| `/srv/usenet/repair/incomplete` | SAB compressed/repair spool |
| `/srv/usenet/downloads/incomplete` | Bind of the repair spool; SAB sees `/data/incomplete` |
| `/srv/usenet/library` | Synchronous Storage Box SSHFS mount |
| `/srv/usenet/downloads/complete/remote` | Bind of `library/.acquisition-staging`; completed output is its `complete` child |

`config/catalog/repair-spool.json` records the provider volume ID and filesystem
UUID. `state/catalog/repair-spool-setup.json` is immutable historical evidence,
not a command to replay. The former `downloads/incomplete-local-spool` is a dated
rollback copy, not synchronized state; retain it until a separate disposition.

## Restore current definitions

The deleted remote/hybrid/repair migration helpers are not needed for the current
layout. Restore application configuration and current source from the verified
backup chain. Restore the existing writer key and pinned host, then the library
mount through `ansible/cloud-library.yml`. Keep SAB and Arr stopped while repairing
mount configuration; inspect activity before stopping either service.

Run from `usenet-infra` only on the restored host:

```sh
just restore-storage
```

This checks that SAB/Arr systemd services are inactive, verifies the existing
provider device's UUID against the restored marker, protects empty unmounted
directories, installs current units and enables mounts. It does not format,
copy payloads, switch a running installation, or start applications. An unknown
volume, nonempty unmounted directory or active application requires inspection.
A replacement volume needs a separately reviewed initialization and identity;
never use the production marker to format it.

The repair unit requires the saved UUID; the incomplete bind requires both
repair and completed-storage mounts. SAB binds to incomplete storage; Arr binds
to the library and SAB storage lifecycle. `config/usenet-discovery.service` and
`compose/discovery/compose.yaml` contain the final layout directly. Install
`config/arr-shared-library-init` at `/srv/usenet/libexec/arr-shared-library-init`
as root-owned mode 0555 before starting Arr; the discovery role does this.

Keep restored old workers disabled. Review any restored Compose overrides or
systemd drop-ins before startup: they must agree with these current definitions,
not redirect scratch to an earlier layout. Mount the existing filesystems and
verify paths, free space, ownership and the saved Arr completed-path mapping.
Then start SAB through `usenet-sab-remote.service` and Arr through
`usenet-discovery.service`, preserving queue pauses. Do not start SAB directly
with Docker Compose or grant Docker its own restart policy.

## Capacity and failure behavior

Keep the 100 GiB release limit, both 30 GiB SAB reserves, Arr hardlinks/free-space
checks and mount-dependent startup. A mount failure must stop/refuse applications;
never make its underlying directory writable to get past a startup failure.
Do not run `mkfs`, replay purchase plans, delete retained spools or apply the
canonical storage root during a cloud restore.

The accepted 80 GiB PAR2 repair and two concurrent 50 GiB expansions are bounded
tests, not guarantees for arbitrary archives. See [validation](validation.md)
for evidence and [recovery](recovery.md) for the wider recovery procedure.
