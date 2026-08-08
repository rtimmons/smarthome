# Grid dashboard upgrade plan

> **Status:** Proposed — no dashboard upgrade work described here has been implemented
>
> **Investigation baseline:** 2026-08-08
>
> **Scope:** The Grid Dashboard add-on, its Home Assistant-facing action and state contracts, and the iPad mini 3 wall panels that use it
>
> **Primary rule:** Preserve the existing one-screen, room-context interaction model and iOS 12 compatibility while moving device logic behind stable Home Assistant interfaces.

## Objective

Keep the wall-mounted dashboard fast, predictable, and usable on the existing iPad mini 3 units while reducing the custom behavior embedded in its browser code. The upgraded dashboard should remain a lightweight appliance interface rather than becoming a general-purpose Home Assistant administration UI.

Completion means that:

- The complete primary control surface still fits on one landscape screen without scrolling or routine navigation.
- Every current, working control has an equivalent after the upgrade, including room selection, Sonos grouping and playback, lighting scenes, LED-wall presets, and the printer shortcut.
- Icons render consistently on iOS 12 without depending on the operating system's emoji set.
- Device actions are provided by Home Assistant scripts, entities, or documented backend adapters instead of being assembled independently in browser code.
- Per-panel room context remains local to each iPad and cannot be changed inadvertently by another panel.
- The dashboard displays useful pending, stale, unavailable, and failure states without issuing duplicate actions.
- A secondary Home Assistant-native dashboard can use the same scripts and entities on supported devices.
- The previous dashboard release remains available as a tested rollback until the upgraded version has passed a wall-panel observation period.

This is an execution plan, not a claim that the listed work has been completed.

## Recommendation

Retain and modernize the Grid Dashboard as the primary wall-panel UI. Do not replace it with a Home Assistant-native dashboard while the installed panels remain iPad mini 3 units.

The iPad mini 3 uses an A7 processor and is capped at iOS 12.5.7. Apple lists iOS 12.5.7 for this model and dates that security release to January 2023 ([Apple security documentation](https://support.apple.com/en-euro/103015), [iPad mini 3 specifications](https://support.apple.com/en-kw/112018)). Home Assistant's legacy frontend targets browsers released within approximately the last seven years, which places iOS 12 outside the intended compatibility window as of this assessment ([Home Assistant browser targets](https://github.com/home-assistant/frontend/blob/dev/.browserslistrc)). A native dashboard may happen to load, but it is not a dependable primary interface for these panels.

The long-term architecture should support two frontends over the same Home Assistant contracts:

```text
iPad mini 3 panels -> lightweight Grid Dashboard --+
                                                 +-> HA scripts/entities -> devices and custom adapters
Supported devices -> native Home Assistant UI ---+
```

This preserves the useful wall-panel experience now and avoids trapping device behavior in that frontend. When the iPads are eventually retired, the presentation layer can change without another whole-home action migration.

## Current functionality and strengths

The dashboard is a fixed 11-column by 8-row touch grid configured in [`grid-dashboard/ExpressServer/src/public/js/config.js`](../grid-dashboard/ExpressServer/src/public/js/config.js). It is intentionally sparse and optimized for repeated use rather than discovery.

| Capability | Current behavior | Upgrade requirement |
| --- | --- | --- |
| Room context | Eight room buttons select the active room; the selection is stored per browser. | Preserve per-panel context without introducing shared Home Assistant helper state. |
| Sonos grouping | The second row shows group membership. A tap joins or leaves a room; a room double-tap requests an all-join intent. | Preserve active, pending, unknown, failed, and stale feedback, including the intent-based all-join behavior. |
| Sonos playback | Group volume up/down, volume normalization, absolute low-volume double-tap, favorites, TV presets, play/pause, pause, and next. | Keep the one-tap paths and avoid opening media-browser dialogs for routine actions. |
| Now playing | Album art becomes the background and a scrolling banner displays track/station metadata and stale or intent status. | Retain glanceable metadata while bounding animation and network cost on the A7 processor. |
| Lighting | High, Medium, and Off target the active room; Off double-tap calls All Off. | Continue using the generated `script.fast_scene_*` entry points and preserve single-versus-double-tap safety. |
| Blinds | Four buttons request roller and blackout up/down operations for the active room. | Confirm the live contract, then expose it as Home Assistant `cover` entities or scripts before changing the UI. |
| LED wall | Living Room and Kitchen replace selected empty cells with Rainbow, Sparkle, and Tetris presets. | Expose stable Home Assistant actions while preserving the room-specific layout. |
| Printer | Kitchen shows a calendar shortcut that navigates to a printing preset and returns afterward. | Preserve the navigation flow or replace it only with a tested Home Assistant action that provides equivalent feedback. |
| Recovery | A hidden refresh action reloads the page. | Retain an obvious but unobtrusive recovery mechanism and add automatic stale/offline indication. |

The room context is the most important interaction to retain. It allows a small fixed set of controls to operate across the home without menus, scrolling, modal dialogs, or one dashboard view per room.

## Baseline technical findings

- The frontend combines jQuery, Bootstrap, FastClick, Underscore, and hand-written JavaScript. The stack is old, but its small, locally served output is one reason it remains usable on iOS 12.
- The layout depends on system emoji glyphs, so unsupported characters render inconsistently or not at all on the wall panels.
- Sonos state is polled every two seconds. Each interval requests room state, zones, and intent status separately through the Grid Dashboard and Sonos API add-ons.
- Lighting already has the desired Home Assistant boundary. The browser calls the Grid Dashboard scene route, which invokes generated `script.fast_scene_<room>_<preset>` wrappers. Preserve the dispatch and concurrency contract in [`operations/zwave-scene-ops.md`](operations/zwave-scene-ops.md).
- The live assessment found native `media_player` entities for all eight Sonos rooms, with standard join, unjoin, playback, volume, and `group_members` support. The current custom Sonos stack also contains important cache, stale-state, volume-normalization, and intent behavior documented in [`sonos/overview.md`](sonos/overview.md) and [`sonos/routing-guide.md`](sonos/routing-guide.md); do not remove it merely because native entities exist.
- The blind client posts to `/blinds-i2c/<room>_<blind>`, but repository inspection found no matching router mounted by the current Grid Dashboard server. Treat this as an unverified or orphaned contract until a live panel test establishes the intended behavior.
- The add-on currently enables unrestricted CORS and exposes an optional LAN port. That is broader than necessary for a fixed local control surface.
- The 2026-08-08 repository test run passed all 21 Grid Dashboard tests, TypeScript checking, and the add-on container build. The implementation is supportable enough to evolve incrementally.

## Dashboard alternatives considered

| Candidate | Fit for iPad mini 3 | Functional fit | Decision |
| --- | --- | --- | --- |
| Home Assistant Sections and Tile cards | Poor; inherits the moving HA frontend compatibility window | Moderate; good entity controls, but more chrome and navigation than the current surface | Build only as a secondary/future dashboard. See [views](https://www.home-assistant.io/dashboards/views/) and [cards](https://www.home-assistant.io/dashboards/cards/). |
| `button-card` plus `layout-card` | Poor on iOS 12 because both run inside the HA frontend | Good; supports fixed grids, double-tap, service calls, state styles, and templates | Preferred native approximation on supported hardware, using the fewest custom cards possible. See [`button-card`](https://github.com/custom-cards/button-card) and [`layout-card`](https://github.com/thomasloven/lovelace-layout-card). |
| Mushroom or Bubble Card | Poor; adds custom frontend JavaScript on top of HA | Moderate; polished entity cards but not a replacement for the room-context appliance model | Do not use for the legacy panels. Consider selectively on the future native dashboard only. See [Mushroom](https://github.com/piitaya/lovelace-mushroom) and [Bubble Card](https://github.com/Clooos/Bubble-Card). |
| Dwains Dashboard | Poor; the current generation requires a recent HA frontend | Low; optimized for automatic area/device discovery and navigation | Do not use for this control surface. See [Dwains Dashboard Next](https://github.com/dwainscheeren/dwains-dashboard-next). |
| AppDaemon HADashboard | Plausible, but must be proven on physical iOS 12 hardware | Good fixed-grid and wall-panel model; custom widgets would still be required | The only standalone alternative worth a prototype if the current UI becomes unmaintainable, but not a migration target now. See [HADashboard documentation](https://appdaemon.readthedocs.io/en/latest/DASHBOARD_INSTALL.html). |
| TileBoard | Historically suitable for old tablets | Good conceptual match | Do not migrate to it; the [TileBoard repository](https://github.com/resoai/TileBoard) is archived. |
| CasaBoard | Unproven on Safari 12 | Promising self-hosted builder, but kiosk/display behavior is still evolving | Reassess for supported hardware later, not for this upgrade. See [CasaBoard](https://casaboard.dev/). |

## Target interfaces and ownership

### Presentation layer

The Grid Dashboard remains responsible for:

- Fixed cell placement, local room selection, touch dispatch, and visible feedback.
- Local SVG or PNG icons and concise text fallbacks.
- A single compact read model representing active room, Sonos state, action/intent status, and backend availability.
- Navigating to another local UI only when the interaction genuinely requires it, such as the printer countdown page.

It must not own device identifiers, service sequencing, retry policies, or credentials beyond selecting a named dashboard action.

### Home Assistant action layer

Home Assistant should provide stable, named scripts or entities for dashboard operations:

- Keep `script.fast_scene_<room>_<preset>` and `script.fast_scene_all_off` as the lighting contract.
- Add or document named Sonos actions for group membership, all-join intent, favorite playback, TV presets, group volume changes, and volume normalization. These may initially delegate to the existing Sonos API where it provides required reliability behavior.
- Represent blinds as `cover` entities when accurate position/state is available; otherwise use named scripts with explicit up/down semantics.
- Represent LED-wall presets as scripts or button entities that delegate to the existing local API.
- Represent printing as a named action if Home Assistant can provide the same countdown, confirmation, and return behavior; otherwise retain a documented local navigation exception.

Action names are the public dashboard contract. Entity IDs and backend routes may change behind them without requiring cell configuration changes.

### State layer

Provide one compact Grid Dashboard state endpoint rather than three independent browser requests per polling interval. The response should include:

- Server observation time and overall freshness.
- The selected room's playback state, volume, metadata, and artwork reference.
- Sonos zones/group members and whether that observation is fresh, stale, or unknown.
- Active or recent long-running intent status, message, target, missing rooms, and failure state.
- Availability of optional capabilities such as blinds, LED wall, and printer.

Keep polling as the initial transport because it is simple and reliable on Safari 12. A push transport may be considered only after the polling version is stable and real hardware measurements show a meaningful benefit.

## Implementation phases

### Phase 0: Baseline and rollback

1. Capture screenshots and a cell/action inventory from every room context.
2. Exercise each visible action from a physical iPad and classify it as working, degraded, unused, or broken; explicitly resolve the blind controls before promising parity.
3. Record page-load time, steady-state request volume, command-to-feedback behavior, duplicate-action observations, and memory/reload failures on iOS 12.5.7.
4. Preserve the deployed add-on artifact and configuration needed to restore the current release.
5. Define a pilot panel and a direct URL or deployment switch that can return it to the previous dashboard without changing Home Assistant device logic.

### Phase 1: Presentation compatibility

1. Replace emoji with repository-owned icons that render locally without a font or network dependency. Include concise labels or accessible names for ambiguous symbols.
2. Preserve the 11-by-8 layout, landscape fit, large hit targets, room highlighting, and single/double-tap semantics.
3. Establish an explicit iOS 12 JavaScript/CSS build target. Reject emitted syntax or required web APIs that Safari 12 cannot execute.
4. Remove unused frontend libraries only when their behavior has been covered by tests on desktop and a physical iPad; do not perform a framework rewrite in this phase.
5. Add immediate pressed/pending feedback without treating a submitted command as successful until authoritative state arrives.

### Phase 2: Stable Home Assistant actions

1. Inventory every configured dashboard action and map it to a named Home Assistant script/entity or an explicitly retained adapter.
2. Keep the current fast-scene wrappers unchanged except where the established Z-Wave workflow requires a measured correction.
3. Introduce Sonos wrapper actions without removing the existing intent and stale-cache protections. Compare native Sonos behavior with the custom stack before choosing the implementation behind each wrapper.
4. Repair and migrate the blind contract, then add state/availability feedback where the underlying integration supports it.
5. Add LED-wall and printer contracts, retaining local adapters where Home Assistant would otherwise reduce functionality.
6. Change the frontend to call named actions rather than compose device-specific URLs.

### Phase 3: Consolidated state and reliability

1. Add the compact state endpoint and migrate the browser to one bounded poll cycle.
2. Prevent overlapping polls and discard out-of-order responses.
3. Distinguish stale, unknown, unavailable, pending, succeeded, failed, and timed-out states visually.
4. Ensure a failed optional subsystem cannot prevent lighting or other independent controls from rendering and operating.
5. Bound artwork size and marquee work so metadata cannot cause sustained CPU load or layout overflow.

### Phase 4: Native companion dashboard

1. Create a separate Home Assistant dashboard for supported phones, computers, and future tablets using the same named actions.
2. Start with native Sections, Tile, Button, Grid, and Media Control cards. Add `button-card` or `layout-card` only for behavior the native cards cannot reproduce.
3. Use room-specific views or another per-client mechanism; do not use one shared `input_select` whose room choice would couple every wall panel.
4. Treat this dashboard as a secondary client. Do not redirect the iPad mini 3 panels to it during this plan.

### Phase 5: Pilot and rollout

1. Deploy to one wall panel while the other panels remain on the previous version.
2. Run the full acceptance suite and observe the pilot for at least 48 hours of normal household use.
3. Review logs for duplicate actions, polling overlap, backend errors, reload loops, stale-state duration, and Sonos intent failures.
4. Roll out one remaining panel at a time, preserving immediate rollback until every panel completes the observation window.
5. Document the deployed dashboard version, browser constraints, recovery URL, and ongoing real-device smoke test.

## Browser compatibility requirements

- The supported wall-panel baseline is Safari/WebKit on iOS 12.5.7, not a current desktop browser running at an equivalent screen size.
- Serve only local JavaScript, CSS, icons, and fonts required for primary controls. External album art must fail closed to a neutral background.
- Do not require service workers, modern JavaScript modules without a proven fallback, container queries, unsupported CSS layout behavior, or newly introduced browser APIs.
- Preserve touch handling without double-firing synthetic click events. Single-tap controls must respond immediately; double-tap controls must cancel the pending single action exactly once.
- The logical landscape viewport must fit without vertical scrolling, accidental zoom, clipped hit targets, or dependence on browser toolbars being in one specific state.
- Desktop automation supplements but does not replace testing on at least one physical iPad mini 3.

## Security requirements

- Keep the panels and dashboard local-only. Do not expose the Grid Dashboard port or action endpoints to the public internet.
- Place legacy iPads on an appropriately restricted network segment. Permit only the local services and explicit artwork access required by the dashboard.
- Never store a Home Assistant long-lived access token, Supervisor token, webhook secret, or device credential in browser-delivered files.
- Authenticate Home Assistant calls in the server/add-on layer and allow only a fixed action catalog with validated arguments.
- Replace unrestricted CORS with the minimum origins and methods required by the supported access paths.
- Use POST for mutations, disable caching of action responses, encode route components, and prevent arbitrary URL proxying.
- Do not render untrusted metadata as HTML. Treat track, station, intent, and error text as plain text.
- Keep the current iOS/WebKit security limitation recorded as an accepted residual risk with network isolation as the compensating control.

## Test plan

### Automated tests

- Configuration validation: unique/in-bounds cells, valid room overrides, known icons, known action names, and complete room-to-lighting mappings.
- Touch dispatch: single tap, double tap, delayed single cancellation, FastClick/synthetic click behavior, and stale-event rejection.
- Action contracts: request method, action name, argument validation, error mapping, and no duplicate calls.
- State handling: fresh, stale, unknown, unavailable, malformed, delayed, and out-of-order responses.
- Sonos: join, leave, all-join intent, partial convergence, timeout, favorite, TV preset, volume actions, metadata parsing, and artwork failure.
- Lighting: every room's High/Medium/Off wrapper and All Off double-tap without also firing room Off.
- Optional services: blinds, LED wall, and printer available/unavailable behavior.
- Build gates: TypeScript/static checks, Safari 12 syntax target, unit suite, and Home Assistant add-on container build through the repository `just` workflows.

### Physical-panel acceptance

- Cold-load and reload the dashboard repeatedly on iOS 12.5.7 in the actual mounted orientation.
- Visit every room context and confirm icons, labels, active state, cell placement, and room-specific overrides.
- Exercise every working baseline control once and all double-tap controls multiple times while checking that exactly one intended action occurs.
- Verify Sonos group changes in both directions, all-join convergence, playback controls, favorites, volume behavior, metadata, stale state, and recovery after a speaker/API interruption.
- Verify representative High-to-Off lighting behavior through the fast scripts and confirm All Off follows the Z-Wave operational contract.
- Verify network loss, server restart, optional-service loss, recovery, and the manual refresh path.
- Leave the panel running through the 48-hour pilot and confirm there is no accumulating lag, frozen touch handling, runaway marquee, or reload loop.

## Migration and rollback

- Migrate one boundary at a time: presentation assets, named actions, then consolidated state. Do not combine a full UI rewrite with removal of the Sonos API or scene-dispatch changes.
- Preserve action compatibility during each phase so old and new dashboard builds can operate against the same backend during the pilot.
- Keep the previous deployable add-on artifact and configuration until the final panel completes its observation window.
- Roll back the frontend first when presentation or compatibility fails. Roll back an individual action adapter only when its backend contract is the fault.
- A rollback must not require editing light scenes, regrouping Sonos manually, or restoring unrelated Home Assistant configuration.

## Acceptance criteria

The upgrade is complete only when all of the following are true:

- The physical iPad mini 3 acceptance suite passes on iOS 12.5.7.
- The upgraded UI provides parity for every action classified as working in Phase 0; removed controls were explicitly confirmed unused or broken and documented.
- No single tap or double tap produces a duplicate or unintended companion action.
- Room context remains local to each browser and survives a normal reload.
- Lighting continues through the generated fast-scene scripts and passes representative live High/Off and All Off validation.
- Sonos grouping, all-join intent, playback, favorites, volume, metadata, stale state, and failure recovery remain available from the one-screen UI.
- Loss of Sonos, LED wall, printer, blinds, or artwork does not block unrelated controls.
- Primary assets are local, icons do not depend on emoji coverage, and no browser-delivered secret is present.
- The steady-state browser performs one bounded state poll at a time and does not issue duplicate action requests.
- Automated tests, TypeScript/static checks, the Safari 12 compatibility gate, and the add-on container build pass.
- One-panel rollout and 48-hour observation complete without a critical regression, followed by successful staged rollout to the remaining panels.
- The secondary native dashboard can invoke the same public Home Assistant actions on supported hardware.
- Rollback to the previous Grid Dashboard release has been exercised or demonstrated from retained artifacts.

## Explicit non-goals

- Replacing the iPad mini 3 units as part of this plan.
- Replacing the Home Assistant administration UI or making it work on iOS 12.
- Removing the custom Sonos API before native Home Assistant behavior has demonstrated equivalent reliability and feedback.
- Changing Z-Wave scene concurrency or pacing without the measurements and workflow required by [`operations/zwave-scene-ops.md`](operations/zwave-scene-ops.md).
- Turning the wall panel into a comprehensive monitoring, history, configuration, camera, or automation-editing interface.
- Adopting a visual framework or third-party dashboard solely for aesthetic modernization.

## Assumptions

- The installed wall panels remain iPad mini 3 units running iOS 12.5.7 and are expected to remain in service.
- The fixed, utilitarian interaction model is more important than visual novelty or automatic entity discovery.
- Home Assistant remains the source of truth for device state and automation, while local add-ons may remain behind stable adapters where they provide required functionality.
- Lighting fast-scene scripts and their Z-Wave dispatch contract remain authoritative.
- A physical panel is available for every compatibility and rollout gate; emulation alone is insufficient.
