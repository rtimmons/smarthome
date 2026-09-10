# Operations

## Administrative access

SABnzbd and Prowlarr listen on cloud loopback only. Open a tunnel from the
workstation:

```sh
ssh -L 8080:127.0.0.1:8080 -L 9696:127.0.0.1:9696 "$CLOUD_SSH_TARGET"
```

Then use `http://127.0.0.1:8080` and `http://127.0.0.1:9696`. Do not change the
Compose bindings to `0.0.0.0`.

Configure SABnzbd's incomplete and complete paths as `/data/incomplete` and
`/data/complete`. Configure the two TLS providers exactly as recorded in
`account-setup.md`. Set a conservative free-space pause threshold large enough
for the biggest expected repair/unpack; the initial operational floor is 30 GiB.

Add NZBGeek and NZBFinder to Prowlarr and run each built-in API test. Add SABnzbd
as a download client at `http://sabnzbd:8080`. Do not add Sonarr/Radarr-style
automatic acquisition, RSS grabs, broad automatic search, or another path that
can silently make an arbitrary result permanent. A human intentionally chooses
each acquisition and later supplies its provenance when promoting it.

## Deliberate acquisition and promotion

1. Confirm that the material is authorized and record the basis.
2. Deliberately send the selected NZB to SABnzbd.
3. Wait for local download, PAR verification/repair, and unpack to finish.
4. Review the completed directory and promote it from the workstation:

```sh
just catalog-promote \
  /srv/usenet/downloads/complete/ITEM \
  "Human-readable title" \
  other \
  "Indexer or official test source" \
  "Public-domain, freely redistributable, owned, or generated test content"
```

Promotion rejects sources outside the configured completed directory and
rejects symlinks. It calculates SHA-256 for every file, copies to a unique remote
`.incoming` path, downloads/checks the remote bytes, moves the verified tree to
its immutable catalog ID, and publishes the manifest last. Failures leave local
content and recoverable remote staging intact. Local completed content is kept
unless the operator explicitly adds `--delete-local` after a verified publish.

Remote layout:

```text
catalog/
├── .incoming/
├── manifests/<item-id>.json
└── objects/<category>/<item-id>/...
```

## Selective QNAP cache

From `usenet-infra/` on the workstation:

```sh
just catalog-list
just catalog-status
just catalog-pull "item-id"
just catalog-evict "item-id"
```

Pull requires enough free bytes for the item plus the configured reserve. It
copies to hidden staging, validates every local SHA-256, then performs a
same-filesystem rename into the cache. A failed or interrupted item never appears
as a complete cached object. Retry the same command safely; complete matching
files are skipped, though one interrupted file restarts from byte zero.

Eviction resolves a local state record and deletes only the root-confined local
object directory. Its implementation never calls rclone. The QNAP's server-side
read-only Storage Box subaccount is the independent backstop against a client
bug.

## Health and failures

```sh
just cloud-health
just qnap-health
```

Cloud health checks Storage Box reachability/capacity, SABnzbd, Prowlarr health
including indexer-reported faults, scratch free space, and recorded promotion
failures. QNAP health checks Storage Box access, cache free space, and recorded
pull failures. Ansible synchronizes the locally generated SABnzbd and Prowlarr
API keys into the protected health environment after starting the applications.
A missing application API key is a warning; a configured but unreachable service
is a failure.

Set `STORAGE_WARN_FRACTION=0.80` in the deployed catalog environment. Do not
rely on a compiled/default value: 80% is the approved operator warning. At a
warning:

1. Check catalog objects, `.incoming`, and snapshots for unexpected growth.
2. Confirm current used space and the next tier's authenticated account price.
3. Back up the storage Terraform state and verify independent recovery copies.
4. Before 90% use, change only the desired Storage Box type along the approved
   BX11 -> BX21 -> BX31 -> BX41 ladder.
5. Require the storage plan to show an in-place type update with no replacement,
   deletion, location change, SSH-key change, or protection reduction.
6. Apply deliberately, then verify the Storage Box ID, catalog hashes, QNAP
   read-only access, capacity, and health checks.

Hetzner permits upgrades and permits downgrades only when use is below the
smaller tier's capacity. Snapshots consume capacity and lower tiers have fewer
snapshot slots, so remove or independently preserve excess snapshots before a
downgrade. The provider's type update is in place, but Hetzner does not make an
explicit zero-downtime guarantee for ordinary tier changes. See the official
[scaling rules](https://docs.hetzner.com/storage/general/which-storage-is-right-for-me/),
[snapshot limits](https://docs.hetzner.com/storage/storage-box/snapshots/), and
[hcloud provider 1.68.0 implementation](https://github.com/hetznercloud/terraform-provider-hcloud/blob/v1.68.0/internal/storagebox/resource.go#L432-L447).

Failure records live under the configured catalog state `failures/` directory.
Inspect the corresponding service/container logs and keep the record until the
cause is fixed and the operation has been successfully retried.

## Updates

Review release notes and change pinned versions in Git first. Then:

```sh
git pull --ff-only
terraform -chdir=terraform/cloud plan
terraform -chdir=terraform/storage plan
ansible-playbook -i ansible/inventory.yml ansible/site.yml
ssh "$CLOUD_SSH_TARGET" 'cd /srv/usenet/compose/cloud && docker compose pull && docker compose up -d'
just cloud-health
just qnap-health
```

Never use `latest`. Preserve application config backups before upgrades and test
the authorized fixture path after a major SABnzbd, Prowlarr, rclone, Docker, or
catalog-tool update.

## Configuration backups

Back up and encrypt, separately from the canonical library as it grows toward
the 20 TB target:

- `/srv/usenet/config/sabnzbd`;
- `/srv/usenet/config/prowlarr`;
- `/srv/usenet/state/catalog`;
- the QNAP catalog state directory; and
- Terraform states, variable files, SSH keys, and verified host keys.

Storage Box snapshots are same-box rollback aids, consume capacity, and are not
an independent backup. Keep source in Git and put encrypted configuration
backups somewhere outside both the VM and Storage Box.

## Authorized end-to-end acceptance test

Use a provider's official test NZB or a small item whose redistribution license
has been independently verified. Record that evidence in the manifest. Then
verify all of the following before declaring production ready:

1. Eweka connects over TLS with strict verification.
2. The fill block tests successfully but remains lower-priority/optional.
3. Both indexer built-in API tests pass.
4. SAB downloads, verifies, and unpacks the authorized item locally.
5. Promotion publishes bytes and a provenance manifest.
6. QNAP lists, pulls, SHA-256 verifies, and reports the item local.
7. Eviction removes the local copy while the writer still sees identical remote bytes.
8. QNAP credentials fail overwrite and delete attempts against a disposable sentinel.
9. Restarting both Compose projects preserves configuration.
10. Repository secret scans find no credential material.
