# TinyURL Service

Tiny URL management add-on with a simple web UI and REST API. Create short links, see total visits, inspect the last 10 access timestamps, reset stats, and delete entries. Redirects live at `/ <slug>`; the UI and API live at `/` and `/api`.

## Features

- Auto-generated slugs (a-z, 2-9, optional dashes; no 0/1/O/I/L; max length 10; no leading/trailing/repeated dashes)
- MongoDB-backed storage (defaults to the bundled MongoDB add-on at `addon_local_mongodb`)
- Visit tracking with total count and last 10 timestamps
- Reset and delete controls; duplicate targets reuse the same slug
- Ingress-enabled web UI; optional host port `4100`

## Endpoints

- `GET /healthz` — liveness probe
- `GET /api/urls` — list all tiny URLs with stats
- `POST /api/urls` — create a new tiny URL  
  Body: `{ "url": "https://example.com" }`
- `POST /api/urls/:slug/reset` — reset counters and visit history
- `DELETE /api/urls/:slug` — delete an entry
- `GET /:slug` — redirect to the target URL and record the visit

## Configuration

- `mongodb_url` (option / env `MONGODB_URL`): MongoDB connection string  
  Default: `mongodb://addon_local_mongodb:27017/tinyurl` (use `addon_mongodb` if installed from a non-local add-on repository). On startup the service will also try the other known add-on hosts (`addon_mongodb`, `mongodb`) if the first host is unreachable.
- `public_base_url` (option / env `PUBLIC_BASE_URL`): External base URL to use when copying short links (e.g., `http://homeassistant.local:4100`). If empty, the UI will fall back to `http://<hostname>:4100`.

## Local development

```bash
cd tinyurl-service
just setup     # install deps
just dev       # start Fastify in watch mode on http://localhost:4100
just test      # run vitest
just lint      # eslint
just typecheck # tsc --noEmit
just build     # compile to dist/
```
