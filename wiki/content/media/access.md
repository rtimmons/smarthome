# Usenet pages and logins

Use this directory to open the right service and identify which account to use.
The household services need the home network or their existing private access
route. Filex additionally needs a tunnel running on the computer opening it.

## Household services

| Page | What it is for | Login to use |
| --- | --- | --- |
| [Seerr](http://10.77.0.1:15055/) | Browse and request movies or TV | **Sign in with Plex**, using the existing Plex **owner account**. Local username/password login and automatic registration are disabled. |
| [Plex](http://192.168.1.66:32400/web) | Watch the NAS and Remote libraries | Your existing **Plex account**. For ordinary household viewing, select the **Movies & TV** profile after signing in; its profile/PIN choice is separate from the account login. |
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
