# Repository Guidelines

## Project Structure & Module Organization
This repository is organized as a uv-managed Python project. Core code sits under `src/printer_service/`: `app.py` serves the Flask UI/API, `label.py` provides persistence helpers and routes print jobs, while template flows live in `label_templates/` (renderer modules + SVG assets) and `templates/` (Jinja forms composed via `base.html`). The browser bundle stays in `static/app.js`. Generated labels land in `label-output/` and the gallery lists the 100 newest files straight from that directory. Add new Python modules under `src/printer_service/`, keep static assets in `static/`, and drop new template pairs into `label_templates/` + `templates/`.

## Build, Test, and Development Commands
Install uv and use the Just recipes to stay consistent:
```bash
just setup   # installs cairo, syncs deps, rebuilds cairocffi
just start   # exports env vars (LABEL_OUTPUT_DIR, DYLD paths, etc.) and runs the server
just fmt     # applies Ruff formatting in place
just test    # enforces Ruff formatting, runs mypy type-checking, and executes pytest
```
`just setup` expects Homebrew and will install `cairo`. If you install cairo manually, make sure `libcairo.2.dylib` is on the loader path (the recipe handles `DYLD_FALLBACK_LIBRARY_PATH`/`PKG_CONFIG_PATH` for you). The dependency set pins Pillow `<10` so `python-escpos` keeps working; run `uv sync --frozen` in CI to ensure lock fidelity. The service writes labels to `label-output/` using the `file` backend by default—set `PRINTER_BACKEND` to `brother-network`, `escpos-usb`, or `escpos-bluetooth` (plus the relevant env vars) when targeting real hardware. Visit `http://localhost:5000/` to use the UI; choose a template from the nav, submit the form to call `POST /labels`, and click a thumbnail to confirm-and-send `POST /print`.
The dependency set pins Pillow `<10` so libraries such as `python-escpos` keep working; run `uv sync --frozen` in CI to ensure lock fidelity. By default the service writes labels to `label-output/` using the `file` backend—set `PRINTER_BACKEND` to `brother-network`, `escpos-usb`, or `escpos-bluetooth` (plus the relevant env vars) when targeting real hardware. Hit `http://localhost:5000/` to use the UI: the form calls `POST /labels` to generate an image and the gallery fetches `GET /labels`. Click a thumbnail to confirm-and-send a `POST /print` with that filename; uploads to `/print` still work for ad-hoc files.

## Coding Style & Naming Conventions
Follow PEP 8 with four-space indentation and snake_case identifiers. Configuration values live in `PrinterConfig`, so extend that dataclass and its `from_env()` constructor instead of scattering environment lookups. File persistence helpers (`save_label_image`, `_recent_labels`) make it easy to keep the UI list snappy—reuse them rather than duplicating filesystem code. Keep Flask handlers thin by delegating logic into modules under `src/printer_service/`, and design new labels as template modules exposing `render(form_data: TemplateFormData) -> Image.Image`. Run `just fmt` before committing to keep formatting consistent.

### Label Template Interface
- Implement new templates by subclassing `TemplateDefinition` in `src/printer_service/label_templates/`.
- Provide `display_name`, `form_template`, and `render(self, form_data: TemplateFormData)` implementations; call `form_data.get_str(...)` to normalize inputs.
- Reuse the shared utilities in `printer_service.label_templates.helper` (imported as `helper`) for fonts, centered text, new image creation, choice/date normalization, and SVG rasterisation.
- Templates are responsible for drawing the full label image; there is no project-wide fallback renderer for ad hoc text lines.
- Export a module-level `TEMPLATE = Template()` (or similar) so the discovery loader registers the template automatically.
- Use the helper docstrings and type hints as the canonical reference point; they are exercised by dedicated unit tests under `tests/test_label_templates/`.

### Frontend JavaScript Conventions
The UI under `src/printer_service/static/app.js` ships directly to the browser without a bundler or transpile step, so keep it as standards-based JavaScript that Mobile Safari (iOS) and Firefox can execute as-is. Prefer incremental helpers (for example the shared `requestJson` response handler) over ad hoc `try/catch` flow-control, and return structured `{ ok, error }` objects from async utilities instead of throwing. When type hints help, lean on JSDoc comments rather than TypeScript, since introducing `.ts` files would require a build pipeline that we intentionally avoid here. All label generation must originate from a registered template; the legacy raw `"lines"` payload is no longer accepted.

## Testing Guidelines
Target behaviour with `pytest` modules under `tests/`. Mock printer backends (`brother_ql.backends.helpers.send`, `escpos.printer.Usb/Bluetooth`) to keep tests hardware-free and assert that generated images carry expected dimensions and text. Add contract tests for `/print` that cover JSON payloads, multipart uploads, invalid inputs, and backend overrides. Run `just fmt` followed by `just test` locally before opening a PR so formatting, typing, and pytest all stay green.
Existing coverage in `tests/test_app.py` seeds sample labels, verifies `/labels` ordering, ensures `/print` dispatches correctly, and exercises the template renderers (including SVG handling). Extend that module when adding API behaviour or templates; stub lower-level integrations (SVG rasterisation, printer drivers) so tests stay hardware-free.

## Commit & Pull Request Guidelines
Stick to short, imperative commit messages such as `Support ESC/POS Bluetooth printers`. Reference issue IDs where relevant and avoid bundling unrelated changes. Pull requests should outline behaviour changes, configuration updates (new env vars, default backend tweaks), and include screenshots or terminal captures that prove a `/print` request succeeded using either hardware or the file backend. Loop in reviewers who maintain the production printer setup when altering dispatcher logic.

## Security & Configuration Tips
Treat printer addresses and Bluetooth MACs as secrets—never commit production values. Share runtime settings via `.env` files ignored by git and document the expected keys (`PRINTER_BACKEND`, `BROTHER_PRINTER_URI`, `ESC_POS_VENDOR_ID`, etc.). Validate uploaded files (already enforced in `app.py`) before rendering, and keep logging minimal to avoid leaking pantry inventory or user details.
Set `LABEL_OUTPUT_DIR` when you need the UI to surface a shared directory; ensure the path is writable by the service user and periodically prune old artifacts if storage is constrained.

### Brother QL-810W quickstart
See `docs/ql810w-setup.md` for step-by-step instructions on putting a QL-810W on Wi‑Fi and enabling the raw `tcp://<ip>:9100` service used by the `brother-network` backend.
