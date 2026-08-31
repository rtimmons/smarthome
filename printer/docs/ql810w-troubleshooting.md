# Brother QL-810W Troubleshooting Guide

## Agent Notes

- Follow the repo-wide expectations in `../../AGENTS.md#ground-rules`.
- Read the current [UniFi Network Setup and Tuning](../../docs/operations/unifi-network-setup.md) baseline before changing Wi-Fi, multicast, DHCP, or firewall settings.
- Preserve a failure before saving or reprovisioning anything in UniFi. Make one coherent change and verify both controller and effective device state.

This guide troubleshoots the Brother QL-810W used by the Home Assistant printer add-on. It is intentionally specific to the current network instead of presenting generic UniFi settings as universal fixes.

## Current Known State

The controller's last retained printer record on 2026-08-31 was:

| Property | Observed value |
| --- | --- |
| Hostname | `BRWACF23C3213C4` |
| MAC | `ac:f2:3c:32:13:c4` |
| Address | `192.168.1.192` |
| SSID/radio | `sintheta`, U7 Pro XG, 2.4 GHz |
| Routed network | `Default` / `192.168.1.0/24` |
| Fixed-IP reservation | **Not configured** |
| Add-on target | `tcp://192.168.1.192:9100` |

The missing reservation is a configuration risk: `printer/addon.yaml`, the service default, and the operator README all expect `.192`, but DHCP is free to assign another address. The recommended first change is to reserve `192.168.1.192` for the MAC above, renew/reconnect the printer, and verify the lease before diagnosing intermittent Wi-Fi.

## Do Not Put the Printer on `sintheta-printer`

`sintheta-printer` is the restricted network for untrusted **print-request clients**. It permits those clients to call only Home Assistant TCP/8099 and blocks other LAN, gateway, client-to-client, and Internet traffic.

The Brother printer must accept a connection initiated by Home Assistant on TCP/9100, so it should remain on `Default`, preferably through the 2.4 GHz compatibility SSID `sintheta-iot`. Moving the Brother itself to `sintheta-printer` would put it on the wrong side of the firewall and client-isolation design.

## Quick Diagnostics

First find the live address in **UniFi Network > Client Devices** by searching for the hostname or MAC. Do not assume `.192` until the reservation exists and the current lease confirms it.

```bash
PRINTER_IP=<current-printer-ip>

# Basic reachability; sleep state may suppress ping.
ping -c 3 "$PRINTER_IP"

# The add-on's required raw-print service.
nc -z -v -w 3 "$PRINTER_IP" 9100

# Local address-resolution evidence.
arp -a | grep -i 'ac:f2:3c:32:13:c4\|BRWACF23C3213C4'
```

Interpret the results cautiously:

- No ARP and no port 9100: confirm the live UniFi client record, power, and Wi-Fi association.
- ARP exists but port 9100 is closed: wake the printer, inspect its error state, and confirm Raw Port 9100 is enabled.
- Port 9100 opens but the add-on fails: verify the add-on's configured URI and inspect printer-service logs.
- `http://homeassistant.local:8099/health/mongo` succeeds: the print API and MongoDB are healthy, but this does not prove the Brother TCP/9100 path.

The controller's retained client list is historical evidence, not an availability probe. Confirm the service directly.

## Physical Wake-Up

The QL-810W can appear offline while sleeping:

1. Open and close the top cover.
2. Press the Feed button if consuming a blank label is acceptable.
3. Wait 15 seconds for Wi-Fi reassociation, then repeat the port-9100 test.
4. Check for cover-open, empty-roll, cutter, or other printer error indicators.

Do not reboot or factory-reset it before preserving the current UniFi association, address, AP, radio, RSSI, and event timestamps.

## Intended Wi-Fi Settings

The preferred printer SSID is `sintheta-iot`, which stays on `Default` and supplies compatibility settings without changing routing:

- 2.4 GHz only
- WPA2 with PMF disabled
- Fast Roaming and BSS Transition disabled
- DTIM 1 and 1 Mbps minimum/basic rate
- Client isolation, multicast filtering, multicast-to-unicast, and multicast/broadcast blocking disabled

The printer's last record was still on `sintheta`; moving it to `sintheta-iot` is a planned compatibility change, not proof that Wi-Fi caused a particular outage. Keep the same fixed `.192` lease if it remains on `Default`.

Do not apply the following as generic fixes:

- Do not set a made-up minimum RSSI such as `-80 dBm`. Leave minimum RSSI off unless captured association behavior supports a threshold, then derive it from measured coverage and client capability.
- Do not disable global connectivity monitoring merely because a printer slept.
- Do not enable IGMP snooping merely to fix mDNS. Same-VLAN discovery does not require the gateway mDNS proxy, and snooping requires a deliberate multicast/querier design.
- Do not disable global band steering for this device; the dedicated 2.4 GHz SSID already removes the band choice.
- Do not change several Wi-Fi optimization settings at once.

## Addressing and Add-On Configuration

Use a UniFi fixed-IP reservation rather than a printer-side static address unless there is a documented reason not to. A reservation keeps the address plan in one place and avoids collisions with the DHCP pool.

After creating the reservation:

1. Reconnect or renew the printer so UniFi shows `192.168.1.192` for `ac:f2:3c:32:13:c4`.
2. Verify TCP/9100 from Home Assistant or another `Default` client.
3. Confirm the deployed add-on option remains `tcp://192.168.1.192:9100`.
4. Print one known small test label.

If the printer later moves to a real IoT VLAN, make the migration as one coordinated change:

- Create a reservation in the new subnet.
- Permit Home Assistant to initiate TCP/9100 to only that printer.
- Add only the discovery services actually required for AirPrint/Brother apps.
- Update `brother_uri` in the add-on configuration and deploy it.
- Verify direct printing, API printing, discovery, sleep/wake, and the intended negative firewall tests.
- Keep a rollback to the old SSID/address until the observation window passes.

## Finding a Lost Printer

1. Search UniFi clients for `BRWACF23C3213C4` or `ac:f2:3c:32:13:c4`, including offline/history records.
2. Check the current SSID, network, AP, radio, address, last-seen time, and reconnect events.
3. Use Brother iPrint&Label or Printer Setting Tool from a client on `Default`; discovery may find the printer after its address changes.
4. If necessary, scan only the current `Default` subnet for raw print service:

   ```bash
   nmap -p 9100 192.168.1.0/24
   ```

5. Compare the discovered address with the add-on setting and reservation.

## Printer-Side Checks

Open `http://<current-printer-ip>/` when reachable and verify:

- Raw Port 9100 is enabled.
- The configured SSID is intentional and uses WPA2.
- DHCP is enabled if UniFi owns the fixed-IP reservation.
- Signal strength and reconnect evidence are consistent with the serving AP.
- Sleep settings match the availability/power tradeoff.

Check Brother's official support page for the current firmware applicable to this exact regional model. Do not use a hard-coded firmware number from this runbook as an upgrade target. Record the existing version, release notes, backup/rollback considerations, and a post-update print test before upgrading.

## Decision Register

| Setting | Current/expected value | Recommendation | Open question |
| --- | --- | --- | --- |
| Printer SSID | Last seen on `sintheta`; intended `sintheta-iot` | Move only after reserving the address and preserving a rollback | Is there an active reliability problem, or is this preventive compatibility work? |
| Address | `.192`, but dynamic | Reserve `.192` to the recorded MAC | Must any other system besides this add-on be updated if the address changes? |
| Client isolation | Off for the printer SSID | Keep off while Home Assistant must initiate TCP/9100 | Will a future routed VLAN replace same-Layer-2 access? |
| Minimum RSSI | No printer-specific threshold | Keep disabled unless measured evidence supports one | What is the worst normal RSSI at the printer, and which AP should serve it? |
| IGMP snooping | Off | Keep off unless multicast measurements and querier design justify it | Is there actual multicast flooding or loss, rather than ordinary sleep/reassociation? |
| Firmware | Verify live | Use Brother's current model-specific release notes | Does the release fix an observed problem, and what is the rollback/support path? |
| Sleep mode | Verify live | Keep power saving unless captured wake failures outweigh it | What wake latency is acceptable for print jobs? |

## Last Resort

Factory reset only after exporting or recording printer-side network/protocol settings and confirming the Wi-Fi credential is available from the approved password manager. A reset destroys evidence and creates a second setup problem; it is not an initial connectivity test.

If Wi-Fi remains unreliable after a fixed reservation and evidence-based diagnosis, USB is the supported fallback for this add-on:

```bash
export PRINTER_BACKEND=brother-network
export BROTHER_PRINTER_URI=usb://0x04f9:0x209b
```

Confirm the exact USB product identifier on the host rather than assuming the example value.

## See Also

- [QL-810W initial setup](./ql810w-setup.md)
- [Printer add-on README](../README.md)
- [UniFi Network Setup and Tuning](../../docs/operations/unifi-network-setup.md)
- [Brother QL-810W support](https://support.brother.com/g/b/spec.aspx?c=us&lang=en&prod=lpql810weus)
- [UniFi wireless troubleshooting](https://help.ui.com/hc/en-us/articles/221029967-UniFi-Troubleshooting-Wireless-Connectivity)
