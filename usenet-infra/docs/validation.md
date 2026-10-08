# Validation

Run `just --justfile usenet-infra/Justfile --working-directory usenet-infra test`
from the repository root. It checks unit behavior, shell/YAML syntax, Ansible
playbooks and secrets. The full-history scan reports the two documented
[historical RSA keys](security-findings.md); report that separately from current
source/index checks. Do not waive findings or rewrite history to pass validation.
Offline checks do not establish live deployment or media acceptance.

## Recorded operational acceptance

The approved plan completed October 8, 2026. These are dated observations, not
promises about future health. Preserve the immutable records in `recovery/`.

| Area | Evidence and limit |
| --- | --- |
| Native acquisition | [Native acceptance](../recovery/drills/native-cutover-20260920.json): fresh movie/episode imports, source cleanup, Plex discovery and scoped restart passed. RSS/direct carts stay off; failed releases need explicit review. |
| NAS copying | [Movie copy](../recovery/drills/native-copy-live-20260913.json) and [September closure](../recovery/drills/closure-20260922.json): selected movie/TV copies passed SHA-256, safe repeat and exact-file Plex indexing. TV required a general-library scan. |
| Playback/privacy | User confirmed Roku and Apple TV playback and restricted-profile privacy. This is not an agent-run codec/subtitle matrix. |
| Seerr/Filex | [October closure](../recovery/drills/closure-20261008.json): user confirmed both browser sign-ins. Earlier Seerr 2160p acquisition passed after a manually selected alternate; automatic failed-release recovery is not proven. |
| Repair capacity | An 80 GiB PAR2 repair and two concurrent 50 GiB expansions passed. The latter peaked at 200.22 GiB with 90.97 GiB free. This does not cover arbitrary expansion or concurrent 100 GiB repairs. |
| Configuration recovery | October cloud archive independently restored 785 files, five databases, all 44 journals and both Filex bundles. Recurring off-host NAS/Plex settings readback and isolated restores passed. |
| Replacement startup | Isolated cloud startup, authenticated APIs, reboot and storage-loss guards passed using empty read-only fixtures. Disposable resources were removed. Live acquisition, canonical writes, NAS/VPN integration and replacement NAS boot were outside the drill. |

NAS originals, artwork and installation binaries are excluded from the chosen
settings-only backup scope. Do not infer whole-NAS protection from settings
restore. New work that changes these boundaries requires its own relevant checks;
do not rerun acquisitions, purchases or deployment merely to reproduce a receipt.
