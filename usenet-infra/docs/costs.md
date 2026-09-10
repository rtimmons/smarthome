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

## Known subscription (EUR)

| Item | Charge | Monthly equivalent | Source |
| --- | ---: | ---: | --- |
| Eweka unlimited | €104.85 prepaid for 15 months | €6.99/month | [Eweka pricing](https://www.eweka.nl/en/pricing) |

EUR is intentionally not converted to USD here. Confirm the checkout total,
applicable VAT, commitment, and renewal price before purchase; a monthly
equivalent is not the same thing as monthly billing.

## One-time and usage-dependent purchases

| Item | Expected charge | Treatment | Source |
| --- | ---: | --- | --- |
| UsenetExpress 500 GB block | $20.00 one time | Not recurring until depleted; checkout price still needs confirmation | [UsenetExpress plans](https://www.usenetexpress.com/plans/) |

Do not count the block as a fixed monthly subscription. Once real consumption
is known, report its effective cost as `$20 / months until replacement`.

## Not yet priced

| Item | Current status | Budget treatment | Source |
| --- | --- | --- | --- |
| NZBGeek | Registration page reachable, but paid tier and renewal price still require verification after login | Unknown recurring cost | [NZBGeek registration](https://nzbgeek.info/register.php) |
| NZBFinder | Candidate replacement indexer; paid tier and renewal price still require verification after login | Unknown recurring cost | [NZBFinder registration](https://nzbfinder.ws/register) |
| DrunkenSlug | Registration is closed | $0; do not budget or seek an invitation workaround | [DrunkenSlug registration](https://drunkenslug.com/register) |

## Budget assessment

The known recurring total cannot honestly be collapsed into one currency:

```text
USD recurring  = $23.09 initial Hetzner
               + confirmed USD indexer charges
               + usage-based block-account amortization

EUR equivalent = €6.99/month Eweka
               + any EUR-denominated indexer charges
```

The initial Hetzner subtotal is inside the prior $75–90/month target, leaving a
nominal $51.91–$66.91 USD margin before any currency conversion. Eventual BX41
capacity reduces that margin to $9.91–$24.91 at the currently verified price.
Neither figure proves the completed service fits the target: Eweka is
denominated in EUR, both indexer costs are unresolved, the block replacement
interval is unknown, and taxes/FX may apply. Keep the overall budget status
**uncertain** until the Eweka, NZBGeek, NZBFinder, and UsenetExpress checkout
screens have been confirmed. Re-run the official price checks immediately
before ordering or changing Storage Box tier.
