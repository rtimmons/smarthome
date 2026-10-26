# Usenet pages and logins

Use this directory to open the right service and identify which account to use.
The household services need the home network or their existing private access
route. Filex additionally needs a tunnel running on the computer opening it.

## Household services

| Page | What it is for | Login to use |
| --- | --- | --- |
| [Seerr](http://seerr.home.arpa/) | Browse and request movies or TV | **Sign in with Plex**, using the existing owner account. The dedicated Moonfin local login is also enabled; automatic registration remains disabled. Seerr does not yet use Authelia OIDC. |
| [Plex](http://plex.home.arpa/web/) | Watch the NAS and Remote libraries | Your existing **Plex account**. For ordinary household viewing, select the **Movies & TV** profile after signing in; its profile/PIN choice is separate from the account login. |
| [Plex on Home Assistant](http://homeassistant.local:32400/web/) | Watch **Movies (hass) (Remote)** and **TV Shows (hass) (Remote)** on the established HA server | The same **Plex account** and **Movies & TV** managed profile. |
| [Jellyfin](https://jellyfin.home.rytim.com/) | Watch the general libraries alongside Plex | **Household AD password**, with `ryantimmons` or the existing `ryan` alias. This preserves Ryan's existing profile; it is not Authelia browser MFA. |
| [Moonfin](https://jellyfin.home.rytim.com/Moonfin/Web/) | Jellyfin playback and integrated Seerr requests | Use the same **AD-backed Jellyfin login**. Its separate request session is configured server-side; Roku app setup remains a user step. See the [Moonfin runbook](../../../usenet-infra/docs/jellyfin-trial.md#moonfin-requests). |
| [NAS copies / catalog dashboard](https://catalog.home.rytim.com/) | Select local copies and follow transfers | **Authelia MFA**, then Catalog's native OAuth sign-in using the same household identity. Only Ryan's mapped identity receives operator actions. The local catalog login is retained for recovery. |
| [SABnzbd](https://sabnzbd.home.rytim.com/) | Download queue, speed, repair and unpacking | **Authelia sign-in and MFA**. Provider credentials and the native API key are separate. |
| [Prowlarr](https://prowlarr.home.rytim.com/) | Indexer connections and search status | **Authelia sign-in and MFA** at the proxy; Prowlarr uses External authentication, not native OAuth. Existing API clients retain their API keys. |
| [Radarr](https://radarr.home.rytim.com/radarr/) | Movie requests, release selection and import history | **Authelia sign-in and MFA** at the proxy. Native API clients keep their existing API keys. |
| [Sonarr](https://sonarr.home.rytim.com/sonarr/) | TV series, episodes and import history | **Authelia sign-in and MFA** at the proxy. Native API clients keep their existing API keys. |
| [Filex](http://127.0.0.1:15213/) | Browse staging files and perform reviewed file operations | The saved **Filex operator account**, not its bootstrap administrator. First run `just usenet-filex-ui` from the repository root and leave it running. The link works only on that computer. |
| [QNAP administration](http://192.168.1.66:8080/cgi-bin/) | NAS settings and maintenance | The existing **local QTS administrator** for maintenance and recovery. QTS is not behind Authelia; AD-backed SMB share access is separate from the administration login. |

HA Plex is an ongoing household service. The NAS libraries remain available;
their possible future retirement includes analysis, Jellyfin/Moonfin migration
and service-address updates described in the
[HA Plex runbook](../../../docs/operations/plex-secondary.md#possible-future-nas-retirement).

The protected browser entrances use publicly trusted HTTPS and the household
[Authelia portal](https://auth.home.rytim.com/). The older numeric cloud entrances
retain their separate recovery authentication; do not use them as the normal
browser bookmarks. Native API clients and saved playback addresses retain their
existing access paths. No browser SSO redirect is added to playback APIs.

The [identity runbook](../../../docs/operations/household-identity.md) records the
exact boundaries and dated acceptance. On October 25, 2026, the user confirmed
Prowlarr, Radarr, Sonarr and SABnzbd opened through Authelia without a second
application password. The user also confirmed Catalog OAuth sign-in and visible
operator actions. These checks did not start searches, downloads or transfers.

## Plex: slow title opening or playback

The October 25 server analysis repair passed; fresh Roku/iOS playback remains
unverified. See the [Plex investigation](../../../usenet-infra/docs/nas-plex-layout.md#playback-delay-investigation)
for evidence, limits and the iOS 2026.20.0 Direct Play workaround. Confirm playback
actually advances before treating either issue as resolved.

## Roku: browse, request and watch with Moonfin

The server integration is configured. After connecting the **Moonfin** Roku app,
normal browsing, requests and playback can happen with the remote alone. The
stock Jellyfin Roku app does not expose this request workflow. Roku installation
and on-device playback remain unverified; the user deferred that device setup.

1. On Roku, search for **Moonfin** and install it from the Channel Store.
2. Open Moonfin and choose **Enter Server URL**. Enter
   `http://192.168.1.66:8096` while connected to the home network.
3. Sign in to Jellyfin as **`ryantimmons`** (or the existing **`ryan`** alias),
   using your **household AD password**. This is the Jellyfin login, not the
   dedicated Seerr login.
4. Alternatively, select **Quick Connect**. In a phone/computer browser already
   signed into that Jellyfin server, select **user icon → Quick Connect**, enter
   the Roku's displayed code and approve. The phone is only needed for this
   optional initial sign-in. Skip the appearance wizard if desired.
5. Open **Settings → Moonfin Plugin → Enable Plugin**. Confirm the plugin is
   found, then open **Seerr → Enable Seerr**.
6. The request session is already linked to the `ryan` Jellyfin account. If
   **Account & Sign In** asks for separate credentials, choose **Local** and use
   the dedicated Moonfin Seerr account from
   `usenet-infra/secrets/moonfin/seerr.json`. Do not select Jellyfin Account for
   this Seerr instance: it retains Plex as its primary media-server mode.
7. Browse Seerr discovery rows or use global **Search**, open a title, and choose
   its request action. For TV, select only the intended seasons. Use the normal
   request option rather than a separate 4K request: the configured default
   already prefers 2160p with 1080p fallback, without duplicate quality copies.
8. Check **Requests** for status. Requests from this dedicated account are
   automatically approved. Playback becomes available after a matching release
   is downloaded, imported and indexed by Jellyfin. An approved request can
   remain unfulfilled if no release meets the quality rules. Seerr uses Plex for
   availability, so its Available status can precede Jellyfin's library scan.

Official references: [Roku installation and sign-in](https://github.com/Moonfin-Client/Roku/wiki/Getting-Started)
and [Seerr controls](https://github.com/Moonfin-Client/Roku/wiki/Seerr-Setup).

### Authentication troubleshooting

Check the server address first, then distinguish the AD-backed Jellyfin login
from Seerr's separate account screen. The October 24 directory migration replaced
Ryan's local Jellyfin password with AD authentication while preserving the account
ID and request linkage. An older saved local password no longer authenticates
that profile; sign in again with the household AD password. The hidden local
recovery administrator is for maintenance, not normal playback. Server-side
login checks passed; Roku sign-in and playback still need user confirmation.
Passwords must never be published in this wiki or its repository.

If Jellyfin login works but Seerr request controls remain disabled, a maintainer
can run `just usenet moonfin-login`. The pinned Moonbase version can cache zero
permissions after local sign-in; this helper verifies the actual dedicated user
and repairs that cache. See the [Moonfin runbook](../../../usenet-infra/docs/jellyfin-trial.md#moonfin-requests).
Roku's Control by mobile apps setting is needed for agent remote-control checks,
not for ordinary use of Moonfin with the physical remote.

### Verified request pipeline

The October 24 public-domain test requested one season through Moonfin's server
proxy. All **36 episodes** downloaded and imported, and both Plex and Jellyfin
indexed them with the correct series identity and episode numbering. Seerr marked
the request fulfilled; the request appeared in Moonfin Web. Representative 720p
Jellyfin browser playback passed. Only this test series used a 720p profile;
global defaults stayed unchanged and later seasons remained unmonitored.
Jellyfin's initial indexing was slower than Plex's for this season. These checks
prove the server/browser workflow, not Roku playback. See the
[comparison and acceptance results](../../../usenet-infra/docs/jellyfin-trial.md#trial-verification-and-recovery)
for indexing quality, playback limitations and backup scope.

## Provider and indexer accounts

| Page | Login to use | Keep separate from |
| --- | --- | --- |
| [NZBGeek](https://nzbgeek.info/dashboard.php?mycart) | The existing **NZBGeek website account** | The API key stored by Prowlarr; cart auto-download remains off. |
| [NZBFinder](https://nzbfinder.ws/cart) | The existing **NZBFinder website account** | The API key stored by Prowlarr; cart auto-download remains off. |
| [My Eweka](https://www.eweka.nl/en/myeweka) | The existing **Eweka account** for provider account management | The household Authelia login used for SABnzbd browser access. SAB's provider connection credentials are stored in its private configuration. |
| [Hetzner Console](https://console.hetzner.com/) | The existing **Hetzner account** owning the cloud server and Storage Box | Cloud API tokens, server SSH keys, and Storage Box service/subaccount credentials. None is a console password. |

## Where to find the saved login

Use the existing saved credentials for the named service. This page intentionally
contains account roles and known non-secret account names, not passwords, API keys,
Plex PINs, personal email addresses or recovery keys: its source lives in a public
repository and the retained LAN wiki entrances are unauthenticated. The preferred
HTTPS entrance requires Authelia MFA; neither entrance may publish secrets.

- **Filex:** the private operator login is saved at
  `usenet-infra/secrets/filex/operator-login.txt` on the maintainer's checkout.
  This is a local file location, not a downloadable wiki link.
- **Household SSO and Jellyfin:** use your AD identity and password; browser MFA
  applies at Authelia-protected entrances. SMB uses the same directory password,
  independently of browser sign-in.
- **Legacy catalog / numeric cloud recovery login:** deployment material is in
  `usenet-infra/secrets/dashboard-auth.json`. It contains an Argon2id **hash**, not
  a readable password. Use the saved original login; do not paste the hash into a
  password prompt.
- **Other accounts:** use the existing account entry saved for that service.
  Exact personal account names and password-manager item titles are not documented
  here, so this directory does not invent them. If saved credentials are missing,
  follow [account and credential recovery](../../../usenet-infra/docs/account-setup.md)
  rather than creating duplicate accounts or resetting a working service.

## Related guides

- [Media and storage overview](usenet.md): how requests, downloads, libraries and NAS copies connect.
- [Seerr requests and login policy](../../../usenet-infra/docs/seerr.md).
- [Household directory, browser SSO and native-client boundaries](../../../docs/operations/household-identity.md).
- [Private cloud access and browser authentication](../../../usenet-infra/docs/lan-ui.md).
- [Filex access and operator restrictions](../../../usenet-infra/docs/filex.md).
- [NAS and Plex library layout](../../../usenet-infra/docs/nas-plex-layout.md).
- [Configuration backups](../../../usenet-infra/docs/scheduled-backups.md).

This directory documents the repository's access configuration. It does not test
passwords, change accounts, or establish that every service is currently online.

## Security maintenance

Seerr now runs pinned stable 3.5.1 with its existing account and client mappings.
QNAP firmware and Plex package updates are prepared but still require a renewed
QTS administrator session. See the [security findings and remediation status](../../../usenet-infra/docs/security-findings.md)
for the historical-key audit, backup ownership repair and unapplied history-cleanup
preview. Browser SSO does not replace native Plex or SMB authentication.
