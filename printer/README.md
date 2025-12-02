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

The printer service uses visual regression testing to ensure refactoring doesn't change label rendering:

```bash
# Run all tests including visual regression
just test

# Run only visual regression tests
.venv/bin/pytest tests/test_visual_regression.py -v

# Regenerate baselines after intentional visual changes
.venv/bin/pytest tests/test_visual_regression.py --regenerate-baselines -v
```

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
```

See [addon.yaml](./addon.yaml) for all available configuration options.

## Label Templates

The printer service supports multiple label templates:

- **best_by** - Date-based labels with QR code support
- **kitchen_label_printer** - Simple multi-line text labels
- **receipt_checklist** - Checklist with checkboxes
- **bluey_label** / **bluey_label_2** - Decorative character labels
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
- [docs/ql810w-setup.md](./docs/ql810w-setup.md) - Brother QL-810W setup
- [docs/ql810w-troubleshooting.md](./docs/ql810w-troubleshooting.md) - Printer troubleshooting

For project-wide documentation, see the [main repo CLAUDE.md](../CLAUDE.md).
