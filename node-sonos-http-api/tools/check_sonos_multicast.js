#!/usr/bin/env node
/**
 * Quick diagnostic to verify that the local machine can transmit
 * the SSDP multicast/broadcast probes that node-sonos-http-api requires.
 *
 * The script attempts to send the standard M-SEARCH packet to both
 * 239.255.255.250 and 255.255.255.255. When macOS network extensions
 * (VPN/Tailscale/WARP, etc.) steal the multicast route, the send call
 * fails with EHOSTUNREACH. We surface that so `just setup` can point the
 * developer to the right fix instead of letting node-sonos fail silently.
 */

const dgram = require('dgram');

const SEARCH_PACKET = Buffer.from([
  'M-SEARCH * HTTP/1.1',
  'HOST: 239.255.255.250:1900',
  'MAN: "ssdp:discover"',
  'MX: 1',
  'ST: urn:schemas-upnp-org:device:ZonePlayer:1',
  '', // blank line terminator
  '',
].join('\r\n'));

const TARGETS = [
  { address: '239.255.255.250', label: 'multicast' },
  { address: '255.255.255.255', label: 'broadcast' },
];

function run() {
  const socket = dgram.createSocket({ type: 'udp4', reuseAddr: true });

  const results = [];

  function finish() {
    socket.close();
    const failures = results.filter((r) => r.error);
    if (failures.length) {
      failures.forEach((failure) => {
        console.error(
          `[FAIL] Unable to send SSDP probe (${failure.label}) to ${failure.address}: ${failure.error.code || failure.error.message}`,
        );
      });
      console.error(
        '\nSonos discovery failed before the HTTP API even starts. ' +
          'This typically indicates a VPN/ZeroTrust client (Tailscale, WARP, corporate VPN) ' +
          'or macOS privacy features (Private Wi-Fi Address / Limit IP Address Tracking) ' +
          'that inject utun routes and block multicast/broadcast traffic on macOS.',
      );
      process.exit(1);
    } else {
      results.forEach((ok) => {
        console.log(`[OK] SSDP probe (${ok.label}) sent via ${ok.address}`);
      });
      process.exit(0);
    }
  }

  socket.once('error', (err) => {
    console.error(`Failed to create UDP socket: ${err.message}`);
    process.exit(2);
  });

  socket.bind(0, () => {
    socket.setBroadcast(true);
    socket.setMulticastTTL(2);

    TARGETS.forEach((target) => {
      socket.send(SEARCH_PACKET, 1900, target.address, (error) => {
        results.push({
          ...target,
          error,
        });

        if (results.length === TARGETS.length) {
          finish();
        }
      });
    });
  });
}

run();
