# Daily snapshot and receipt service

This add-on supports printed daily summaries and receipt checkbox analysis. The
implemented `/snapshot` endpoint returns a checked-in fixture; it does not fetch
live weather, calendars, thermostat state or camera images. Treat the fixture's
dates and values as sample data even when the service is healthy.

## Implemented endpoints

| Method and path | Purpose |
| --- | --- |
| `GET /healthz` | Process liveness (`status: ok`); does not verify external data freshness |
| `GET /snapshot` | Fixture summary validated against the snapshot schema |
| `GET /receipt/upload` | Browser form for a photographed printed checklist |
| `POST /receipt/analyze` | Analyze one multipart upload and return checkbox results |

The receipt form sends an image with optional item labels, date and receipt ID.
The upload limit is one file of at most 15 MiB. The analyzer returns its findings;
it does not print a label or write a Home Assistant entity. Use the
[receipt guide](docs/receipt.md) for layout and image-processing details.
That guide's printing demo sends a physical print job.

The server registers no `/openapi.json` route and has no live weather/calendar
adapters. Those were development proposals, not delivered capabilities.

## Configuration and ownership

The service uses the repository-pinned Node runtime from [`.nvmrc`](../.nvmrc),
TypeScript, Fastify and Zod. [The manifest](addon.yaml) owns deployment ports and
packaging; the [server](src/server.ts) owns routes and runtime defaults.

| Environment variable | Default | Purpose |
| --- | --- | --- |
| `PORT` | `4010` | HTTP listener |
| `HOST` | `0.0.0.0` | Bind address |
| `LOG_LEVEL` | `info` | Server logging |

There is no Home Assistant ingress page declared for this add-on. Access depends
on the mapped host port and network policy. Keep uploaded household photos and
raw request evidence private.

## Development and validation

From the repository root, `just setup` installs the pinned toolchain and
`just dev` runs the local stack. In `snapshot-service`, use `just dev` for the
service alone and `just test`, `just lint`, `just typecheck`, and `just build`
for its checks. Root `just test snapshot-service` also runs the repository's
add-on/container checks.

If a daily summary looks old, first identify whether it came from `/snapshot`:
that endpoint intentionally returns the fixture. For receipt failures, separate
upload/size errors from image alignment and checkbox interpretation. A successful
health response does not prove a photographed receipt was interpreted correctly.

## Recovery

Rebuild the service from repository source and restore its configured endpoint.
The fixture and schemas are source-controlled. Printer archives and printer
application state belong to the [printer service](../printer/README.md), not this
API. Follow [add-on state backup procedures](../docs/operations/addon-state-backups.md)
for any separately persisted application state.
