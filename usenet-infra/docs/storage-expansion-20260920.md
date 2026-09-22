# Storage expansion — approved and deployed September 20, 2026

The user approved the proposal and deployment completed: the existing Storage Box
is now **BX21 (5 TiB)** and a **300 GB cloud volume** backs the incomplete/repair
spool. The VM remains CX43. The recurring catalog increase is **$32.01/month**:
$9 for BX21 and $23.01 for the volume (USD, account VAT 0%). Pricing was refreshed
through the authenticated API before applying the reviewed plans.

At 18:03 UTC, the actual mounted filesystems had **291.18 GiB free locally** and
**4.06 TiB free remotely**. Both observed-workload shortfalls are zero. Only
535 incomplete-spool files (28,639,139 bytes) were copied; complete SHA-256 and
metadata inventories matched, and the original spool remains intact. The
Storage Box identity and all canonical paths were retained.

Verification passed a 128 MiB synthetic PAR2 repair with independent SHA-256,
fresh hardlink probes as both Arr application users, NAS reader write/delete
refusal, missing-mount startup refusal, protected empty mountpoints and scoped
service restart. Queue/history, journals, holds and original operating settings
were preserved. This is storage acceptance, not fresh movie/TV native acceptance.
See the [sanitized receipt](../recovery/drills/storage-expansion-20260920.json)
and [operating/recovery runbook](repair-spool.md).

Private rollback settings, Terraform state, reviewed/applied plans and operational
evidence are in ignored `build/storage-expansion-20260920/`. The Storage Box plan
updated only its tier; the volume plan created only the volume and attachment.
The reader-account Samba drift from the full plan remains outside this change.
The volume has provider deletion protection and Terraform `prevent_destroy`;
automount was disabled so formatting could be bound to the verified blank device.
Do not apply the older saved proposal plans or repeat provisioning.

## Original measured need (before expansion)

Read-only live preflight at 17:17 UTC found:

| Filesystem | Available | Required for observed workload | Shortfall |
| --- | ---: | ---: | ---: |
| VM incomplete/repair | 118.20 GiB | 184.28 GiB | 66.09 GiB |
| Storage Box staging/library | 62.85 GiB | 172.80 GiB | 109.96 GiB |

The largest recorded download is 74.64 GiB; the largest journal source inventory
is 68.90 GiB. Local sizing includes the download and a full PAR2 replacement.
Remote sizing includes completed output and a complete import-copy fallback.
Both include the existing 30 GiB reserve and a proposed 5 GiB planning margin.
Hardlink success is useful but does not remove the copy allowance.

Proposed initial envelope: one release of at most 100 GiB downloaded and at most
100 GiB unpacked, requiring at least 235 GiB free on the spool and 235 GiB free
on staging/library before starting. A 300 GB volume provides headroom even when
budgeted conservatively as decimal GB, subject to its measured formatted capacity
and the size of preserved spool data. Actual NZB size does not bound archive
expansion; this envelope and the means of enforcing it still require validation.
Do not enable unrestricted concurrent requests on the strength of these numbers.

## Alternatives considered before approval

Prices came from authenticated, read-only Hetzner product/pricing API responses
on September 20. The account pricing response reports USD and 0% VAT. Raw
noncredential quotes are preserved privately in
`build/native-cutover/expansion-prices.json`. The final quote was refreshed before provisioning; these remain catalog rates,
not a statement of invoiced prorations.

| Option | Quote | Operational effect |
| --- | ---: | --- |
| Previous BX11, 1 TiB | $4/month | Replaced by BX21; was 93.9% used |
| BX21, 5 TiB | $13/month, $0 setup | +$9/month; in-place upgrade; roughly 4.06 TiB free at current use |
| Keep CX43, add 300 GB volume | $0.0767/GB-month = $23.01/month | Move only the incomplete spool; preserves VM size and root disk |
| Rescale CX43 to CX53, 320 GB primary disk | $34.99/month for CX53 | +$16.50/month against current CX43 catalog price of $18.49; actual delta depends on existing billing |

BX21 plus the volume adds $32.01/month. BX21 plus CX53 would add $25.50/month
against the current catalog baseline, but the API reports CX53 unavailable in
the listed European locations. Rescale eligibility must be checked separately;
availability is not promised. Enlarging its primary disk also prevents later
return to a smaller-disk plan. A volume avoids that primary-disk commitment and
does not require extra CPU/RAM, but adds a spool-mount dependency and needs a
representative repair/performance test.

The Storage Box upgrade preserves canonical paths; the proposal does not migrate
or duplicate the media library. Hetzner documents in-place Storage Box scaling.
Primary disk expansion requires server rescaling and is not shrinkable. See
[Storage Box tiers/scaling](https://www.hetzner.com/storage/storage-box/),
[server disk rules](https://docs.hetzner.com/cloud/servers/faq/#is-it-possible-to-downgrade-the-disk),
[current cloud prices](https://docs.hetzner.com/general/infrastructure-and-availability/price-adjustment/)
and the [pricing API](https://docs.hetzner.cloud/reference/cloud#pricing).

## Subsequent native cutover

The user accepted native Arr import and cleanup and authorized random fresh
movie/episode selection. Native import/source cleanup, an 80 GiB reconstruction
with independent SHA-256 and a scoped service restart passed after this storage
checkpoint. The [cutover record](native-cutover.md) contains final acceptance and
current operating controls. This dated storage receipt preserves its original
baseline; do not reinterpret its active hybrid timers as current configuration.
