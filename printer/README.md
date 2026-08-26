# Printer Service

Kitchen label printing service for Home Assistant.

## Quick Start

```bash
# Option 1: Start all services from repo root
cd /path/to/smarthome
just dev          # Starts all services including printer

# Option 2: Start only printer service
cd printer
just start        # Starts just the printer service
```

The printer service will be available at http://localhost:8099
Use the header emoji picker (☀️/🌙/🖥️) to switch between light, dark, and system themes.

The **PNG Upload** navigation route accepts drag-and-dropped PNG files, validates and
fits them to the 62 mm × 1.3-inch label canvas, and uses the standard print countdown.
When a print is confirmed, the prepared PNG is archived in `/data/printed-labels`, the
printer add-on's Supervisor-backed data directory. The PNG Upload page lists that
archive and supports previewing, downloading, reprinting, and deleting saved labels.
Local development uses `printer/label-output/printed-labels` by default and can be
overridden with `PRINTED_LABELS_DIR`.

### Print a PNG from the repository

From the repository root, validate and print a PNG with:

```bash
just print durban.png
```

The command validates the file locally with the same rules as the upload page, sends
it to `/png/preview` as a non-printing server preflight, then sends exactly one request
to `/png/print`. It never retries the print request: after a network timeout, check the
physical printer before deciding whether to run it again.

Two helpers make endpoint and authentication setup testable without using a label:

```bash
just printer-config          # resolved URLs/auth source; never prints a token
just print-check durban.png  # local validation plus remote preview; does not print
```

By default the client uses the add-on's mapped direct endpoint at
`http://${HA_HOST:-homeassistant.local}:8099/`, which does not require Home Assistant
ingress authentication. Configuration precedence is:

- `PRINTER_SERVICE_URL` for a complete base URL, or the component variables
  `PRINTER_SERVICE_SCHEME`, `PRINTER_SERVICE_HOST`, `PRINTER_SERVICE_PORT`, and
  `PRINTER_SERVICE_PATH`.
- The add-on-compatible `PUBLIC_SERVICE_*` variables, with `HA_HOST` as the host
  fallback.
- `PRINTER_SERVICE_TOKEN_FILE` for a bearer token required by a trusted reverse
  proxy. The file must be mode `0600`; `PRINTER_SERVICE_TOKEN` is also supported for
  ephemeral environments but is easier to expose through shell/process state.
- `PRINTER_SERVICE_CA_FILE` for a private HTTPS certificate authority and
  `PRINTER_SERVICE_TIMEOUT` for the request timeout (45 seconds by default).

Credentials embedded in URLs and HTTP redirects are rejected so a print body or
bearer token cannot be forwarded to an unexpected host. Server preflights remain
in-memory only; a confirmed print is retained in the printed-label archive.

## Build the Home Assistant Add-on Image

Build the talos add-on payload and a local container image to catch Dockerfile issues before deploying:

```bash
# From repo root
just printer-image

# Or from printer/
just build

# Optional: match a specific architecture for container build
PRINTER_DOCKER_PLATFORM=linux/arm64 just printer-image
```

The system automatically detects and uses `podman` (preferred) or `docker` (fallback). See [../docs/addon-development/container-runtime.md](../docs/addon-development/container-runtime.md) for details.

## TODO

1. Make the URL params shorter or perhaps just remove them entirely and instead just have them be ordered params and keep the order consistent over time. So `/bb?t=abc&v=1&p=a,b,c` for `t` being the template name, `v` being a version for backward-compatibility if we change the order or template names or params/order, and `p` being a comma-separated list of the params, being careful to handle the case where the params have commas themselves. We don't need to be backward-compatible with old URLs for this update.
1. Make the print URL (`?print=true`) render the HTML that then uses javascript to trigger the actual print with a countdown timer. This way the user can preview and modify the label from the QR code before printing it.

## Development

### Running Tests

```bash
# Run all tests (includes formatting, type checking, and pytest)
cd printer
just test

# For more specific test runs, use pytest directly:
.venv/bin/pytest tests/ -v                    # All tests with verbose output
.venv/bin/pytest tests/test_visual_regression.py -v   # Specific file
.venv/bin/pytest tests/ -k bluey -v           # Tests matching keyword
```

For comprehensive testing documentation, see [docs/testing.md](./docs/testing.md).

### Visual Regression Tests

The printer service has a comprehensive test suite covering all functionality:

```bash
# Run the full test suite (includes dark mode test)
just test

# Run only the main pytest suite
.venv/bin/python -m pytest

# Run only visual regression tests
.venv/bin/pytest tests/test_visual_regression.py -v

# Regenerate baselines after intentional visual changes
.venv/bin/pytest tests/test_visual_regression.py --regenerate-baselines -v

# Run dark mode test separately
.venv/bin/python tests/test_dark_mode_standalone.py
```

**Note:** The dark mode test runs separately to avoid asyncio conflicts with the main Playwright-based test suite.

See [docs/testing.md](./docs/testing.md) for details.

## Printer Setup

### Brother QL-810W Network Printing

For instructions on setting up a Brother QL-810W printer for network printing, see:
- [docs/ql810w-setup.md](./docs/ql810w-setup.md) - Initial setup
- [docs/ql810w-troubleshooting.md](./docs/ql810w-troubleshooting.md) - Troubleshooting connectivity issues

### Configuration

Set these environment variables in your Home Assistant add-on configuration:

```yaml
PRINTER_BACKEND: "brother-network"
BROTHER_PRINTER_URI: "tcp://192.168.1.192:9100"
BROTHER_MODEL: "QL-810W"
BROTHER_LABEL: "62x29"
MONGODB_URL: "mongodb://local-mongodb:27017/smarthome"
```

Presets are stored in MongoDB. Configure `mongodb_url` in the add-on options (or
set `MONGODB_URL` when running locally). See [addon.yaml](./addon.yaml) for all
available configuration options.
The service prefers Supervisor's canonical `local-mongodb` hostname and also
tries its FQDN and legacy add-on hostnames for existing configurations.

## Label Templates

The printer service supports multiple label templates:

- **best_by** - Date-based labels with QR code support
- **bluey_label** - Decorative character labels (Line 1/Line 2/Side/Symbol/Bottom free text)

Templates are auto-discovered from `src/printer_service/label_templates/`.

## Architecture

```
printer/
├── src/printer_service/
│   ├── app.py                    # Flask application
│   ├── label.py                  # Label generation and printing
│   ├── label_specs.py            # Brother printer specifications
│   └── label_templates/          # Template modules
│       ├── base.py               # Template abstraction
│       ├── helper.py             # Drawing utilities
│       └── *.py                  # Individual templates
├── tests/
│   ├── test_app.py               # Flask API tests
│   ├── test_visual_regression.py # Visual regression tests
│   ├── baselines/                # Visual regression baselines
│   └── test_label_templates/     # Template unit tests
└── docs/
    ├── testing.md                # Testing guide
    ├── ql810w-setup.md           # Printer setup
    └── ql810w-troubleshooting.md # Troubleshooting

```

## Documentation

- [docs/testing.md](./docs/testing.md) - Comprehensive testing guide
- [docs/presets.md](./docs/presets.md) - Preset storage and QR shortcuts
- [docs/ql810w-setup.md](./docs/ql810w-setup.md) - Brother QL-810W setup
- [docs/ql810w-troubleshooting.md](./docs/ql810w-troubleshooting.md) - Printer troubleshooting

For project-wide documentation, see the repo guide at `../AGENTS.md`.
