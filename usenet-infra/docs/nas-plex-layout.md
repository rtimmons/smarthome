# Deployed NAS and Plex layout

September 11, 2026. The existing `FromDrobo` SMB share is retained to preserve
network shortcuts and permissions. Its physical root is
`/share/CACHEDEV2_DATA/FromDrobo`, on the 4 TiB data volume, not the roughly
99 GiB system volume containing the default `Multimedia` share.

```text
FromDrobo/
├── loljk/               existing private collection; unchanged
├── Movies/              selective, verified Usenet cache
│   ├── video/<item-id>/  completed movie files visible to Plex
│   ├── .staging/        incomplete transfers; excluded from Plex's root
│   └── other/           diagnostic/nonvideo catalog entries
├── TV Shows/            separate TV library root
├── Remote/files/        read-only Storage Box mount
└── .remote-cache/       bounded disposable streaming cache
```

Only the former `/share/Usenet/usenet-cache` directory was relocated, using an
atomic same-filesystem rename to `/share/FromDrobo/Movies`. The inode and device
were verified unchanged. Zero media bytes were copied by this layout operation.
The `loljk` inode, modification time, library path and 5,258-entry count were
preserved. No recursive permission changes, share deletion, collection-wide
hashing, or cross-volume copy was performed.

The private deployment inventory now sets `qnap_data_root` to
`/share/FromDrobo` and `qnap_catalog_cache_dir` to `/share/FromDrobo/Movies`.
The deployed Compose environment agrees; containers still use `/data/library`.
Only the catalog dashboard and rclone services were recreated. Plex and other
NAS applications were not restarted. The cache remains selective: removing a
local catalog copy removes its NAS file, while the canonical Storage Box copy
remains. Do not manually rename files inside an item-ID directory: manifests
and verification records refer to those relative paths.

## Plex libraries and access

| Library | Plex ID | Physical source |
| --- | --- | --- |
| `loljk` | 1 | `/share/CACHEDEV2_DATA/FromDrobo/loljk` |
| `Movies (NAS)` | 2 | `/share/CACHEDEV2_DATA/FromDrobo/Movies/video` |
| `TV Shows (NAS)` | 3 | `/share/CACHEDEV2_DATA/FromDrobo/TV Shows` |
| `Movies (Remote)` | 4 | `Remote/files/library/Movies` and legacy `Remote/files/objects/video`, beneath the same physical share |
| `TV Shows (Remote)` | 5 | `Remote/files/library/TV`, beneath the same physical share |

New libraries use Plex Movie and Plex TV Series agents. Video preview thumbnail
generation is disabled for these libraries to avoid unnecessary NAS processing.
Do not point either general library at the share root.

The `Movies & TV` managed Home profile is explicitly granted only IDs 2, 3, 4 and 5;
verification using that profile's server token returned only those libraries,
and direct access to ID 1 returned HTTP 403. `loljk` visibility is set to **Exclude from home screen and
global search**. The owner can still deliberately open that library.

The owner profile did not have a PIN. Set one privately in Plex Home and select
`Movies & TV` on each Apple TV/Roku. Client startup behavior has not been changed
remotely or tested: a device still signed into the owner, especially one reopening
the last library, is not equivalent to the restricted profile. Avoid automatic
sign-in to the last-used owner profile. Library visibility alone is not access
control. [Plex Home](https://support.plex.tv/articles/204234323-creating-a-plex-home/),
[Roku settings](https://support.plex.tv/articles/204275243-settings-plex-for-roku/)

Plex already watched local filesystem changes. Partial scans are now enabled,
with an hourly scan fallback. Automatic trash emptying is disabled to preserve
metadata if storage temporarily disappears. These are Plex's native settings;
OliveTin does not perform the Plex library scan.

The first real movie copy, `Colony (2026)` (13.5 GiB), completed and passed
SHA-256 verification. Plex indexed it automatically in `Movies (NAS)`; a
read-only API check confirmed the title, year and media-file entry. This tests
copy/publication/indexing, not Apple TV/Roku decoding or client startup. The
transfer took about 30 minutes with variable throughput; remote playback later passed a 1 MiB HTTP 206 range read, as recorded in
[native media](native-media.md). Sustained playback on each real TV client remains
unverified.

## Recovery and boundaries

Before-change Plex paths/library preferences and the changed server preferences
are recorded in ignored `build/plex-layout-before-20260911.json`. The NAS stores
the old private Compose environment and a nonsecret move receipt under
`/share/Container/usenet/state/media-layout-20260911/`. The private deployment
inventory also has an ignored local before-change copy. These are rollback
records, not a full Plex database backup or proof of whole-NAS disaster recovery.

To reverse only the directory relocation, first stop the two cache services
when no transfer is active, confirm the old destination is absent and both
parents are on the same filesystem, then rename `Movies` back to the old cache
path and restore the matching Compose/inventory settings. The Plex Movies source
must be updated before scanning that reversed layout. Do not copy a directory
over an existing collection, remove the share, or empty Plex trash as part of
this operation.

Native Radarr/Sonarr imports now sort new movies and TV into separate canonical
library folders. The old publisher timer is disabled. See [native media](native-media.md)
for mount dependencies and remaining client tests, and [scheduled backups](scheduled-backups.md)
for encrypted Plex/database protection.

## Prepared native-copy layout (not yet deployed)

TV copy actions default disabled until `qnap_native_tv_copy_enabled` is explicitly
enabled after the source migration. Native movie copies publish under `Movies/video/native-<id>/<title>`, preserving
Plex source ID 2. TV publication requires narrowing Plex source ID 3 to
`TV Shows/library`; TV staging then lives at `TV Shows/.staging`, outside that
source but within the same container bind. Distinct bind mounts cannot perform
an atomic rename between them, even when their device numbers match.

The current deployed source table above has not been changed by this source-only
increment. Before migration, inspect only the general TV root and ID 3; require
no existing series outside `library`, record its current source, and preserve
all IDs/profile grants. Follow [native media](native-media.md#selective-native-library-nas-copies)
and the current [handoff](../../plan.md). No collection move or whole-library
hash is required. Live native-copy and Plex indexing acceptance remain pending.
