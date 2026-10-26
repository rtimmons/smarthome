# Agents Guide

Repository-wide constraints; component `AGENTS.md` files add local guidance.

## Ground rules
- Durable controller inputs now live outside Git at `~/.local/share/smarthome/tree/`.
  Run `just checkout-prepare` on a fresh/clean checkout before standalone tools;
  deployment does this automatically. Existing `.ssh/` and infrastructure paths
  are compatibility links to those same dedicated keys, not new identities.
  Preserve the separate master `~/.config/smarthome/recovery.agekey`; see
  `docs/setup/disposable-checkout.md`. Never clean the external state directory.
- Default to `just` recipes and the provided env wrappers (`.venv`, `nvm`) instead of ad-hoc commands.
- You start in a sandbox; ask before taking the git lock (`git add`, etc.).
- Agent commits must use the dedicated, Git-ignored SSH signing key `.ssh/id_ed25519_codex_git_signing`, never Ryan's personal signing identity or SSH agent. From the repository root, use `git -c gpg.format=ssh -c gpg.ssh.program=ssh-keygen -c user.signingkey="$PWD/.ssh/id_ed25519_codex_git_signing" -c commit.gpgsign=true commit ...` (apply the same overrides to other operations that create signed commits). Preserve the user's normal Git configuration and author metadata. If this key is missing, create a dedicated Ed25519 signing key there; never fall back to a personal key or reuse infrastructure access keys. Keep its private key untracked.
- Runtimes are pinned by `.nvmrc` (Node) and `.python-version` (Python); use the self-contained nvm/pyenv installed by `just setup`.
- “Prepare to commit” means: stage your changes (with permission), run `just test`, and drop the proposed commit message in `./msg` without staging that file.

## Paired printer repository
- `printer/` is an independent, ignored private Git repository, cloned from
  `ssh://git@git-ssh.home.arpa:2222/ryan/printer.git`. It is required at that exact
  path for setup, tests, local development, builds, deployment and wiki checks.
  It is not a submodule; never force-add it or its source to this repository.
- The two repositories may depend on each other's current structure and change
  together. Keep application code, tests, assets and printer docs in `printer`;
  keep shared orchestration and integration consumers in smarthome. Read both
  this file and `printer/AGENTS.md` before cross-repository work.
- Inspect both `git status` and `git -C printer status` before and after work.
  A printer-only implementation change needs only a printer commit unless its
  public integration/docs or the printing wiki review also change. Shared API,
  manifest, build/runtime or deployment changes require a coordinated pair when
  both repositories are affected; do not create empty companion commits.
- For coordinated commits, finish both sides and run root `just test` against
  the combined working trees first. Ask before index writes as above. Stage
  explicit paths separately and inspect each complete staged diff, filenames,
  and proposed message for secrets and media identifiers. Put a proposed message
  in each affected repo's untracked `msg` without overwriting an existing message.
- Git cannot commit two repositories atomically. When commits are authorized,
  commit printer first, then smarthome with the printer SHA in its commit body;
  use a shared short change description in both messages. Record both SHAs in
  the handoff. If the second commit fails, finish or report the incomplete pair
  before deployment/publication; do not rewrite unrelated history. When pushes
  are requested, push printer only to its private origin before the smarthome
  companion. Never push printer to GitHub.
- Use the same dedicated agent signing key for both repos. From this root, the
  printer command is `git -C printer -c gpg.format=ssh -c gpg.ssh.program=ssh-keygen
  -c user.signingkey="$PWD/.ssh/id_ed25519_codex_git_signing" -c commit.gpgsign=true
  commit ...`. Do not change the user's Git configuration or author metadata.
- A fresh clone/worktree must have its own private clone at `printer/`; see
  `docs/setup/dev-setup.md`. Preserve its `.git`, ignored state and uncommitted
  work. Never use `git clean -ff` to remove nested repositories. History in old
  smarthome commits is unchanged; this boundary keeps future printer source out
  of smarthome commits.

## Media privacy
- Never commit specific movie/show/episode/song/program titles, artists, albums, release names, media filenames, artwork URLs, or identifying catalog links/IDs from live content. This applies across the repository, including wiki sources, code examples, fixtures, receipts, filenames, and commit messages.
- Use neutral aliases (`media-001`) for operational evidence and clearly synthetic metadata (`Synthetic Track`, `Fixture Artist`) in tests. Preserve parser syntax and relationships without copying real content. Exact operational names and replacement maps belong only in ignored private evidence.
- Configured radio stations and music favorites are an explicit exception: preserve the exact names/identifiers needed to select playback sources. This exception does not extend to incidental now-playing metadata or live response dumps.
- Before committing, inspect the complete staged diff, added/renamed paths, and proposed commit message for content identifiers. Secret scanning alone does not establish media privacy. For a history audit, inspect all branches/tags and commit messages, including deleted files; cleaning the current tree alone is insufficient. Rewrites must also account for remote refs, stashes/reflogs, and old backup clones without changing immutable private recovery snapshots.

## Root workflows (Justfile-aligned)
- Bootstrap everything: `just setup` (installs pinned Node/Python, builds `talos` if needed).
- Create the ignored, repository-local Home Assistant SSH key with `just ha-ssh-key-create`. A human installs it on Home Assistant once with `just ha-ssh-key-copy`; agents must not run the copy recipe.
- Run the whole stack locally: `just dev`; free conflicting ports with `just kill`. Read the relevant add-on’s `AGENTS.md`; manifests and the generated wiki service reference own ports and dependencies.
- Build add-ons: `just ha-addon [addon]`; list discovered add-ons with `just addons` (discovery is by `*/addon.yaml`).
- Deploy: `just deploy [addon]` builds via `talos` and deploys, then rolls out `new-hass-configs`. Use `just printer-image` to preflight the printer container build.
- Tests: `just test [addon]` runs add-on tests plus container build checks.
- `talos` lives at `talos/build/bin/talos`; build it with `./talos/build.sh` if a recipe complains.

## Reference repos
- Upstream Home Assistant references live under `reference-repos/` as submodules; see `reference-repos/AGENTS.md` for purposes, doc entry points, and refresh commands.

## Home Assistant configuration
- Everything lives under `new-hass-configs`. Common commands: `just fetch`, `just check`, `just deploy`, and `./iterate.sh` for before/after scene inventories. From the repo root, use the repository-owned `just ha-state <entity_id>`, `just ha-call <domain.service> <entity_id>`, and `just ha-inventory` commands to inspect or operate the live system; they do not depend on the Python-based `hass-cli` package.
- **SSH access**: From the repository root, use `ssh -i .ssh/id_ed25519_codex_smarthome -o IdentitiesOnly=yes root@homeassistant.local` to access Home Assistant directly. Always select this repository-local identity explicitly; do not use 1Password or another SSH-agent identity for agent access. The remote `ha` command manages Core/Supervisor lifecycle, logs, backups, and host services; it does not expose entity state or service-call commands, so use the repository API client for those. The entity registry is at `/config/.storage/core.entity_registry` for advanced device discovery.
- **SSH key setup and failures**: The private key is local-only under the Git-ignored `/.ssh/` directory. If the keypair is missing, run `just ha-ssh-key-create`, then stop and ask Ryan to run the human-only `just ha-ssh-key-copy`. If the dedicated key exists but authentication fails, stop the Home Assistant workflow immediately and ask Ryan to rerun `just ha-ssh-key-copy`; do not retry repeatedly or fall back to 1Password, another host, an IP address, a browser session, an API token, or alternate credentials.
- **Hostname failures are not authentication failures**: The Codex sandbox can fail to resolve `homeassistant.local`. Retry the same hostname-based command with the repository-local identity once outside the sandbox; do not substitute an IP address. If it still cannot resolve, stop and report the mDNS/network failure rather than changing credentials.

## Operational notes
- Lifecycle hooks live in `local-dev/hooks/` per add-on and are documented in `docs/addon-development/hooks-guide.md`; `node-sonos-http-api` checks Sonos multicast reachability and `printer` validates cairo/pkg-config for label rendering.
- Sonos reliability patches are in `node-sonos-http-api/patches` and are applied during container builds; adjust those patches if you change upstream Sonos behavior.
- RGBW scenes use the aggregate endpoint 1 exactly once for white, color, and all-channel off. White scenes send an explicit `rgbw_color: [0, 0, 0, level]` plus matching brightness; `_white` endpoint entities are diagnostic-only because they can report on without energizing the installed strips. Never auto-expand a target to multiple endpoints. Node 7's aggregate curtain entity also has proven optimistic false matches, so its device uses `fastSceneForceOnDispatch: true` to send turn-on commands during both initial and convergence passes; off remains mismatch-only. Do not apply that extra traffic to other devices without the same live evidence. Repo-owned Z-Wave JS priority configs under `new-hass-configs/zwave-device-configs/` request `disableAutoRefresh` for the installed RGBW controller models; deploy them with `just zwave-deploy-device-configs`. A `User-provided device config loaded` message proves only that the file parsed: node 3 still ran an endpoint-sensor refresh afterward, so verify behavior in the persistent log rather than assuming the flag took effect.
- Operational lighting must use `script.fast_scene_<scene_id>`, never native `scene.turn_on`; wrappers record per-target-scope intent so disjoint rooms remain additive, overlapping targets use the newest request, and `all_off` overrides every scope. Per-room restart dispatchers feed one global queued 500-ms-paced Z-Wave gate while preserving health/mismatch filtering, error isolation, skipped-target reporting, and convergence. Central Scene automations pass `origin_entity_id` so the local load is suppressed on the initial pass and a short RF quiet window protects the trigger. Non-Z-Wave and Z-Wave branches start together. Compatible dimmer hardware uses isolated CC38 `zwave_js.set_value` with `wait_for_result: false` and a zero-second transition. Multicast is currently forbidden for every device because repeated normal-operation failures invalidated the former Minoston MP22ZD allowlist. See `docs/operations/zwave-scene-ops.md`.
- `new-hass-configs/scripts.yaml` is a generated, ignored deployment artifact. Edit generator sources, review `new-hass-configs/generated/scripts.yaml`, and let `just generate`, `just check`, or deployment prechecks rebuild it; do not commit or reconcile the root file.
- Outlets powering smart lights must set both `includeInAllOff: false` and `allowSceneTurnOff: false`; generated scenes must control the bulb entity and never cut its power.
- Former Z-Wave node 2 (`living_palm`) was permanently retired on 2026-10-16; do not restore it to the device registry or scenes. Node 16 (`outdoor_cafe`) was intentionally removed on 2026-08-21 and retains its desired entity ID in `devices.ts` with `inventoryStatus: "temporarily_removed"`; preserve that marker while absent, then clear it only after re-inclusion and restoration of the same entity ID. If failed-node removal is accepted but its completion event times out, do not submit it again: restart only Z-Wave JS once, then verify the fresh controller node list and Home Assistant registries.
- Z-Wave nodes 23 (`guestbathroom_overhead`) and 28 (`living_sillleftpower`) are temporarily excluded from every generated scene through `sceneStatus: "temporarily_excluded"`. Node 23 remains usable as a Central Scene trigger and changes its local load, but repeatedly times out during command acknowledgement. Node 11 (`kitchen_dining_nook`, also called the living nook) returned on 2026-09-01 and is active in scenes again; preserve the remaining exclusions until node 28 is repaired and node 23 is excluded/re-included or replaced.

## Docs map
- The smarthome wiki is built from `wiki/` and explicitly imported canonical runbooks. For behavioral changes, update the corresponding explanation and run `just wiki-check`. Review changed component fingerprints with `just wiki-review <component> '<specific reason>'`; do not acknowledge unfamiliar changes merely to bypass the check. Supported deployments publish once after success; use `just wiki-deploy` for documentation-only changes. See `docs/operations/wiki.md` and `docs/operations/home-dns.md`.
- Usenet, QNAP storage, Plex and their recovery workflow: read `usenet-infra/AGENTS.md` and `usenet-infra/docs/validation.md` for accepted scope and recovery limits before operating them.
- Start with `docs/README.md` for the index; `docs/setup/dev-setup.md` and `docs/development/local-development.md` cover local workflows.
