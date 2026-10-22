# Sonos migration: remaining work

Reconciled October 22, 2026. Home Assistant-backed Sonos API is deployed; the
candidate is merged. The October 9 deployment disabled the retained node add-on,
removed the Sonos API dependency, and verified port 5005 closed with healthy
HA-backed API/Grid reads. Normal Sonos controls were user-confirmed after the
October 22 gateway changes. These checkpoints do not establish the outstanding
observation windows or authorize final deletion.

[Architecture](sonos/overview.md), [routing and rollback](sonos/routing-guide.md),
[source compatibility](sonos/source-compatibility.md) and
[validation evidence](sonos/ha-migration-validation.md) own the implemented
contracts. The old implementation/merge checklist is superseded.

## Remaining work

- [ ] **Close route decisions.** Observe external callers and obtain explicit
  disposition of the five legacy root routes (`/pause`, `/play`, `/tv`, `/07`,
  `/quiet`) that already return `410` in HA mode. No recorded parity exception
  approves those responses yet. Retain every other compatibility route still used.
- [ ] **Complete reproducible acceptance evidence.** Tie current package digests,
  deployed source and the full automated route/security/packaging matrix to a clean
  revision. Scoped Sonos tests passed at the October 9 checkpoint; its root run
  stopped on unrelated printer visual baselines. Record the final root/container/
  clean-install result; a failing root run remains a blocker. Older pre-commit
  results do not establish final acceptance.
- [ ] **Finish live parity and recovery checks.** Record actual iOS 12 direct/ingress
  operation, artwork, reconnect/stale recovery, join/leave/join-all and partial/
  superseded operations, unequal group volume, favorites and all three TV presets.
  Include available Apple Music/line-in capabilities or record the limitation.
  Exercise the documented rollback within 10 minutes. Capture and restore current
  household state; normal-control confirmation alone does not cover this matrix.
- [ ] **Resolve missing observation evidence.** The record still lacks accepted
  uninterrupted 24-hour shadow, 24-hour panel pilot, 48-hour whole-house and
  24-hour stopped-node evidence. The October 9 stop returned Supervisor `error`,
  although port 5005 was closed and boot/watchdog disabled. Recheck current state,
  unexpected restarts, callers and observation coverage; calendar time elapsed
  does not prove a monitored window. Record completion or the user's explicit
  disposition of missing gates. Do not automatically restart node or switch away
  from healthy HA mode to recreate historical stages.
- [ ] **Retain a proven reinstall path.** Preserve a current verified state backup,
  prior node/Sonos API installable packages and checksums outside disposable build
  output, exact reinstall commands and configuration, a safe-target rehearsal and
  a concrete retention date at least 30 days after uninstall. The August 29 export
  proves the backup workflow ran; it does not prove today's reinstall path.
- [ ] **Final retirement.** Obtain explicit behavior acceptance and final uninstall/
  code-removal authorization after the above gates. Remove the retained add-on,
  node/shadow modes, legacy clients, patches/hooks, packaging/development references
  and obsolete documentation; preserve journals and private recovery artifacts.
  Verify HA-only clean install/development, no direct Sonos discovery dependency
  or node traffic, closed port 5005, representative controls and root checks.

## Rollback

The executable procedure is maintained in
[backend rollback](sonos/routing-guide.md#backend-rollback). Keep node disabled
outside an explicitly requested rollback. Preserve unrelated work and private
credentials; never expose the Supervisor token, signed artwork URLs or real
media metadata in acceptance records.
