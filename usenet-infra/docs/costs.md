# Costs

Prices were checked against official product or registration pages on
2026-09-10. This is a planning snapshot, not a quote. Taxes, exchange-rate
effects, card fees, promotional renewal changes, and metered overages are not
included unless stated.

Immediately before the provisioning checkpoint, authenticated read-only API
checks confirmed the account's USD pricing: CX43 is $18.49/month, a Primary
IPv4 is $0.60/month, and the initial BX11 in `hel1` is $4.00/month with a $0.00
setup fee. Gross and net were equal and the pricing response reported a 0% VAT
rate for this account. Recheck if the plan, location, tier, or account changes.

## Known recurring infrastructure (USD)

| Item | Billing basis | Monthly USD | Source |
| --- | --- | ---: | --- |
| Hetzner CX43, Germany/Finland | Hourly, capped monthly; price excludes IPv4 and VAT | $18.49 | [Hetzner Cloud price adjustment effective 2026-06-15](https://docs.hetzner.com/general/infrastructure-and-availability/price-adjustment/) |
| Hetzner Cloud Primary IPv4 | Per address | $0.60 | [Hetzner IP pricing](https://docs.hetzner.com/general/infrastructure-and-availability/ipv4-pricing/) |
| Hetzner BX11 Storage Box, 1 TB | Hourly, capped monthly; account-specific USD price | $4.00 | [Hetzner BX11](https://www.hetzner.com/storage/storage-box/bx11/) |
| **Initial Hetzner subtotal** |  | **$23.09** |  |

The explicit Primary IPv6 in Terraform is free according to Hetzner's IP
pricing page. The CX43 is the cost-optimized 8-vCPU, 16-GB RAM, 160-GB NVMe
choice; cost-optimized capacity can be temporarily unavailable. A move to a
newer or dedicated CPU tier would materially change this table and requires a
new price check.

## Storage capacity ladder

| Tier | Capacity | Role | Price treatment |
| --- | ---: | --- | --- |
| BX11 | 1 TB | Approved initial tier | $4.00/month; $0.00 setup for this account in `hel1` |
| BX21 | 5 TB | First planned in-place upgrade | Recheck the authenticated account price before applying |
| BX31 | 10 TB | Second planned in-place upgrade | Recheck the authenticated account price before applying |
| BX41 | 20 TB | Eventual target | Currently verified at $46.00/month and $0.00 setup for this account in `hel1` |

Capacity warns at 80%, and the next tier must be reviewed and applied before
90%. Hetzner officially supports scaling a Storage Box and permits downgrade
only when used space is below the smaller tier; snapshots consume the same
capacity. The pinned hcloud provider changes `storage_box_type` through an
in-place API action rather than replacement. Sources:
[Hetzner scaling rules](https://docs.hetzner.com/storage/general/which-storage-is-right-for-me/),
[snapshot accounting](https://docs.hetzner.com/storage/storage-box/snapshots/),
and the
[provider 1.68.0 update implementation](https://github.com/hetznercloud/terraform-provider-hcloud/blob/v1.68.0/internal/storagebox/resource.go#L432-L447).

The intermediate-tier prices are deliberately not guessed. A type change takes
effect against the live account and location, so the reviewed plan and official
Hetzner API price are the purchase checkpoint. At the currently verified BX41
price, the eventual 20 TB Hetzner subtotal would return to $65.09/month.

## Eweka advertised offer and account confirmation (EUR)

| Item | Charge | Monthly equivalent | Source |
| --- | ---: | ---: | --- |
| Eweka unlimited advertised offer; account existence confirmed | €104.85 prepaid for 15 months advertised; actual charge/tier unverified | €6.99/month advertised equivalent | [Eweka 15-month checkout](https://www.eweka.nl/en/checkout?p=15mo) |

The user has confirmed that the Eweka account exists. Its final charged tier,
amount, applicable VAT, commitment and renewal details have not yet been
independently verified; the public offer is not evidence of those account
terms. EUR is intentionally not converted to USD here, and an effective monthly
price is not monthly billing. SABnzbd's saved primary-server configuration and
authenticated built-in connection test have now passed independent live
verification. That operational result does not verify billing terms.

## Deferred fill-provider reference

| Item | Historical quote | Treatment | Source |
| --- | ---: | --- | --- |
| UsenetExpress 500 GB block | $20.00 on 2026-09-10 | Deferred by the user; no current purchase or required budget allocation | [UsenetExpress selected block](https://members.usenetexpress.com/signup/9Jq5Pvyj/?product_id_page-0%5B%5D=9-13&ret=deep) |

Eweka is the sole provider for the current baseline. A fill block is optional
only if genuine missing articles or a completion gap demonstrates a need.
The historical checkout showed a one-time purchase, while current
non-expiration was unverified. Recheck all terms and pricing if revisiting it.
No block amortization is included in the current required budget.

The OliveTin dashboard and its catalog backend run on the existing QNAP; this
design adds no hosted dashboard subscription. NAS power, disk wear, and home
Internet are not newly priced here. HybridMount is optional: QNAP documents two
free third-party File Cloud Gateway connections, but their availability on this
NAS must be checked before experimenting. No extra license is approved. See the
[QNAP HybridMount guide](https://www.qnap.com/en-us/how-to/tutorial/article/hybridmount-quick-start-guide).
The actual WebDAV gateway wizard was inspected and the route was not adopted;
no connection, license purchase, or cache allocation was created.

## Paid indexer subscriptions

| Item | Verified payment/status | Monthly equivalent | Source |
| --- | --- | ---: | --- |
| NZBGeek, one year | User confirmed $12 USD paid through official Stripe checkout; independent account readback active through 2027-09-13 22:01:53 UTC | $1.00 | Authenticated [GeekHub](https://geek-hub.com.au/) checkout and [NZBGeek](https://nzbgeek.info/) account readback on 2026-09-10 |
| NZBFinder Pro | User confirmed payment; authenticated Pro badge observed. Plan advertises $30/year, but currency code and final charge are unverified; expiry/renewal unknown | $2.50 advertised equivalent, currency code unverified | Authenticated [NZBFinder](https://nzbfinder.ws/) plan/account page on 2026-09-10 |

NZBGeek's annual charge is paid upfront. Automatic rebilling and the eventual
renewal price have not been independently confirmed; the monthly equivalent
does not establish monthly billing or automatic renewal. The account guidance
says renewing before expiry extends the existing subscription period.

NZBFinder Pro advertises 20,000 API requests and unlimited downloads, with
counters resetting 24 hours after each request. Its $30/year display is not
evidence of the final charge or of USD denomination. Do not add it to the USD
subtotal until its charge currency is confirmed. No further purchase is
pending; private API setup and the live Prowlarr test have passed, while the
missing billing details remain unverified.

## Unused alternative

| Item | Current status | Budget treatment | Source |
| --- | --- | --- | --- |
| DrunkenSlug | Last signup observation was closed; latest automated refresh returned HTTP 403 | $0; do not budget or seek an invitation workaround | [DrunkenSlug registration](https://drunkenslug.com/register) |

## Budget assessment

The known monthly costs and prepaid equivalents cannot honestly be collapsed
into one currency:

```text
USD equivalent = $23.09 initial Hetzner
               + $1.00 NZBGeek (paid $12 for one year)

EUR equivalent = €6.99/month advertised Eweka offer (account charge unverified)

NZBFinder      = $2.50/month advertised equivalent (currency/charge unverified)
```

The known initial USD subtotal including NZBGeek's annual equivalent is
$24.09/month, inside the prior $75–90/month target and leaving a nominal
$50.91–$65.91 USD margin before currency conversion. Eventual BX41 capacity
reduces that margin to $8.91–$23.91 at the currently verified price.
Neither figure proves the completed service fits the target: Eweka is
denominated in EUR, NZBFinder's charge currency is unresolved, and taxes/FX
may apply.
Keep the overall budget status **uncertain** until Eweka's actual account terms
and NZBFinder's actual charge/currency are confirmed. Both paid indexers now
pass their private Prowlarr connection tests.
Re-run official price checks immediately before ordering or changing Storage
Box tier.
