# Presets

Named presets store label form URL parameters in MongoDB so the UI can recall common labels and generate shorter QR URLs via `/p/<slug>`.

## References
- `../AGENTS.md` (repo ground rules, `just` workflows, git lock)
- `docs/testing.md` (test commands and conventions)
- `src/printer_service/app.py` (Flask routes, QR URL generation)
- `src/printer_service/templates/base.html` (form layout)
- `src/printer_service/static/app.js` (form state, preview + QR URL display)
- `../mongodb/AGENTS.md` (MongoDB add-on usage, if needed)

## Requirements
- Add "Save preset" controls below the left-side label form.
- Saving prompts for a name; preset stores current URL params (including template).
- List presets (name, slug, template, actions) below the save controls.
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
- Add-on expectation: `mongodb://mongodb:27017/smarthome` (talos rewrites to localhost for local dev runs).
- Health check: `GET /health/mongo` reports connection status; the app logs one Mongo status line on first request.

## Data model (MongoDB)
- Collection: `presets`
- Fields:
  - `slug` (string, URL-safe, derived from 64-bit hash)
  - `name` (string)
  - `template` (string, template slug)
  - `query` (string, canonical query string) or `params` (object form)
  - `created_at`, `updated_at` (UTC ISO strings)

## Routing and behavior
- `GET /p/<slug>`: lookup preset, redirect to `/bb?...` with stored params.
- `GET /presets`: list presets (sorted by name or updated time).
- `POST /presets`: create/update preset with name + current params.
- `DELETE /presets/<slug>`: delete preset.
- QR URL generation path:
  - Build canonical query (template + params).
  - If a preset with matching slug exists, use `/p/<slug>` for QR.
  - Otherwise fall back to the full `/bb?...` URL.

## Slug hashing (64-bit, URL-safe)
- Canonicalize params: stable key order, normalized template slug, list handling, empty values removed.
- Hash: `blake2b` or `sha256` truncated to 8 bytes (64-bit).
- Encode: URL-safe base64/base32 without padding (ASCII only).

## Plan / State
- Status: In progress
- Checklist:
  - [x] Confirm MongoDB connection details in local dev (`just dev` root; `../mongodb/AGENTS.md`).
    - Validation: document connection URI/env vars in this file and verify with a one-off health check endpoint or Mongo ping.
    - Demo: run `just dev` (repo root), open printer UI at `http://localhost:8099`, and confirm logs show Mongo connection.
  - [x] Add preset storage module (Mongo client, canonicalization, hash/slug helpers).
    - Validation: unit tests for canonicalization (stable key order, list handling, empty values), hash determinism, and slug encoding.
    - Demo: run `.venv/bin/python tests/test_presets.py` to print slug + canonical query for known inputs.
  - [x] Add Flask endpoints for list/create/delete and `/p/<slug>` redirect.
    - Validation: integration tests in `tests/test_app.py` for CRUD and redirect (200/404 cases).
    - Demo: `curl` create/list/delete + open `/p/<slug>` in browser to confirm redirect.
  - [x] Wire QR URL generation to prefer preset route when slug exists.
    - Validation: unit/integration test asserting QR preview `print_url` uses `/p/<slug>` when preset exists and full `/bb?...` otherwise.
    - Demo: save preset, refresh preview, confirm QR URL text switches to `/p/<slug>`.
  - [x] Update UI (`base.html`, `app.js`) for save + list + delete.
    - Validation: Playwright or DOM tests if available; otherwise add app.js unit tests for preset list rendering and deletion flow.
    - Demo: create two presets, verify list order, delete one, ensure UI and DB reflect removal.
  - [x] Add tests for hashing, storage, routes, QR URL shortening.
    - Validation: `just test` passes with new tests.
    - Demo: run targeted tests (pytest -k preset) and review output.
  - [ ] Update docs and any add-on config needed for MongoDB.
    - Validation: docs reference Mongo env vars, local dev instructions updated, and add-on config validated.
    - Demo: rebuild container (`just build`) and confirm app starts with Mongo enabled.

## Test plan
- Automated:
  - `just test`
  - Add API tests in `tests/test_app.py` for `/presets` and `/p/<slug>`.
  - Add unit tests for canonicalization + slug hashing determinism.
  - Add QR URL shortening tests to ensure preset routes are used when present.
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
- Success criteria:
  - QR scannability metric: ensure generated QR images have module size >= 4 px and quiet zone >= 4 modules (compute from QR metadata in `label_templates`), and verify QR payload length for saved presets is materially shorter (e.g., <= 60 chars for typical bluey labels).
