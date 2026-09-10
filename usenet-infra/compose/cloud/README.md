# Cloud applications

This Compose project runs SABnzbd and Prowlarr on the acquisition host. Both web interfaces listen only on the host loopback address; neither service is directly reachable from the Internet.

## Prepare and start

Create the persistent directories on the cloud host and make them writable by the numeric `PUID` and `PGID` selected for the containers:

```text
/srv/usenet/config/sabnzbd
/srv/usenet/config/prowlarr
/srv/usenet/downloads/incomplete
/srv/usenet/downloads/complete
```

Copy `.env.example` to `.env`, set `PUID`, `PGID`, and `TZ`, then start the project from this directory:

```sh
docker compose pull
docker compose up -d
docker compose ps
```

The environment file is only for non-secret runtime values. Do not add provider passwords, indexer keys, application API keys, or other credentials to it or commit those values to Git.

## Reach the interfaces

Open an SSH tunnel from an administrator workstation, replacing the login and host:

```sh
ssh \
  -L 8080:127.0.0.1:8080 \
  -L 9696:127.0.0.1:9696 \
  operator@cloud-host
```

While the tunnel is open, SABnzbd is available at `http://127.0.0.1:8080` and Prowlarr at `http://127.0.0.1:9696`. If either host port is changed in `.env`, use the changed port in the tunnel and local URL.

## Initial configuration

- In SABnzbd, use `/data/incomplete` and `/data/complete` for the temporary and completed download folders. Configure NNTP providers with TLS and strict certificate verification only.
- In Prowlarr, address SABnzbd as `http://sabnzbd:8080`; the Compose service network resolves `sabnzbd` internally.
- Enable application authentication even though both UIs are loopback-only, generate separate full API keys for the health script, and keep those keys only in the protected runtime `catalog.env` file.
- Enter credentials only through the tunneled interfaces or the repository's encrypted-secret workflow. Application configuration, including credentials entered in the interfaces, persists under `/srv/usenet/config`; protect and back up those directories accordingly.
- Keep the host firewall closed to ports 8080 and 9696. The loopback bindings are intentional and must not be changed to `0.0.0.0`.

The image tags include both the upstream application version and the LinuxServer build number. Update them deliberately and recreate the containers; do not replace them with floating `latest` tags.
