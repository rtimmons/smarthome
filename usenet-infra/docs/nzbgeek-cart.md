# NZBGeek cart downloads from a phone

Configured and verified September 13, 2026 (UTC). Browse NZBGeek's discovery
pages and add a chosen release to **My Cart**. Cloud SAB's enabled
`NZBGeek Cart` RSS feed checks every 15 minutes and queues new matching entries.
The phone does not need to remain connected; adding to the cart also works away
from home. SAB's management UI still requires the existing home LAN route.

- Cart: <https://nzbgeek.info/dashboard.php?mycart>
- Downloader: <http://10.77.0.1:18080/>; use the catalog credentials.
- Faster pickup: SAB menu → **Read All Feeds Now**.
- The one item present at setup was read and held as SAB's initial batch. To
  queue it deliberately, open Config → RSS → NZBGeek Cart and use its individual
  download action. **Force Download** queues all matching held entries.

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

Verification used SAB 5.1.3's configuration API and native `test_rss_feed` action
with downloading disabled. Read-only RSS database counts confirmed one
initial-scan entry and zero downloaded entries. Enabled feed, 15-minute interval,
exact private URL, filter and empty download/post-processing queues were read
back. No content download, cart deletion or service restart occurred. A future
user-selected download remains the end-to-end acquisition check.

Protected original configuration (mode 0600):
`/srv/usenet/config/sabnzbd/sabnzbd.ini.before-nzbgeek-cart-20260913T035244Z`.
Previously there were no feeds and the RSS interval was 60 minutes. To stop this
workflow, disable **NZBGeek Cart** in SAB RSS settings; do not overwrite later
settings by restoring the whole original configuration. Existing settings and
smoke-test helpers intentionally refuse enabled RSS feeds; do not disable this
user-authorized feed merely to make their safeguards pass.

References: [SAB RSS behavior](https://sabnzbd.org/wiki/configuration/5.1/rss),
[installed reader source](https://github.com/sabnzbd/sabnzbd/blob/5.1.3/sabnzbd/rss.py).
