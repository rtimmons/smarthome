# NAS and Plex layout

The existing `FromDrobo` share remains at `/share/CACHEDEV2_DATA/FromDrobo` on
the 4 TiB data volume. Application state is `/share/Container/usenet`. Preserve
`qnap_data_root: /share/FromDrobo` and `qnap_catalog_cache_dir: /share/FromDrobo/Movies`
in private inventory; older bound snapshots contain the former cache path.

```text
FromDrobo/
├── loljk/                    private collection
├── Movies/
│   ├── video/<item-id>/       published NAS movies
│   ├── .staging/             excluded from Plex
│   └── other/                nonvideo catalog objects
├── TV Shows/
│   ├── library/<series>/     published NAS TV
│   └── .staging/             same bind mount, outside Plex's source
├── Remote/files/             read-only Storage Box mount
└── .remote-cache/            disposable playback cache
```

## Libraries and profile grants

| Library | Plex ID | Source beneath the physical share |
| --- | --- | --- |
| Private `loljk` | 1 | `loljk` |
| Movies (NAS) | 2 | `Movies/video` |
| TV Shows (NAS) | 3 | `TV Shows/library` |
| Movies (Remote) | 4 | `Remote/files/library/Movies` and `Remote/files/objects/video` |
| TV Shows (Remote) | 5 | `Remote/files/library/TV` |

The managed `Movies & TV` profile receives exactly IDs 2/3/4/5 and is denied ID 1.
The private library is excluded from home/global search. Never point a general
library at the share root or staging, and never browse private media to inspect
settings. Owner PIN and client profile choice remain private user/device work.
The user confirmed restricted privacy and playback on Apple TV and Roku; this
is not a guarantee about a future client's saved profile.

Plex's preferred network interface is `br0` (`192.168.1.66`); preserve it on
restore. On October 25, `PreferredNetworkInterface=br0` removed eleven internal
container addresses from published connections without a restart, but did not
resolve playback delay. Keep authentication and secure connections enabled.

<a id="playback-delay-investigation"></a>

### Playback delay investigation — October 25, 2026

Roku title metadata requests with `checkFiles=1` spent 30–65 seconds upgrading
outdated media analysis before playback negotiation. Authentication succeeded.
The one-time repair finished at 23:50 EDT: read-only verification found all 683
general-library records at version 8, zero outdated records, and both earlier
readback exceptions reconciled. Four Mac HTTPS title-opening probes took
0.18–2.20 seconds; a 1 MiB stream sample took 1.05 seconds. Debug logging was
restored to off. Fresh Roku/iOS playback remains the client acceptance check;
cached reads and server stream probes do not establish it.

Keep `ButlerTaskUpgradeMediaAnalysis` enabled. Manual Analyze also requests
chapter thumbnails, intro/credits detection and loudness analysis. For a basic
upgrade backlog, use bounded `checkFiles=1` requests for outdated records in
library IDs 2/3/4/5 and verify `media_analysis_version` afterward. Never write
versions directly into the database or include private library ID 1.

A separate iOS 2026.20.0 attempt buffered at 0:00 after Direct Play negotiation
for a Dolby Vision MKV, resembling a
[reported regression](https://forums.plex.tv/t/ios-ipados-mkv-direct-play-stuck-on-infinite-buffering-after-plex-app-update/944874).
Test **Allow Direct Play: off** with **Allow Direct Stream: on** on that client.
A server probe successfully repackaged the video, but client acceptance remains
unverified; this does not explain the separate Roku metadata delay.

Plex watches local changes, uses partial scans and scans hourly. Automatic trash
emptying stays disabled so a missing mount does not purge metadata. Remote/TV
files may require a general-library scan. OliveTin does not own discovery.

## Copying and recovery

Movie copies publish under `Movies/video/native-<id>/<title>`. TV copies publish
under `TV Shows/library/<series>`, with the staging and destination directories
inside one container bind for atomic rename. The private inventory enables
`qnap_native_tv_copy_enabled`; disable it if restoring an older Plex source
that includes staging. Never relocate existing series automatically.

Selective copying uses the read-only canonical credential, a shared lock,
100 GiB reserve, independent SHA-256 and owned-copy receipts. See
[native workflow](native-media.md). Do not rename manifest-managed files,
modify shared hardlinks in place or adopt unrelated files after restoring receipts.

[Scheduled settings backups](scheduled-backups.md) include native-copy receipts,
dashboard state and Plex preferences/databases. They exclude originals and
artwork. Preserve library IDs, grants, physical paths and the separate confined
backup credential on recovery. A settings restore is not a replacement NAS
boot test or permission to delete the original collection.
