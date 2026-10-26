# Plex on the Home Assistant host: isolated trial

Branch: `trial/plex-home-assistant`. Started October 26, 2026.
The trial below is historical. The user subsequently requested a running
[secondary server](plex-secondary.md); that runbook owns current libraries,
startup, analysis settings and the verified limitations of transcode caps.
This is an evaluation, not a Plex migration. Existing NAS libraries, privacy
grants, mounts, accounts and playback remain unchanged. The user selected
measurement without changing lights.

## Host and trial state

Live inventory found an AMD Ryzen Embedded V1202B with Radeon Vega graphics,
four logical CPUs, 30.3 GiB total memory, about 26.5 GiB available, and 54.4 GB
free disk. HAOS is 18.3; Core is 2026.10.2. A render device exists at
`/dev/dri/renderD128`; this does not prove Plex can use its codecs.

Community Plex app `a0d7b954_plex` version 4.1.3 is installed for this trial.
Automatic startup and watchdog are disabled. The user supplied the account
claim through Home Assistant; startup and Plex Pass entitlement were verified.
Never save claim codes or Plex tokens in source, command output, receipts or
chat. The user explicitly approved a private local copy of the trial-only
configuration backup for API access. Private evidence and that credential-bearing
backup are under mode-0700 `/private/tmp/plex-ha-trial/` and must not enter Git.
The server is named `Home Assistant Synthetic Trial`, remote publishing is
disabled, and its only library points at `/media/plex-ha-trial-20261026`.
The synthetic library is excluded from home/search, with thumbnail, credits,
voice-activity, ad and loudness analysis disabled.

The [app documentation](https://github.com/hassio-addons/app-plex/blob/main/plex/DOCS.md)
describes account claiming. Its [configuration](https://github.com/hassio-addons/app-plex/blob/main/plex/config.yaml)
passes graphics devices into the container. [Plex hardware transcoding](https://support.plex.tv/articles/115002178853-using-hardware-accelerated-streaming/)
requires Plex Pass. Verify actual session hardware decode/encode status;
device presence and an enabled checkbox are insufficient.

## Measurements

Run from the repository root using the pinned runtime:

```sh
just plex-ha-probe idle /private/tmp/plex-ha-trial/idle-new.json 120
```

Choose a new output path for every run; existing evidence is never overwritten.
The probe uses the repository's dedicated SSH identity and HA client credential
lookup. Every second it measures an authenticated Core API round trip and a
WebSocket `execute_script` request containing variables and a 50 ms delay.
The script returns server elapsed time. It invokes no device services, changes
no entities, and installs no persistent automation. Round-trip timing includes
network/client overhead and, for scripts, WebSocket authentication.

Every ten seconds it samples host load, CPU pressure, available memory, Core,
Z-Wave JS and Plex app statistics. Following the later Roku incident, it also
captures hwmon temperatures and per-core clocks; the original trial receipts
did not measure thermal headroom. Host sampling consumes time between probes;
this is not an exact 1 Hz sampling clock. Output includes counts, median, p95,
maximum and failures. A failed phase is invalid, not a successful low-latency
result. The observer does not start, stop or constrain any workload.

Initial Z-Wave inventory is in the ignored snapshot
`new-hass-configs/inventory_snapshots/zwave-scene-audits/20261026-153607/`.
It found seven unavailable configured entities, six unhealthy Z-Wave nodes,
zero entity-registry drift and no pending ramp changes. Existing radio faults
must not be attributed to Plex. Inventory/log observation and scheduler timing
do not establish physical device latency or real Central Scene delivery.

## Trial protocol and limits

1. Claim the new server, name it distinctly, disable remote access and automatic
   background analysis, and add only a dedicated synthetic-video directory.
   Do not mount real libraries or clone production Plex configuration.
2. Use a generated 1080p H.264/AAC test pattern. A 120-second, approximately
   260 MiB fixture exists at `/private/tmp/plex-ha-trial/synthetic-1080p.mp4`
   on the controller. Synthetic footage is a controlled comparison, not a
   representative codec/complexity matrix.
3. Measure app-stopped baseline, app-idle baseline, one forced 1080p-to-720p
   software transcode, and recovery with the same probe. Repeat phases to
   distinguish normal variance. Keep playback active throughout each phase;
   capture session transcode speed, buffering and CPU/GPU decode/encode status.
   Direct Play, Direct Stream, throttled/finished transcoding and an idle player
   are not sustained transcoding evidence.
4. If the first load is healthy, test two simultaneous transcodes. Test hardware
   acceleration separately if the account and AMD driver/codec path support it.
   Consider 4K/HDR only after these phases pass; it is not part of initial acceptance.
5. Stop the trial if API or script calls time out, sustained p95 exceeds twice
   baseline with more than 100 ms added latency, memory available falls below
   2 GiB, disk free below 20 GB, CPU/GPU temperature reaches 85°C, effective
   clocks collapse under load, Core/radio services restart, or new radio errors
   appear. These are conservative trial thresholds, not guarantees. A human or
   supervising runner must enforce them; this probe alone is not a watchdog.
6. Stop playback and the Plex app, then measure recovery and compare fresh
   inventories/log windows. Keep startup manual. A favorable result requires
   active transcoding proof, acceptable scheduler/API behavior and recovery;
   physical lighting response remains untested by user choice.

## Rollback

Stop only `a0d7b954_plex` using `ha apps stop a0d7b954_plex` over the dedicated
Home Assistant SSH connection. The trial has no boot requirement or production
mounts. Once evidence is retained and the user no longer wants the trial,
uninstall that exact app and remove only its confirmed synthetic fixture
directory. Do not restart Core, Z-Wave JS, the host or NAS Plex for rollback.

## Results

The 120-second idle baseline (19:38:27 UTC) collected 96 successful samples:

| Metric | Median | p95 | Maximum |
| --- | ---: | ---: | ---: |
| Core API round trip | 4.63 ms | 5.99 ms | 1330.08 ms |
| Script round trip, including connection/authentication | 316.38 ms | 322.00 ms | 334.74 ms |
| Server execution, including requested 50 ms delay | 51.38 ms | 52.36 ms | 53.05 ms |

The API maximum was the first request; retain it as connection-startup cost,
not a proven Core scheduling stall. Available memory remained about 26.5 GiB;
the first/last one-minute load samples were 0.45/0.32. Plex stats explicitly
reported that the app was not running. Evidence is controller-local at
`/private/tmp/plex-ha-trial/idle-retry.json`; the earlier `idle.json` is a failed
sandbox-network attempt and is not the baseline. Temporary evidence is not a
durable backup. A separate ten-second recipe check also passed. TypeScript
build, JavaScript syntax and diff whitespace checks passed.

### Claimed-server tests

The first running-server window included automatic credits detection and is
recorded as initialization, not idle (`plex-idle.json`). After disabling library
analysis and restarting only Plex, a 60-second baseline was collected; its first
host sample still showed startup activity, while later Plex samples were about
0.2% CPU. HTTP connection-startup overhead also changed from the earlier window,
so compare against this contemporary baseline rather than the earlier 6 ms p95.

The software fallback test forced 1080p H.264/AAC to 1280×720 H.264 HLS at a
4 Mbps maximum bitrate, using **Prefer higher quality encoding** (setting 2).
Hardware decoding and encoding were disabled for this comparison. The generated
ten-minute test pattern is deliberately difficult to compress. The client
consumed segments as fast as available, with a 600-second transcoder buffer to
avoid throttling: this measures sustained conversion capacity, not ordinary
paced viewing or subjective picture quality.

| Phase | Samples | API p95 | Script round-trip p95 | Server 50 ms delay p95 |
| --- | ---: | ---: | ---: | ---: |
| Plex idle after analysis disabled, 60 seconds | 42 | 260.40 ms | 318.40 ms | 52.77 ms |
| One software transcode, 120 seconds | 79 | 269.73 ms | 435.45 ms | 72.78 ms |
| Recovery with playback stopped, 60 seconds | 42 | 259.75 ms | 320.03 ms | 52.68 ms |

All software-run samples reported active, unthrottled video transcoding. Plex
reported 0.3–0.7× real time (median 0.6×), insufficient for continuous playback
of this workload. Plex CPU samples ranged 54.83–78.21% on Supervisor's reporting
scale; CPU pressure `some avg10` reached 68.45%. Available memory stayed above
26 GiB. No probe failures occurred, but the server-delay maximum was 232.26 ms.
This establishes measurable contention for the tested software preset; it is
not evidence about working GPU transcoding or every real-world file.

The short `software-check` was stopped by a latency guard based on the older
baseline. It is an invalid guard comparison, not evidence of an HA failure.
The sustained run used the contemporary baseline and completed normally.

### GPU verification and harness correction

Plex sees AMD Raven Ridge / Radeon Vega (`1002:15dd`), the host uses
`amdgpu`, and Plex Pass is active. Initial GPU-requested runs reused an earlier
software-only playback decision. Consequently `transcodeHwRequested=true`
appeared without hardware decoding/encoding fields. Those runs do not establish
a driver failure or GPU incompatibility.

The user explicitly approved downloading the isolated trial's diagnostic logs
into private temporary storage. Logs showed no hardware decoder selected, but
no driver-load failure. Correcting the harness to request a fresh
`/video/:/transcode/universal/decision` for each unique client/session before
`start.m3u8`, and retaining that same client identity for playlists and segments,
produced `transcodeHwDecoding=vaapi`, `transcodeHwEncoding=vaapi` and
`transcodeHwFullPipeline=true`. No host or driver modification was required.
The 20-second verification reported 2.5–2.7× real time and a server-delay p95
of 53.94 ms, without probe failures.

The earlier software run also reused a decision made with an 8 Mbps request;
its encoder command used a 7,227 kbps maximum. Treat that run as observed
software contention, not an exact bitrate-matched GPU comparison. The corrected
runner records actual selected resolution and bitrate and rejects a GPU phase
if either VA-API decoding or encoding is absent. It also rejects missing,
completed, throttled or failed transcode sessions.

The playback runner and credential helper remain private in
`/private/tmp/plex-ha-trial/`; credentials are loaded in memory from the
user-approved snapshot and never passed on command lines. The private diagnostic
archive must not be committed. The completed two-minute GPU runs both retained full VA-API decode/encode and
active, unthrottled sessions throughout. The fresh decisions selected 1280×720
H.264 with a reported 3,545 kbps bitrate for a 4 Mbps request.

| GPU phase | Stream speed, median | Server 50 ms delay p95 | Script round-trip p95 | Plex CPU range |
| --- | ---: | ---: | ---: | ---: |
| One stream, 120 seconds | 2.5× real time | 58.89 ms | 353.40 ms | 24.08–30.89% |
| Two streams, 120 seconds | 1.3× per stream | 66.83 ms | 385.71 ms | 29.10–40.55% |
| Playback stopped, 60 seconds | — | 56.97 ms | 352.16 ms | See receipt |

The first two-stream run contained a significant isolated outlier at 16:27:05
EDT: 4,314.50 ms script round trip, including 584.24 ms server execution for the
nominal 50 ms delay. A second sample had 116.07 ms server execution. This is
observed latency, not proof Plex caused every part of the delay. It prevents a
blanket claim that two streams have no automation impact. One-stream server
execution also had a 123.15 ms maximum. No request timed out.

A 60-second two-stream repeat retained full hardware acceleration at a median
1.4× per stream. Server-delay p95/max were 57.29/63.09 ms; script round-trip
p95/max were 385.32/454.95 ms. The multi-second outlier did not recur, which
limits but does not erase the first observation.

All playback sessions were stopped. The trial's quality setting was restored
to Automatic and its throttle buffer to 60 seconds. GPU decoding/encoding and
explicit AMD selection remain enabled. The Plex app is stopped with manual
startup; production NAS Plex was unchanged. The final read-only inventory at
`20261026-163110` matched the initial seven unavailable entities and six unhealthy
Z-Wave nodes, with no entity drift or pending ramp changes. Its captured driver
log ended at 16:09:49, before the verified GPU runs, so that log window does not
prove an absence of later radio errors. No radio control or device service was
exercised.

Interpretation: one tested 1080p-to-720p GPU stream has useful throughput
headroom and a small p95 scheduling increase. Two streams worked but had less
throughput headroom and one unexplained scheduling stall; start a longer
household trial with a one-transcode cap before considering production migration.
The short tests do not establish a safe maximum stream count. Machine-readable,
credential-free summaries are in `plex-ha-trial-results.json` beside this runbook.

Final stopped-server recovery collected 46 successful samples in 60 seconds:
server-delay p95/max 54.73/83.77 ms and script round-trip p95/max
353.07/377.37 ms. The first part overlapped the read-only inventory and should
not be treated as a perfectly isolated baseline. No probe failed. These are
synthetic throughput tests, not Apple TV/Roku playback, subtitle burn-in, HEVC,
4K/HDR tone mapping, library scanning or physical light-response acceptance.
Lights remain unchanged.
