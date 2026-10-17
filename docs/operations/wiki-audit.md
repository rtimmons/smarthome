# Wiki assessment — October 16, 2026

The wiki has a useful household/maintainer split and a sound static publication
boundary. The audit found substantive factual mistakes and freshness gaps, which
are corrected in this revision. Mechanical reference material now comes from
repository configuration at build time; explanations and dated operational
evidence remain authored.

This was a repository and rendered-site assessment. It did not query household
services, verify passwords, operate devices, restore backups or publish a release.

## Assessment

| Criterion | Finding and improvement | Remaining limit |
| --- | --- | --- |
| Correctness | Corrected snapshot-service purpose, MongoDB data path and network exposure, media retry wording, and Filex backup coverage. Generated scenes now use production target selection. | Repository declarations and dated evidence cannot establish current runtime state. |
| Usability | Grouped household navigation; split reference tables into focused pages; generated a runbook directory; enabled the glossary's definition-list markup. Desktop and 390-pixel navigation were checked. | Wide technical tables scroll horizontally; physical-phone and assistive-technology acceptance were not performed. |
| Utility | Added a symptom-first entry table, switch/scene control reference, effective scene states, explicit printer entry point, and recovery-by-loss table. | Application access still depends on the existing network and saved credentials. |
| Completeness | Every household page, imported runbook and discovered add-on has an owner. Added access, account, Filex, storage, checkout and recovery runbooks to the local site. | This is a curated field guide, not an inventory of every Home Assistant UI integration or every repository document. |
| Maintainability | Build-time tables, counts, titles, navigation and review report share canonical inputs. Missing watch paths and missing/duplicate ownership fail checks. | A successful fingerprint review does not prove the author's explanation is correct. |

## Corrected findings

1. **Wrong service purpose.** The climate guide and root overview called
   `snapshot-service` a camera helper. Its [server](../../snapshot-service/src/server.ts)
   returns a fixture summary and registers receipt-analysis routes. The service
   now belongs to the printing guide, and its [README](../../snapshot-service/README.md)
   separates implemented endpoints from former proposals. No live calendar,
   weather, camera or OpenAPI endpoint is claimed.
2. **Incorrect database guidance.** [MongoDB's entrypoint](../../mongodb/run.sh)
   uses `/data`, while its README said `/data/db`. Its manifest maps host port
   27017, contradicting the statement that only other add-ons could reach it.
   The guide now distinguishes loopback development from declared production
   exposure, and the local 8.0 binary from the production 8.2 image requirement.
   This audit did not test the actual firewall or listener.
3. **Misleading scene reference.** Declared members and default opt-in flags did
   not reveal diagnostic endpoints, exclusions or effective all-off membership.
   The exporter now calls `generateSceneTargets` and the production script-ID
   helper. It includes desired states and omitted declarations. Temporarily
   removed inventory stays visible; that marker is not falsely treated as a
   static scene exclusion.
4. **Missing control reference.** Switch gestures and webhook-driven controls
   now come from the automation registry. The generated mode uses the same
   `getEffectiveAutomationMode` function as deployment, so scene callers display
   `restart` even when their source declaration says `single`.
5. **Conflicting media retry advice.** The interactive-search instructions now
   distinguish manual release choices from automatically selected releases,
   matching [native media policy](../../usenet-infra/docs/native-media.md).
6. **Stale backup statements.** Filex's runbooks now describe its nested encrypted
   bundle and subsequent recurring off-host settings coverage. Media and staging
   exclusions remain explicit; dated recovery checkpoints are not refreshed.
7. **Review gaps.** Guide prose and imported runbooks previously did not
   necessarily affect a component's fingerprint. Both now participate directly.
   Stale package paths were removed/repaired; printer Python lockfiles and the
   snapshot TypeScript source tree are watched. Unmatched watch patterns fail.
8. **Duplicated navigation.** Imports and the long hand-maintained runbook menu
   are replaced by per-component runbook ownership. Titles and the local runbook
   directory are generated from that catalog and source headings.

## What is generated

| Output | Canonical build input |
| --- | --- |
| Add-on status, ingress, network mode, port mappings, dependencies | Discovered `*/addon.yaml` manifests |
| Device inventory, exclusions and all-off membership | `devices.ts`, `scenes.ts`, production scene-target generation |
| Scene scripts, effective targets and desired states | `scenes.ts` and production scene helpers |
| Control triggers, actions and effective modes | `automations.ts` and production automation-mode helper |
| DNS records, resolvers, upstreams and filter flags | `network-infra/dns/policy.json` |
| Runtime pins | `.nvmrc` and `.python-version` |
| Page ownership, review dates/reasons and source coverage | `wiki/components.json` and `wiki/reviews.json` |
| Runbook directory and navigation titles | The component catalog and Markdown headings |
| Build provenance, source fingerprint and deployment receipt view | Existing build/publication metadata |

The build never reads private Home Assistant storage, credential files, live
media listings or application APIs to fill these tables. Webhook IDs, arbitrary
action payloads and device-registry IDs are omitted from the control export.
Canonical explanations are copied, not independently rewritten during a build.

## Validation and limits

- `just wiki-check`: strict static build, rendered links/assets/fragments,
  legacy Usenet anchors, 25 wiki tests and three DNS policy tests passed.
- The Home Assistant configuration test recipe passed 90 generator tests,
  nine driver/route tests and its shell regression checks using the pinned Node
  wrapper. New tests cover actual all-off membership, exclusions, protected
  power, absent inventory and sanitized control output.
- Browser checks passed for desktop rendering, local search finding the new
  snapshot runbook, and 390-pixel mobile navigation into the control reference.
- Live DNS/DHCP adoption and gateway migration remain as documented in the
  [network guide](../../wiki/content/network.md). No new acceptance is implied.
- Manual YAML, package and UI-owned automation behavior still needs its runbook
  explanation. Full Home Assistant recovery, NAS-originals protection and
  physical client playback retain their existing evidence limits.
- External repository links and service shortcuts were not tested as live
  availability checks. Build validation checks local pages, not remote servers.

See [wiki operations](wiki.md) for authorship, review and publication. Keep the
[generated coverage report](wiki-reference:coverage) as the current inventory;
the counts and outcomes in this assessment describe this audit only.
