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
.venv/bin/pytest tests/ -k kitchen -v         # Tests matching keyword
```

For comprehensive testing documentation, see [docs/testing.md](./docs/testing.md).

### Visual Regression Tests

The printer service has a comprehensive test suite with 75 tests covering all functionality:

```bash
# Run the full test suite (includes dark mode test)
just test

# Run only the main pytest suite (74 tests)
.venv/bin/python -m pytest

# Run only visual regression tests
.venv/bin/pytest tests/test_visual_regression.py -v

# Regenerate baselines after intentional visual changes
.venv/bin/pytest tests/test_visual_regression.py --regenerate-baselines -v

# Run dark mode test separately
python tests/test_dark_mode_standalone.py
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
MONGODB_URL: "mongodb://addon_local_mongodb:27017/smarthome"
```

Presets are stored in MongoDB. Configure `mongodb_url` in the add-on options (or
set `MONGODB_URL` when running locally). See [addon.yaml](./addon.yaml) for all
available configuration options.
If your MongoDB add-on is installed from a non-local repository, use
`mongodb://addon_mongodb:27017/smarthome`; the service will also try
`addon_mongodb` and `mongodb` hosts if the configured one is unreachable.

## Label Templates

The printer service supports multiple label templates:

- **best_by** - Date-based labels with QR code support
- **receipt_checklist** - Checklist with checkboxes
- **bluey_label** - Decorative character labels
- **daily_snapshot** - Calendar and date display

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
