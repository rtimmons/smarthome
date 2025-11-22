# Brother QL-810W Network Printing

## Agent Notes
- Follow the repo-wide expectations in `../../CLAUDE.md#agent-expectations-repo-wide` (sandbox/git-lock permission, use `just`/env wrappers, “prepare to commit” steps).

These steps walk through preparing a Brother QL-810W so the `brother_ql` backend can talk to it over Wi‑Fi using the raw TCP port (`tcp://<ip>:9100`). The printer ships with direct-USB enabled but network printing disabled, so a little one-time setup is required.

## 1. Connect the printer to your network
- Plug the printer in and load a roll.
- Install Brother’s “Printer Setting Tool” (macOS/Windows) or use the mobile “iPrint&Label” app.
- Use the tool/app to put the printer on the same Wi‑Fi network as the machine running this service. Record the assigned IP address (DHCP or static).
- Optional but recommended: reserve the IP in your router or assign a static address so the URI stays stable.

## 2. Enable the raw TCP print service
- In the Setting Tool, open **Communication Settings → WLAN**.
- Make sure *Protocol* → **Raw Port (Port 9100)** is enabled. LPR and AirPrint are optional.
- Apply the configuration and wait for the printer to reboot.

If you prefer the web UI, browse to `http://<printer-ip>/` → **Network Configuration** → **Services**, then enable **Raw Port (9100)** there.

## 3. Verify connectivity
- From the host machine run `ping <printer-ip>` to make sure the address is reachable.
- Run `nc -z <printer-ip> 9100` (or `telnet <printer-ip> 9100`) to confirm the port is open. A successful connection means the printer is ready.

## 4. Configure the service
```bash
export PRINTER_BACKEND=brother-network
export BROTHER_PRINTER_URI=tcp://<printer-ip>:9100
# Optional tweaks if you changed media or rotation:
# export BROTHER_MODEL=QL-810W
# export BROTHER_LABEL=62
# export BROTHER_ROTATE=auto
```

Restart `just start` (or your process manager) after updating the environment.

## 5. Send a test label
- Visit `http://localhost:8099/` (override with `FLASK_PORT`), pick a template, and print.
- The service will stream raster instructions to the printer. If you still see timeouts, double-check the URI, firewall rules, and that the printer is awake (it sleeps quickly but wakes when you open the cover or press Feed).

### Troubleshooting
- **Timeouts**: usually indicate the printer is unreachable; confirm steps 1–3.
- **Brother Setting Tool can't find the printer**: connect via USB temporarily, then push updated Wi‑Fi settings.
- **Frequent drop-offs**: give the device a static IP or reserve the DHCP lease; poor Wi‑Fi signal can also cause the raw socket to hang.

For comprehensive troubleshooting, especially on Ubiquiti/UniFi networks, see [ql810w-troubleshooting.md](./ql810w-troubleshooting.md).
