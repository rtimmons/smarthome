# Presets

Named presets store label form URL parameters in MongoDB so the UI can recall common labels and generate shorter QR URLs via `/p/<slug>`.

## References
- `../AGENTS.md` (repo ground rules, `just` workflows, git lock)
- `docs/testing.md` (test commands and conventions)
- `src/printer_service/app.py` (Flask routes, QR URL generation)
- `src/printer_service/templates/base.html` (form layout)
- `src/printer_service/static/app.js` (form state, preview + QR URL display)
- `../mongodb/AGENTS.md` (MongoDB add-on usage, if needed)

## Feature overview
- "Save preset" controls live below the left-side label form.
- Saving prompts for a name; presets store current URL params (including template).
- Saving a preset refreshes the preview so the QR URL updates to `/p/<slug>` immediately.
- The full-width presets table shows name, slug, template, date added, successful print count,
  and actions.
- Every data column is sortable. The default is newest date added first.
- Presets can be deleted.
- Presets are stored in MongoDB (via the mongodb add-on).
- Presets require `pymongo` as a core dependency (not optional).
- Use `.venv/bin/python` for helper scripts in this doc so dependencies (including `pymongo`) are available.
- `/p/<slug>` redirects to the full `/bb?...` URL.
- Slug is a stable hash of canonical form values, max 64 bits, URL-safe.
- When generating QR URLs, use `/p/<slug>` if a matching preset exists; otherwise use the full URL.
- Ensure printer add-on works when mongodb is running locally via `just dev` at repo root.

## MongoDB connection
- Add-on option: `mongodb_url` (env `MONGODB_URL`) for the full Mongo connection string.
- Local dev default: `mongodb://localhost:27017/smarthome` when `PRINTER_DEV_RELOAD=1`.
- Add-on expectation: `mongodb://addon_local_mongodb:27017/smarthome` (Supervisor exposes add-ons as `addon_<slug>`, so use `addon_mongodb` for non-local installs; the service also falls back to `addon_mongodb` and `mongodb`; talos rewrites to localhost for local dev runs).
- Health check: `GET /health/mongo` reports connection status; the app logs one Mongo status line on first request.

## Data model (MongoDB)
- Collection: `presets`
- Fields:
  - `slug` (string, URL-safe, derived from 64-bit hash)
  - `name` (string)
  - `template` (string, template slug)
  - `query` (string, canonical query string)
  - `params` (object form, optional)
  - `created_at`, `updated_at` (UTC ISO strings)
  - `print_count` (integer, defaults to `0` for existing documents)

## Routing and behavior
- `GET /p/<slug>`: lookup preset, redirect to `/bb?...` with stored params.
- `GET /presets`: list presets. Defaults to `sort=created&direction=desc`; supported sort
  values are `name`, `slug`, `template`, `created`, `updated`, and `prints`.
- `POST /presets`: create/update preset with name + current params.
- `DELETE /presets/<slug>`: delete preset.
- QR URL generation path:
  - Build canonical query (template + params).
  - If a preset with matching slug exists, use `/p/<slug>` for QR.
  - Otherwise fall back to the full `/bb?...` URL.
- After a print dispatch succeeds, the service looks up a preset matching the canonical form
  values and atomically increments its `print_count`. Counting is best-effort: a MongoDB error
  never turns an already-dispatched label into a failed response that might cause a duplicate
  retry. A print request counts once, including QR or jar variants.

## UI framework decision

Do not add MUI for the presets table. The printer UI is server-rendered Jinja with one vanilla
JavaScript file and has no React runtime, package manager, or frontend build step. A native
semantic table, the existing CSS variables, and small sorting handlers provide the required
interaction and accessibility without adding React, Emotion, and a new asset pipeline. Revisit a
component framework only if the printer UI is intentionally moving to a broader React application
with several shared, complex interactive views.

## Slug hashing (64-bit, URL-safe)
- Canonicalize params: stable key order, normalized template slug, list handling, empty values removed.
- Hash: `blake2b` truncated to 8 bytes (64-bit).
- Encode: URL-safe base64 without padding (ASCII only).

## Testing
- Automated:
  - `just test`
  - Focused runs: `.venv/bin/pytest tests/ -k preset -v`
  - Key coverage: `tests/test_app.py`, `tests/test_presets.py`, `tests/test_preset_store.py`,
    `tests/test_presets_ui.py`
- Manual (local dev):
  - From repo root: `just dev` (ensure mongodb is running).
  - Load printer UI, save a preset, reload page, verify list persists.
  - Delete preset and confirm it is removed and `/p/<slug>` 404s.
  - Confirm QR preview URL switches to `/p/<slug>` for saved presets.
- Manual (curl demo):
  - Known slug fixture: `hvS2eIbWbE0` for `best_by` + `Text=Fresh Pasta`, `Prefix=Use by`, `Delta=3 days`.
  - Check missing preset redirect (expect 404 before create):
    ```bash
    curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8099/p/hvS2eIbWbE0
    ```
  - Create preset (expect 200 with `preset.slug == "hvS2eIbWbE0"` and `preset.query`):
    ```bash
    curl -s -X POST http://localhost:8099/presets \
      -H 'Content-Type: application/json' \
      -d '{"name":"Fresh Pasta","template":"best_by","data":{"Text":"Fresh Pasta","Prefix":"Use by","Delta":"3 days"}}'
    ```
  - Confirm redirect now exists (expect `302` and `/bb?tpl=best_by&Delta=3+days&Prefix=Use+by&Text=Fresh+Pasta`):
    ```bash
    curl -s -o /dev/null -w "%{http_code} %{redirect_url}\n" http://localhost:8099/p/hvS2eIbWbE0
    ```
  - Delete preset (expect `{"deleted": true, "slug": "hvS2eIbWbE0"}`):
    ```bash
    curl -s -X DELETE http://localhost:8099/presets/hvS2eIbWbE0
    ```
  - Confirm missing again (expect 404):
    ```bash
    curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8099/p/hvS2eIbWbE0
    ```
  - If using a different slug, recompute it from the canonical query string rules and substitute it in the commands.
- QR scannability check: ensure generated QR images have module size >= 4 px and quiet zone >= 4 modules (compute from QR metadata in `label_templates`), and verify QR payload length for saved presets is materially shorter (e.g., <= 60 chars for typical bluey labels).
