# Checkout deletion and recovery

The user authorized preserving the checkout so it can be deleted, and explicitly
deferred NAS-loss protection. This is narrower than replacing Home Assistant,
UniFi or the entire NAS. No checkout was deleted.

The additive snapshot `20260911T235253Z-9d6bbacf00ac982a` lives at:

```text
/share/Container/usenet-recovery/20260911T235253Z-9d6bbacf00ac982a/
```

It contains 1,319 unique local files: ignored credentials/private configuration,
Terraform state, retained archives, local MongoDB, generated-label skill work,
HA inventories/history, operational notes and the untracked `msg` file. Ciphertext
is 525,627,393 bytes, SHA-256
`4a7c871f62fa61c1a82f5329fad1e9dbc4bc9b7e0cb2513f74b1222015e90759`.

Named dependency/tool/build caches are excluded. One derived recovery-download
directory was omitted only after every file matched its preserved original
byte-for-byte. The source is still included. The archive format is a streamed
compressed tar encrypted with age to the existing cloud-admin public identity;
its private identity remains recoverable through the original SOPS vault.

Verification used source cloned independently from published commit `185e420`,
a freshly bootstrapped age binary, and credentials recovered in the earlier
clean-clone drill. The NAS archive was fetched independently, all files restored
and checked, and local MongoDB started on a separate loopback port. All five
collections in five databases validated; that temporary database was shut down.
The restored inputs were installed into the new clone with overwrite refusal.
Only the two present configuration files needing checkout-path rebasing changed;
remote host paths were preserved. The recovered clone successfully authenticated
and read live Radarr/Sonarr health with native import enabled.

Original SOPS-bound inventory, vault and full-machine `deletion_safe: false`
receipts remain unchanged. The NAS recovery store's immutable transport receipt
also keeps that conservative field. Checkout readiness is recorded separately
in `recovery/drills/checkout-20260911.json` and checked against current local work
and published source. New ignored files or uncommitted/unpublished changes make
that check fail and require a new snapshot or publication.

## Recovery sequence

1. Clone the published `usenet` branch using the HTTPS GitHub URL and bootstrap
   pinned tools with `just setup` / the narrower infrastructure bootstrap recipes.
2. Restore the original SOPS vault using the existing master from 1Password or
   its already confirmed paper copy. Follow the original clean-clone runbook;
   do not generate replacement keys or modify its bound inventory.
3. Fetch the additive snapshot with `scripts/recovery-store.py fetch` using the
   restored dedicated QNAP identity and host pin. This is a checkout-local archive,
   so use `checkout-backup.py`, not `recovery-bundle.py`, to decrypt it.
4. Run `python3 scripts/checkout-backup.py restore --archive /absolute/recovery.tar.age
   --identity /absolute/cloud-admin --destination /absolute/new-isolated-directory`.
5. For a fresh clone with no conflicting private files, `checkout-backup.py install
   --source-directory /absolute/new-isolated-directory --destination /absolute/new-clone
   --source-checkout /Users/rtimmons/Projects/smarthome` moves restored inputs into
   that clone. It refuses every existing-file collision and rebases only the
   configuration paths already identified in the immutable inventory. If vault
   inputs already exist in that clone, use a separate fresh target for this step
   or review the conflicts individually; do not overwrite them blindly.
6. Use the latest private inventory overrides documented in
   [scheduled backups](scheduled-backups.md), then inspect live services before
   choosing whether any live restore or redeployment is necessary.

To verify that the current checkout still matches this backup, run
`checkout-backup.py check --archive /absolute/recovery.tar.age --identity
/absolute/cloud-admin`. It checks every preserved local file, rejects tracked
changes, and requires HEAD to match published `usenet`. This command never deletes
anything. Host-owned backup schedules continue when the checkout is absent.

Loss of the NAS disks remains out of scope. Actual HA/UniFi replacement drills,
Plex package startup restoration and TV-client setup remain separate work.
