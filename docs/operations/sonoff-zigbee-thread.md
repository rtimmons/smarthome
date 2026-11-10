# Sonoff Zigbee and Thread operation

The installed Sonoff ZBDongle-E currently serves **Zigbee only**. Thread and Matter were tested, then parked on October 16, 2026 at Ryan's request until real devices need them. Their saved configuration and credentials are retained. The MultiPAN firmware and shared radio app remain installed, so enabling Thread later requires no firmware flash or Zigbee migration.

The successful migration retained all eight paired Zigbee devices and all 117 entities. An uncached read from the existing Sengled top bathroom bulb confirmed communication after restoration. Six devices were already unavailable before migration; their retained registrations do not establish that they are online.

## October 16 migration baseline

| Component | Configuration |
| --- | --- |
| Home Assistant | Core 2026.10.1, ZHA 2.3.1, bellows 1.1.0, zigpy 2.3.0 |
| Radio | Sonoff Zigbee 3.0 USB Dongle Plus V2, ZBDongle-E, EFR32MG21 |
| Radio firmware | SONOFF MultiPAN beta 4.6.0, 115200 baud, no hardware flow control |
| Radio service | SONOFF Silicon Labs Multiprotocol 1.0.2, `81bc2df9_hassio_ihost_silabs_multiprotocol` |
| Zigbee stack | Zigbeed 8.1.1.0 build 341, EZSP 16 |
| ZHA connection | `tcp://81bc2df9-hassio-ihost-silabs-multiprotocol:9999` |
| Zigbee channel | 20, unchanged from the original network |
| Thread API | `http://81bc2df9-hassio-ihost-silabs-multiprotocol:8081` |
| Thread network | Saved `ha-thread-4548`, channel 20; radio service off (`otbr_enable: false`) |
| Thread integrations | Thread and OpenThread Border Router disabled, configuration retained |
| Matter | Official Matter Server app 9.2.0 stopped, manual startup; Matter integration disabled |

The November 9 lighting checks ran on Home Assistant Core 2026.10.4 and
confirmed that the Zigbee network was still on channel 20.

The multiprotocol app owns the USB device and must keep running for Zigbee. ZHA connects to that app, so it must not also open the physical serial port. The app starts automatically, with its watchdog enabled, while its Thread service stays off. The SONOFF flasher stays stopped with manual startup; stop ZHA and the multiprotocol app before using it.

## Why the first restore failed

The original attempt used `socket://` and failed in `networkInitExtended`, with status decoding errors and a timeout. The backup was complete, and the radio service had started successfully.

The exact bellows 1.1.0 source contains a reset-state bug. `startup_reset()` replaces the protocol handler with version 4 without resetting the remembered negotiated version. If the TCP connection receives Zigbeed's startup reset, `_startup_reset()` skips the explicit reset that would otherwise synchronize those fields. When version negotiation returns the already-remembered version 16, `version()` sees no change and leaves the version 4 handler active. Restoration then sends the obsolete initialization command.

An isolated reproduction using bellows 1.1.0, zigpy 2.3.0, and serialx 1.11.0 reproduced a reported version of 16 with an actual version 4 handler after the second reset. Using `tcp://` kept both at 16. Serialx accepts both schemes through the same socket transport; bellows applies its special startup-reset shortcut only to `socket://`.

The live retry used `tcp://`, completed the normal ZHA restore, and produced a fresh EZSP 16 backup with matching PAN IDs, channel, network key, trust-center key, and coordinator IEEE. The outgoing frame counter advanced. ZHA then completed its existing-entry reconfiguration, preserving entity IDs and device registry associations. Home Assistant and its Python packages were not patched.

This workaround is verified for the versions above. Recheck reset and reconnect behavior when updating bellows or the vendor app. SONOFF's published guide still describes ZHA as limited to EZSP 14; the installed bellows supports EZSP 16 through 19, so that explanation does not describe this installation.

## Verification and recovery

The Closet MOES TS0003 (`_TZ3000_gykhrpiv`) is a mains-powered Zigbee router on
channel 20. The bottom touch button controls endpoint 1, which drives the
fixture as `light.light_closet_main`. The other channels are disabled in Home
Assistant and stay outside scenes and All Off. Verify switching with an
uncached read of the On/Off cluster (`0x0006`) on endpoint 1. A blank map for a
new device can mean the neighbor scan has yet to run.

On November 9, all five Bathroom bulbs answered fresh On/Off reads after
their wall switches were turned on. The coordinator's refreshed routing table
showed the Closet MOES as the next hop for both vanity bulbs and the
above-sauna bulb. Edison-top was a child of the coordinator. Edison-bottom
still used vanity-right as its parent, even in route records that also used
the MOES. Keep vanity-right powered and use a lighting preset to turn its
output off.

The two Edison bulbs share a wall switch. Defer a factory reset until the
lower bulb can be isolated. To test the move, admit the lower bulb's fresh
join via the MOES, verify its actual parent, and check fresh reads with the
vanity switch off and the Edison fixture powered. Zigbee chooses routes
automatically. The targeted re-pair and physical vanity-off test are deferred.

The Closet High request at 21:29 reached `light.turn_on` in about 9 ms and the
relay reported on about 3.5 seconds after the request. The two-second
convergence wait followed the first radio command. With the Bathroom routers
online, a later logged cycle reported on after 413 ms and off after 163 ms,
with one successful Zigbee unicast per command. Compare the worker trace,
radio send result, and relay state timestamp before changing scene timing.

The November 9 parallel light exercise queued the first six Zigbee requests
within 14 ms of one another. During Off, the coordinator returned `FAIL` for
left vanity and Edison-bottom, and separately reported
`ZIGBEE_SOURCE_ROUTE_FAILURE` for Edison-bottom. Both sends succeeded on retry.
A four-cycle comparison delayed left vanity by 90 ms and Edison-bottom by
180 ms in two Off trials. The last state report took 1.21–1.64 s with the
stagger and 1.33–6.28 s in the two parallel trials. The same exercise saw
repeated source-route and many-to-one route failures, with one On cycle taking
39 s for the last bulb to report. The small sample and intermittent failures
did not establish a scheduling improvement. Keep parallel dispatch and check
radio send results and routes when delays recur.

Use `just ha-state light.light_bathroom_edison_top` for a basic state check. A cached state alone is not a radio test: use ZHA's cluster attribute read with caching disabled to confirm a fresh response. While parked, ZHA should be loaded and Thread, OpenThread Border Router, and Matter should be disabled. After enabling them, check all four integration states separately.

After parking on October 16, all eight Zigbee device identities, all 117 entity IDs, and the network credentials still matched, and another uncached bulb read succeeded. Matter Server took longer than Supervisor's shutdown allowance and was terminated with exit code 137. Supervisor therefore reports its stopped app as `error`; automatic startup and its watchdog are off. This is a recorded shutdown issue, not evidence that Matter is still running. Check its startup log when enabling it for the first accessory.

The combined service passed a restart check on October 16: Thread retained its network and channel, and ZHA retained every identity and answered another uncached bulb read. Allow roughly a minute for ZHA to reconnect after restarting the app. An early request returned `No gateway object exists` during that interval; it recovered without manual intervention. This check does not establish long-term reliability of the vendor beta firmware.

On November 9, Supervisor reported the multiprotocol app as started while Zigbeed was restarting repeatedly with `CPC endpoint open failed`. ZHA was in `setup_retry` and all five bathroom bulbs were unavailable. Restarting only the multiprotocol app reconnected the co-processor. Reloading the existing ZHA entry brought it back to `loaded`, and the bulbs returned as they reported in. If this recurs, check the app log for a successful co-processor connection and use an uncached bulb read to verify recovery.

Keep the Zigbee and Thread channels aligned at 20. A Thread channel change through Home Assistant takes five minutes. The vendor app is not recognized as the official multiprotocol app by all Home Assistant channel checks, so do not assume automatic channel coordination.

After a channel change, compare the border router's active dataset with Home Assistant's preferred Thread dataset. The first transition left the stored preferred dataset at channel 15 while the router had moved to 20. Importing the router's current active dataset through `thread/add_dataset_tlv` updated the existing preferred record to channel 20 without changing its identity or keys. Verify this before sending credentials to a phone.

Private evidence and backups are under `new-hass-configs/backups/sonoff-multipan/20261016` and `20261016-tcp-retry`. They contain network credentials and must remain ignored and private. The first directory includes the original 6.10.3 firmware, a verified encrypted Home Assistant backup, the pre-migration Zigbee database, and successful rollback evidence. The second contains the fresh pre-retry backup, driver reproduction, successful restore proof, and verification results.

The working-state encrypted Supervisor backup includes Home Assistant, the multiprotocol app, and Matter Server. Its local archive is verified against the host's SHA-256 hash. Preserve its separately saved password with the private recovery material.

Those October 16 archives capture the tested combined setup before parking. Restoring them can re-enable Thread and Matter; apply the parked settings above afterward if no devices need them yet.

For recovery, preserve the **latest** ZHA network backup and the multiprotocol app's persistent state. Zigbee state now lives in the app as well as Home Assistant; saving only the dongle firmware is insufficient. Matter server state and Thread credentials also need backup. Never restore an old network backup casually: newer outgoing frame counters must be preserved or advanced to avoid devices rejecting traffic.

If reverting to Zigbee-only firmware, first capture the latest network backup, unload ZHA, stop the multiprotocol app, and flash the verified original image. Reconfigure the same ZHA entry to the original USB path and restore the current network backup through ZHA's migration flow. Verify network identity, device and entity IDs, and a fresh device response before removing the multiprotocol app. Do not delete the ZHA entry, create a new Zigbee network, or re-pair devices as a diagnostic shortcut.

## Enable when the first device arrives

1. In Home Assistant, open **Settings → Apps → Silicon Labs Multiprotocol → Configuration**. Set `otbr_enable` to `true`, save, and restart this app. Keep its device, baud rate, flow control, and automatic startup settings unchanged. Allow about a minute for ZHA to reconnect.
2. In **Settings → Devices & services**, show disabled entries and enable **Thread** and **OpenThread Border Router**. Keep the existing `ha-thread-4548` network. Confirm its preferred credentials and the border router both report channel 20. Do not create a replacement network or restore an old dataset over healthy current settings.
3. Open the installed **Matter Server** app, enable **Start on boot**, and start it. Enable the existing **Matter** integration. No new integration, coordinator, or radio flash is needed.
4. Sync the preferred Thread credentials to the phone as described below. On that phone, choose **Add device → Add Matter device** in Home Assistant and scan the accessory's Matter QR code or enter its setup code. Keep the manufacturer's setup code privately for future commissioning.
5. Verify the new accessory responds and an existing Zigbee device still responds. Create a fresh encrypted backup containing **Home Assistant**, **Silicon Labs Multiprotocol**, and **Matter Server** after commissioning. Preserve its recovery password through SOPS or the established password-manager recovery workflow.

To park again, disable the Matter, OpenThread Border Router, and Thread integrations; stop Matter Server and turn off its automatic startup; set `otbr_enable` to `false` and restart the shared app. Leave that app's automatic startup enabled for Zigbee, and retain its data.

### Sync credentials to the phone

The phone used for commissioning needs the preferred Thread network's credentials. In the Home Assistant Companion app on iPhone, open Settings, Connectivity, Thread and select **Send credentials to phone**. On Android, use Settings, Companion app, Troubleshooting, **Sync Thread credentials**. Then add the device through the Matter integration using its setup code. Keep the phone on the home network during commissioning.

Running services and a healthy border router establish readiness. Commissioning an actual Matter over Thread accessory is a separate end-to-end check.

## Credentials and SOPS

No new account credentials or `secrets.yaml` entries are needed for ordinary operation. Home Assistant stores the Thread dataset, and Matter Server stores its controller credentials and paired-device state. Retain the full server backup once devices are commissioned; the Thread network key alone cannot restore Matter pairings.

A separate encrypted supplement is saved at `usenet-infra/vault/homeassistant-radio-20261016.sops.json`, using the existing SOPS age recipient. It contains the complete channel-20 Thread dataset and the passwords, locations, and SHA-256 hashes for three encrypted Supervisor archives, including the final verified combined setup (`612fabd6`). It contains no new private SOPS identity. The original `secrets.sops.json`, its inventory, and bound recovery snapshots remain unchanged.

The supplement is not part of `just setup-secrets` or the immutable original recovery manifest. Decrypt it separately only when recovering, with the existing master identity supplied through the established one-process `SOPS_AGE_KEY` workflow. Keep the output in a private mode-0600 file, not terminal output or chat. Normal future enabling uses the already-saved Home Assistant credentials and does not require decrypting this file.

Authenticated decryption **passed on October 16, 2026** using the existing recovery identity from 1Password, injected into one isolated SOPS process. The recovered Thread dataset matched the saved active channel-20 network; all three passwords matched their private originals, and all three archive SHA-256 hashes matched. The pinned SOPS binary was verified, no decrypted payload or private master was written to disk, and the original vault remained unchanged. The [verification receipt](../../usenet-infra/recovery/drills/homeassistant-radio-20261016.json) binds this result to the supplement's ciphertext hash.

The encrypted supplement and sanitized verification receipt belong in Git. Wiki publication contains this explanation only, never the credential payload or backup archives. Keep the original archives and private recovery copies: this check verifies the supplement, not a full Home Assistant restore or independent off-host preservation of the archives.

## References

- [bellows 1.1.0 reset and version negotiation source](https://github.com/zigpy/bellows/blob/1.1.0/bellows/ezsp/__init__.py)
- [bellows network restoration source](https://github.com/zigpy/bellows/blob/1.1.0/bellows/zigbee/application.py)
- [SONOFF multiprotocol app documentation](https://github.com/iHost-Open-Source-Project/hassio-ihost-addon/blob/master/hassio-ihost-silabs-multiprotocol/DOCS.md)
- [Home Assistant Thread setup](https://www.home-assistant.io/integrations/thread/)
- [Home Assistant Matter setup](https://www.home-assistant.io/integrations/matter/)
