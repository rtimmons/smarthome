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
- `/p/<slug>` redirects to the full `/bb?...` URL.
- Slug is a stable hash of canonical form values, max 64 bits, URL-safe.
- When generating QR URLs, use `/p/<slug>` if a matching preset exists; otherwise use the full URL.
- Ensure printer add-on works when mongodb is running locally via `just dev` at repo root.

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
- Status: Draft
- Checklist:
  - [ ] Confirm MongoDB connection details in local dev (`just dev` root; `../mongodb/AGENTS.md`).
  - [ ] Add preset storage module (Mongo client, canonicalization, hash/slug helpers).
  - [ ] Add Flask endpoints for list/create/delete and `/p/<slug>` redirect.
  - [ ] Wire QR URL generation to prefer preset route when slug exists.
  - [ ] Update UI (`base.html`, `app.js`) for save + list + delete.
  - [ ] Add tests for hashing, storage, routes, QR URL shortening.
  - [ ] Update docs and any add-on config needed for MongoDB.

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
- Success criteria:
  - QR scannability metric: ensure generated QR images have module size >= 4 px and quiet zone >= 4 modules (compute from QR metadata in `label_templates`), and verify QR payload length for saved presets is materially shorter (e.g., <= 60 chars for typical bluey labels).
