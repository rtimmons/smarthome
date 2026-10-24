# Usenet pages and logins

Use this directory to open the right service and identify which account to use.
The household services need the home network or their existing private access
route. Filex additionally needs a tunnel running on the computer opening it.

## Household services

| Page | What it is for | Login to use |
| --- | --- | --- |
| [Seerr](http://10.77.0.1:15055/) | Browse and request movies or TV | **Sign in with Plex**, using the existing owner account. The dedicated Moonfin local login is also enabled; automatic registration remains disabled. |
| [Plex](http://192.168.1.66:32400/web) | Watch the NAS and Remote libraries | Your existing **Plex account**. For ordinary household viewing, select the **Movies & TV** profile after signing in; its profile/PIN choice is separate from the account login. |
| [Jellyfin trial](http://192.168.1.66:8096/) | Try the four general libraries alongside Plex | Separate **Jellyfin account**; private login is in `usenet-infra/secrets/jellyfin/operator.json` on the maintainer’s checkout. |
| [Moonfin](http://192.168.1.66:8096/Moonfin/Web/) | Jellyfin playback and integrated Seerr requests | Use the Jellyfin account. Its dedicated request session is configured server-side; Roku app setup remains a user step. See the [Moonfin runbook](../../../usenet-infra/docs/jellyfin-trial.md#moonfin-requests). |
| [NAS copies / catalog dashboard](http://192.168.1.66:1337/) | Select local copies and follow transfers | The existing **catalog dashboard username and password**. This is not the QNAP administration account. |
| [SABnzbd](http://10.77.0.1:18080/) | Download queue, speed, repair and unpacking | At the browser authentication popup, use the **same catalog dashboard login as NAS copies**. These are not the Eweka provider credentials. |
| [Prowlarr](http://10.77.0.1:19696/) | Indexer connections and search status | First use the **catalog dashboard login** at the browser popup, then the existing **Prowlarr account** on its application login page. These are two separate checks. |
| [Radarr](http://10.77.0.1:19696/radarr/) | Movie requests, release selection and import history | The **catalog dashboard login** at the browser popup. If an additional application sign-in appears, use the existing **Radarr account**, not a guessed default; its account name is not recorded in the public runbook. |
| [Sonarr](http://10.77.0.1:19696/sonarr/) | TV series, episodes and import history | The **catalog dashboard login** at the browser popup. If an additional application sign-in appears, use the existing **Sonarr account**, not a guessed default; its account name is not recorded in the public runbook. |
| [Filex](http://127.0.0.1:15213/) | Browse staging files and perform reviewed file operations | The saved **Filex operator account**, not its bootstrap administrator. First run `just usenet-filex-ui` from the repository root and leave it running. The link works only on that computer. |
| [QNAP administration](https://rynapqnap.local/cgi-bin/) | NAS settings and maintenance | The documented **`usenet-deploy`** administration account. This is separate from NAS copies; use it only for maintenance. Preserve the existing browser trust setup. |

**Why can there be two login prompts?** The browser popup protects the private
cloud entrance. It shares the NAS copies credential. An application login form
belongs to that application and can require a different account. A password
accepted by the popup does not imply it will work in the form.

## Roku: browse, request and watch with Moonfin

The server integration is configured. After connecting the **Moonfin** Roku app,
normal browsing, requests and playback can happen with the remote alone. The
stock Jellyfin Roku app does not expose this request workflow. Roku installation
and on-device playback remain unverified; the user deferred that device setup.

1. On Roku, search for **Moonfin** and install it from the Channel Store.
2. Open Moonfin and choose **Enter Server URL**. Enter
   `http://192.168.1.66:8096` while connected to the home network.
3. Sign in to Jellyfin as **`ryan`**, using the current private password from
   `usenet-infra/secrets/jellyfin/operator.json` on the maintainer's checkout.
   This is the Jellyfin login, not the dedicated Seerr login.
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

Check the server address first, then distinguish the initial Jellyfin login from
Seerr's separate account screen. On October 24 the user reported failures in both
Roku and the web browser. At the user's request, the Jellyfin password was changed
and a fresh API login with the replacement succeeded. Both local credential files
were updated. Subsequent user web/Roku sign-in has not yet been confirmed; the
original failure's cause was not established. Use the current private credential
file, not a password copied from an older message or recovery checkpoint.
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
| [My Eweka](https://www.eweka.nl/en/myeweka) | The existing **Eweka account** for provider account management | The catalog dashboard login used to open SABnzbd. SAB's provider connection credentials are stored in its private configuration. |
| [Hetzner Console](https://console.hetzner.com/) | The existing **Hetzner account** owning the cloud server and Storage Box | Cloud API tokens, server SSH keys, and Storage Box service/subaccount credentials. None is a console password. |

## Where to find the saved login

Use the existing saved credentials for the named service. This page intentionally
contains account roles and known non-secret account names, not passwords, API keys,
Plex PINs, personal email addresses or recovery keys: its source lives in a public
repository and the wiki itself has no login.

- **Filex:** the private operator login is saved at
  `usenet-infra/secrets/filex/operator-login.txt` on the maintainer's checkout.
  This is a local file location, not a downloadable wiki link.
- **Catalog dashboard / cloud browser popup:** deployment material is in
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
- [Private cloud access and browser authentication](../../../usenet-infra/docs/lan-ui.md).
- [Filex access and operator restrictions](../../../usenet-infra/docs/filex.md).
- [NAS and Plex library layout](../../../usenet-infra/docs/nas-plex-layout.md).
- [Configuration backups](../../../usenet-infra/docs/scheduled-backups.md).

This directory documents the repository's access configuration. It does not test
passwords, change accounts, or establish that every service is currently online.
