# NZBGeek cart downloads from a phone

Configured and verified September 13, 2026 (UTC). Browse NZBGeek's discovery
pages and add a chosen release to **My Cart**. Cloud SAB's enabled
`NZBGeek Cart` RSS feed checks every 15 minutes and queues new matching entries.
The phone does not need to remain connected; adding to the cart also works away
from home. SAB's management UI still requires the existing home LAN route.

- Cart: <https://nzbgeek.info/dashboard.php?mycart>
- Downloader: <http://10.77.0.1:18080/>; use the catalog credentials.
- Faster pickup: SAB menu → **Read All Feeds Now**.
- The setup item was held as SAB's initial batch. It was media-004,
  individually released September 14 after the user selected the current cart
  items. For another held item, use its individual download action under
  Config → RSS → NZBGeek Cart. **Force Download** queues all matching held entries.

The feed uses **Default** category, repair/unpack/cleanup (`pp=3`), no script,
normal priority, and one enabled Accept `*` filter. The wildcard applies only to
the authenticated cart feed. Direct cart jobs do not establish Radarr/Sonarr
ownership; library import and Plex availability remain separate from completion.

The feed URL stays private on the cloud. Its nonsecret parameters are `t=-2`,
`limit=100`, `dl=1`, `del=0`; `r` uses the existing NZBGeek API key. `del=0`
preserves cart entries when read. SAB tracks processed entries to avoid repeated
RSS grabs; users may remove processed entries from the website cart. Do not
publish the personalized URL or reset downloaded-feed history casually.

Prowlarr's API masks the key, so setup read only the saved NZBGeek indexer record
from its protected database. The cart endpoint refused Python's default client
identification (403) but accepted `SABnzbd/5.1.3`, which SAB already supplies.
No custom client change was needed; strict HTTPS validation remains enabled.

September 13 setup verification used SAB 5.1.3's configuration API and native `test_rss_feed` action
with downloading disabled. Read-only RSS database counts confirmed one
initial-scan entry and zero downloaded entries. Enabled feed, 15-minute interval,
exact private URL, filter and empty download/post-processing queues were read
back. No content download, cart deletion or service restart occurred during setup.
The September 14 continuation passed actual media-004 acquisition, deliberate native
import, full independent SHA-256 verification of 15,090,939,776 bytes, and Plex
discovery after one selected-directory scan. Only its verified new scratch file
and empty parent were reclaimed; SAB history and older scratch were preserved.
See [acquisition](../recovery/drills/cart-acquisition-20260914.json),
[import and cleanup](../recovery/drills/cart-native-import-20260914.json), and
[Plex discovery](../recovery/drills/cart-plex-discovery-20260914.json).
This is a manual Default-category path, not automatic Arr-owned client cleanup.

## Capacity and deliberate native import

Before releasing a held item, allow for download and unpacking while preserving
the scratch reserve. The September 14 cart had approximately 16 GB and 61 GB
releases against about 54 GB available after reserve. Only the smaller release
was admitted. Normal feed polling subsequently queued the oversized release;
only that exact job was paused before payload downloading, preserving the feed
and global pause state. Do not resume it without a new capacity decision.

Default-category movies need a deliberate native Radarr import after the exact
SAB job finishes repair/unpack:

1. Match title, year and catalog identity. Add an absent title without search
   and with monitoring disabled, preventing an unintended second acquisition.
2. Discover candidates by exact `/data/complete/<job>` folder, omitting
   `movieId` and `downloadId`. Review the mapped movie, quality, languages and
   rejections. Exclude samples/extras; do not guess a main stream from disc media.
3. Require no existing movie file and an absent destination. Use native
   `ManualImport` with `importMode: copy`, reviewed file metadata and no
   `downloadId`. Copy mode can still replace an existing library file, and a
   tracked download ID can invoke separate source cleanup; both guards matter.
4. Verify the import event, canonical file and stable size, then match targeted
   scratch SHA-256 against an independent Storage Box server hash. Confirm Plex
   discovery in Movies (Remote), ID 4. Only then assess exact-job scratch
   reclamation, accounting for all sidecars and preserving SAB history and the
   two older archived scratch groups.

The canonical movie path is Radarr `/library`, mapped to host
`/srv/usenet/library/Movies`. This path proves deliberate cart import only;
automatic Arr-owned client cleanup and device playback remain distinct checks.
See the pinned [manual-import API](https://github.com/Radarr/Radarr/blob/v6.3.0.10514/src/Radarr.Api.V3/ManualImport/ManualImportController.cs),
[import implementation](https://github.com/Radarr/Radarr/blob/v6.3.0.10514/src/NzbDrone.Core/MediaFiles/MovieImport/Manual/ManualImportService.cs),
and [existing-file replacement behavior](https://github.com/Radarr/Radarr/blob/v6.3.0.10514/src/NzbDrone.Core/MediaFiles/UpgradeMediaFileService.cs).

Protected original configuration (mode 0600):
`/srv/usenet/config/sabnzbd/sabnzbd.ini.before-nzbgeek-cart-20260913T035244Z`.
Previously there were no feeds and the RSS interval was 60 minutes. To stop this
workflow, disable **NZBGeek Cart** in SAB RSS settings; do not overwrite later
settings by restoring the whole original configuration. Existing settings and
smoke-test helpers intentionally refuse enabled RSS feeds; do not disable this
user-authorized feed merely to make their safeguards pass.

References: [SAB RSS behavior](https://sabnzbd.org/wiki/configuration/5.1/rss),
[installed reader source](https://github.com/sabnzbd/sabnzbd/blob/5.1.3/sabnzbd/rss.py).
