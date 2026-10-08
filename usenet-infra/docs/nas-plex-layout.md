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
