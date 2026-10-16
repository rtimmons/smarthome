# Usenet MCP: requests, downloads, library, and NAS copies

## Summary

Build a local Python MCP server under `usenet-infra`, launched through a root `just usenet-mcp` recipe using stdio. It will support desktop agents without exposing a new network service.

Cover the full workflow: Seerr requests → SAB downloads → Arr imports → canonical storage → optional NAS copies → Plex availability.

## Capabilities and interfaces

Expose focused tools with typed inputs and structured results:

| Area | Tools and behavior |
|---|---|
| Overview | `get_status`: active work, failures, pauses, storage headroom, and service availability. |
| Downloads | `list_downloads`, `get_download`: queue/history, speed, ETA, repair/unpack progress, and linked import status. |
| Diagnosis | `diagnose_item`: source-backed explanation of delays or failures, with suggested actions; never automatically repair. |
| Discovery | `search_media`, `get_media`, `list_requests`: movies, shows, seasons, episodes, existing copies, and pending requests. |
| Acquisition | `request_media`: movies/seasons through Seerr; `search_episodes`: explicit searches for selected existing Sonarr episodes. |
| Queue control | `control_download`, `control_queue`: job/global pause and resume, priority, queue ordering, and speed limit. Explicit target scope is required. |
| Recovery | `retry_download` and `search_replacement`: distinct actions for retrying the same job or an explicit Arr replacement search. |
| NAS copies | `start_nas_copy`, `get_operation`: reuse native/catalog copy commands and their verification receipts. |
| Plex | `get_availability`, `refresh_library`: query or scan only general libraries 2–5. Availability means indexed, not proven playback. |
| Removal | `preview_removal`, `execute_removal`: cancel jobs, delete partial data, evict owned NAS copies, or delete selected canonical media. |

Results include stable source IDs, observation timestamps, source-specific errors, and links to existing interfaces. Lists are paginated. Missing or unreachable data is reported as unknown, never as an empty queue or zero speed.

Correlate records using native identifiers and download IDs. Do not silently join unrelated items by similar titles.

## Implementation and action behavior

- Use the official Python MCP SDK with locked dependencies and the repository’s pinned Python runtime. Return both readable summaries and structured data, following the [SDK’s structured-output interface](https://github.com/modelcontextprotocol/python-sdk/blob/main/docs/servers/structured-output.md).
- Use existing dedicated SSH identities and pinned hosts. Add a constrained remote adapter for application API calls; credentials remain on their hosts. Access Seerr through cloud-host loopback, preserving its proxy authentication policy.
- Reuse existing NAS copy/eviction implementations, including shared locking, ownership checks, reserves, checksums, and atomic publication. Run long operations independently of the MCP connection and return durable operation IDs.
- Persist private operation receipts outside tracked source. Record each mutation’s requested scope and verified outcome. After a timeout, reconcile native state before retrying; report uncertain outcomes rather than risking duplicate requests.
- Preserve manual pauses. A job resume does not resume a globally paused queue. Replacement searches operate only on explicitly selected media; blocklisting a release is an explicit option.
- Keep existing quality profiles, release limits, storage reserves, import ownership, and disabled automatic acquisition policies. Individual episode searches do not introduce future scheduling.
- Use supported native APIs for queue and media actions, validated against deployed versions; reference the [SAB API](https://sabnzbd.org/wiki/advanced/api) and [Sonarr API](https://sonarr.tv/docs/api/).

**Removal contract:** require explicit selection of canonical storage, NAS copies, or both. Preview resolves exact IDs, files, shared episode files, monitoring changes, and expected effects. Execution revalidates that selection and rejects stale previews.

An unambiguous user request authorizes execution without another confirmation. Ambiguous copy selection requires clarification. Cancellation and partial-file deletion remain separate choices.

Canonical deletion uses Arr APIs and unmonitors affected media to prevent unintended reacquisition. Preserve legacy catalog objects and shared hardlinks; report surviving copies without promising reclaimed space. NAS eviction uses ownership receipts. Version one retains the existing whole-title NAS eviction granularity and rejects requests that would silently remove additional episodes.

Multi-service removals report each step separately; they are not atomic. Never empty Plex trash automatically.

## Validation and delivery

- Test MCP initialization, tool schemas, structured responses, and stdout protocol cleanliness.
- Use synthetic fixtures for queue states, ambiguous matches, partial outages, failed imports, duplicate requests, manual pauses, and uncertain mutation outcomes.
- Test stale removal previews, multi-episode files, copy ownership changes, surviving hardlinks, and partial completion across services.
- Verify copies survive client disconnects and retain existing NAS safety checks.
- Test credential redaction and exclusion of private Plex library 1. Keep real media identifiers out of committed fixtures, documentation, and receipts.
- Run infrastructure tests and `just wiki-check`; report the documented historical secret-scan findings separately.
- Deliver the launcher, deployment recipe for remote adapters, client configuration example, tool usage guidance, and updated canonical runbooks. Validate live reads first; do not acquire or delete real media merely to test installation.

## Defaults and boundaries

- Single-user, local desktop MCP; no public endpoint or autonomous monitoring.
- On-demand actions only, with explicit user intent for mutations.
- No arbitrary shell/API passthrough, configuration administration, service restarts, filesystem browsing, or canonical legacy-catalog deletion.
- No changes to backup policy, retired workers, private Plex access, or automatic upgrade/RSS behavior.
