# Printing labels

Use [the HTTPS printer](https://printer.home.rytim.com/) for browser access with Ryan’s Authelia MFA. Existing LAN QR links, HA print commands and ingress remain unchanged. Do not use print-triggering URLs as health checks.

The printer service renders and sends labels to the Brother QL-810W. Its reserved address is `192.168.1.192`, using raw printing on TCP port 9100. The printer belongs to the trusted network; the restricted print-client network is for request clients, not the printer itself.

## Daily use

Open **Printer Service** from Home Assistant’s sidebar and choose **PNG Upload** to preview, print, or inspect saved labels. From the repository, `just print-check <file.png>` performs a preflight without printing; `just print <file.png>` prints. Select the intended label dimensions before sending a job.

## If a label does not print

Check power, loaded media, and printer reachability first. Distinguish an image-rendering error from a network or hardware error. Do not repeatedly resubmit an uncertain job: it may already be queued.

The printer service listens on port 8099. The restricted VLAN is allowed to reach that service only; hosting the wiki must not broaden those rules.

## Configuration and recovery

The add-on manifest and printer service settings own its endpoint and runtime configuration. Rendering requires its documented fonts and graphics libraries, so validate with the repository’s container preflight rather than assuming a host-only render represents production.

Printer source is maintained in a separate private repository at `smarthome/printer`.
Restore both source checkouts before testing or deployment. The root `just` commands
still build and test the combined workspace; printing and saved-label behavior are unchanged.

See the [printer guide](../../printer/README.md) and [QL-810W troubleshooting](../../printer/docs/ql810w-troubleshooting.md). Restore saved service configuration and the fixed address before changing application targets.

## Daily summaries and receipt checkboxes

`snapshot-service` serves a fixture-based daily summary for print layouts and accepts receipt photos for checkbox analysis. Its `/snapshot` response is sample data, not current weather, calendar or camera information. See the [snapshot service guide](../../snapshot-service/README.md) for the implemented endpoints and limits.

[Generated service settings](wiki-reference:services) list ports, sidebar access and declared dependencies, including MongoDB.
