# Talos Architecture & Design

**Talos** is the isolated build/deployment/dev toolchain for the smarthome repository. It provides a unified, declarative interface for building Home Assistant add-ons, running local development environments, and managing deployments.

## Design Principles

1. **Self-Contained**: Talos runs in its own isolated virtualenv to avoid conflicts with add-on runtimes
2. **Declarative**: Add-ons declare their requirements in `addon.yaml`; talos handles the implementation
3. **Auto-Discovery**: Add-ons are discovered via glob patterns (`*/addon.yaml`) enabling symlinks and cross-repo add-ons
4. **Single Source of Truth**: Runtime versions come from `.nvmrc` and `.python-version` in repo root
5. **Template-Based**: Docker images, configs, and run scripts are generated from Jinja2 templates
6. **Hook-Based**: Add-ons can provide lifecycle hooks for custom setup/validation logic

## Directory Structure

```
talos/
├── build.sh                    # Builds talos CLI into isolated venv
├── setup_dev_env.sh           # Automated first-time environment setup
├── README.md                   # Quick start guide
├── pyproject.toml             # Python package definition
├── build/
│   ├── venv/                   # Isolated Python environment
│   └── bin/talos → venv/bin/talos
├── src/talos/
│   ├── cli.py                  # Click-based CLI entry point
│   ├── paths.py                # Path constants (REPO_ROOT, TALOS_ROOT, etc.)
│   ├── addon_builder.py        # Add-on discovery, build, deploy logic
│   ├── dev.py                  # Local dev orchestrator with dependency resolution
│   ├── hooks.py                # Lifecycle hook execution
│   ├── addons_runner.py        # Batch just recipe execution across add-ons
│   ├── manage_ports.py         # Port conflict detection and cleanup
│   └── templates/              # Jinja2 templates for generated files
│       ├── Dockerfile.j2       # Generates Dockerfile based on runtime (Node/Python)
│       ├── config.yaml.j2      # Home Assistant add-on config
│       ├── run.sh.j2           # Container entry point
│       ├── README.md.j2        # Add-on README
│       ├── DOCS.md.j2          # Add-on documentation
│       ├── apparmor.txt.j2     # AppArmor profile
│       └── translations_en.yaml.j2
├── just/
│   └── nvm.just                # Shared justfile include for nvm usage
├── scripts/
│   └── nvm_use.sh              # Shell script to load and use correct nvm version
└── tests/
    ├── test_addon_builder.py
    ├── test_cli.py
    ├── test_nvm_use.py
    └── test_printer_setup.py
```

## Core Components

### 1. Path Management (`paths.py`)

Centralizes all path calculations to ensure consistency:

```python
PACKAGE_ROOT = Path(__file__).resolve().parents[0]  # talos/src/talos
TALOS_ROOT = PACKAGE_ROOT.parents[1]                # talos/
REPO_ROOT = TALOS_ROOT.parent                        # smarthome/
TEMPLATE_DIR = TALOS_ROOT / "templates"              # talos/src/talos/templates (via pyproject.toml)
ADDON_BUILD_ROOT = REPO_ROOT / "build" / "home-assistant-addon"
```

**Why this matters**: All talos modules import from `paths.py` ensuring that regardless of how talos is invoked (from repo root, from add-on dir, via just, etc.), paths are always correct.

### 2. Add-on Discovery (`addon_builder.py`)

Auto-discovers add-ons by globbing for `*/addon.yaml` files:

```python
def discover_addons() -> Dict[str, Any]:
    """Discover all addons by finding */addon.yaml files in the repo."""
    addons: Dict[str, Any] = {}
    for addon_yaml in REPO_ROOT.glob("*/addon.yaml"):
        addon_dir = addon_yaml.parent
        addon_key = addon_dir.name
        data = yaml.safe_load(addon_yaml.read_text())
        # Derive source_dir from addon.yaml location and source_subdir
        addons[addon_key] = data
    return addons
```

**Benefits**:
- **Symlink support**: Add add-ons from other repositories via symlinks
- **Decentralized**: No central manifest file to update
- **Simple**: Just create `<name>/addon.yaml` and talos finds it

### 3. Version Management

Runtime versions are read from repository root files and injected into:
1. **Local development** (via nvm/pyenv)
2. **Docker base images** (via template rendering)
3. **Documentation comments** (for transparency)

```python
def read_runtime_versions() -> Dict[str, str]:
    """Read runtime versions from .nvmrc and .python-version files."""
    versions = {}

    # Node.js from .nvmrc
    nvmrc_path = REPO_ROOT / ".nvmrc"
    if nvmrc_path.exists():
        versions["node"] = nvmrc_path.read_text().strip().lstrip("v")
        versions["node_major"] = versions["node"].split(".")[0]

    # Python from .python-version
    python_version_path = REPO_ROOT / ".python-version"
    if python_version_path.exists():
        versions["python"] = python_version_path.read_text().strip()
        versions["python_minor"] = ".".join(versions["python"].split(".")[:2])

    return versions
```

### 4. Template Engine (`addon_builder.py`)

Uses Jinja2 to generate Dockerfiles, configs, and scripts:

```python
def build_context(addon_key: str, manifest: Dict[str, Any]) -> Dict[str, Any]:
    """Build template context from addon.yaml and runtime versions."""
    runtime_versions = read_runtime_versions()
    addon_config = manifest[addon_key]

    return {
        "addon": {
            "key": addon_key,
            "slug": addon_config["slug"],
            "name": addon_config["name"],
            "node_version": runtime_versions["node"],
            "python_version": runtime_versions["python"],
            # ... many more fields
        }
    }
```

Templates receive the full context and generate appropriate configs for Node vs Python add-ons.

### 5. Dev Orchestrator (`dev.py`)

Sophisticated async orchestrator that:
1. Discovers add-ons
2. Resolves dependencies from `run_env` URLs
3. Performs topological sort for startup order
4. Checks prerequisites (node_modules, uv.lock)
5. Runs lifecycle hooks (pre_start)
6. Launches processes with appropriate env vars
7. Multiplexes logs with timestamps and colors
8. Handles graceful shutdown

**Dependency detection** (automatically infers from environment variables):
```python
def get_dependencies(self) -> Set[str]:
    """Infer dependencies from run_env URL references."""
    deps = set()
    for env_spec in self.run_env:
        default_val = env_spec.get("default", "")
        if "local-node-sonos-http-api" in default_val:
            deps.add("node-sonos-http-api")
        if "local-sonos-api" in default_val:
            deps.add("sonos-api")
    return deps
```

### 6. Lifecycle Hooks (`hooks.py`)

Add-ons can provide executable hooks in `<addon>/local-dev/hooks/`:

- **`pre_setup`**: Run during `just setup` (e.g., validate network configuration)
- **`pre_start`**: Run before starting service in `just dev` (e.g., check dependencies)

```python
def run_hook(addon: str, hook: str, if_missing_ok: bool = False) -> bool:
    """Run a specific hook for an add-on."""
    addon_dir = REPO_ROOT / addon
    hook_path = _resolve_hook(addon_dir, hook)  # Tries hook, hook.sh, hook.py

    if not hook_path or not hook_path.exists():
        return if_missing_ok

    result = subprocess.run([str(hook_path)], cwd=str(addon_dir), check=False)
    return result.returncode == 0
```

### 7. Port Management (`manage_ports.py`)

Scans all add-on ports and provides utilities to:
- List processes using add-on ports
- Kill processes on specific ports
- Clean up stale dev processes

## Integration Points

### Top-Level Justfile Integration

The root `Justfile` uses talos as its primary build tool:

```just
talos_bin := "talos/build/bin/talos"

# Ensure talos is built before using
talos-build:
    ./talos/build.sh

# Build Home Assistant add-ons
ha-addon addon="all": talos-build
    "{{talos_bin}}" addons run ha-addon {{addon}}

# Deploy add-ons
deploy addon="all": deploy-preflight talos-build
    "{{talos_bin}}" addons deploy {{addon}}

# Start local dev environment
dev:
    if [ ! -x "{{talos_bin}}" ]; then ./talos/build.sh; fi
    "{{talos_bin}}" dev

# Run tests
test addon="all":
    "{{talos_bin}}" addons run test {{addon}}
```

### Per-Add-on Justfile Pattern

Individual add-ons follow a consistent pattern:

```just
# grid-dashboard/Justfile
import "../talos/just/nvm.just"

setup:
    {{nvm_use}}
    cd ExpressServer && npm install

test:
    {{nvm_use}}
    cd ExpressServer && npm test

ha-addon:
    if [ ! -x "../talos/build/bin/talos" ]; then ../talos/build.sh; fi
    ../talos/build/bin/talos addon build grid-dashboard

deploy:
    if [ ! -x "../talos/build/bin/talos" ]; then ../talos/build.sh; fi
    ../talos/build/bin/talos addon deploy grid-dashboard
```

### Add-on Declaration (`addon.yaml`)

Add-ons declare all their requirements in a single YAML file:

```yaml
slug: grid_dashboard
name: Grid Dashboard
description: Dashboard UI with Sonos shortcuts
source_subdir: ExpressServer  # Source is in subdirectory
copy:  # Files to include in Docker image
  - src
  - package.json
  - package-lock.json
npm_build: false
python: false  # Node.js add-on
ports:
  "3000": 3000
run_env:  # Environment variables for both dev and production
  - env: PORT
    value: "3000"
  - env: SONOS_BASE_URL
    from_option: sonos_base_url
    default: "http://local-sonos-api:5006"  # Production URL
tests:  # Commands to run for testing
  - npm test
  - npm run check
```

Talos reads this file and:
1. **For builds**: Renders templates, copies files, creates tarball
2. **For dev**: Sets up env vars (with localhost URL substitution), starts service
3. **For deploy**: Builds, SCPs to Home Assistant, installs/rebuilds add-on

## Workflows

### Build Workflow

```
User runs: just ha-addon grid-dashboard
    ↓
Justfile calls: talos addons run ha-addon grid-dashboard
    ↓
addons_runner.py looks for grid-dashboard/Justfile recipe "ha-addon"
    ↓
Runs: cd grid-dashboard && just ha-addon
    ↓
grid-dashboard/Justfile calls: talos addon build grid-dashboard
    ↓
addon_builder.py:
  1. Discovers grid-dashboard/addon.yaml
  2. Reads .nvmrc and .python-version
  3. Builds template context
  4. Renders Dockerfile.j2, config.yaml.j2, run.sh.j2, etc.
  5. Copies source files per addon.yaml "copy" list
  6. Creates tarball in build/home-assistant-addon/
    ↓
Output: build/home-assistant-addon/grid_dashboard.tar.gz
```

### Dev Workflow

```
User runs: just dev
    ↓
Justfile calls: talos dev
    ↓
dev.py (DevOrchestrator):
  1. Discover all addon.yaml files
  2. Parse configs and determine dependencies
  3. Topologically sort for startup order
  4. Check prerequisites (node_modules, etc.)
  5. Run pre_start hooks
  6. Start services with async subprocess management
  7. Multiplex logs with [service timestamp] format
  8. Display service URLs
  9. Wait for Ctrl+C, then gracefully shutdown
```

### Enhanced Deploy Workflow

```
User runs: just deploy grid-dashboard
    ↓
Justfile calls: talos addons deploy grid-dashboard
    ↓
Enhanced deployment system (cli.py addons_deploy):
  1. Prerequisites validation (SSH, disk space, HA health)
  2. Progress tracking with real-time updates
  3. Calls addon_builder.py deploy_addon() for each addon:
     - Builds tarball with verbose output
     - SCPs tarball to homeassistant.local:/root/
     - Executes enhanced remote deployment script:
       * Stop add-on if running (with state checking)
       * Extract tarball to /addons/
       * Reload add-on list with error handling
       * Rebuild or install add-on (graceful fallback)
       * Configure add-on options via Supervisor API
       * Start add-on with health verification
  4. Deployment summary with success/failure reporting
  5. Comprehensive error handling with troubleshooting steps
```

## Extension Points

### Adding a New Add-on

1. Create directory with `addon.yaml`:
```yaml
slug: my_addon
name: My Addon
description: Does something cool
python: true  # or false for Node.js
copy:
  - src
  - pyproject.toml
ports:
  "8080": 8080
run_env:
  - env: PORT
    value: "8080"
tests:
  - just test
```

2. Create `Justfile`:
```just
setup:
    uv sync  # or npm install

test:
    uv run pytest

ha-addon:
    ../talos/build/bin/talos addon build my-addon

deploy:
    ../talos/build/bin/talos addon deploy my-addon
```

3. Talos automatically:
   - Discovers the add-on
   - Generates appropriate Dockerfile (Python or Node base)
   - Includes in `just dev` orchestration
   - Supports `just deploy my-addon`

### Adding Custom Lifecycle Logic

Create hook script in `<addon>/local-dev/hooks/`:

```bash
#!/usr/bin/env bash
# my-addon/local-dev/hooks/pre_start.sh

# Check if external service is reachable
if ! curl -s http://external-api.com/health > /dev/null; then
    echo "External API is not reachable. Cannot start addon." >&2
    exit 1
fi

echo "Pre-start checks passed"
exit 0
```

Make it executable: `chmod +x my-addon/local-dev/hooks/pre_start.sh`

Talos will automatically run this before starting the service in `just dev`.

## Benefits of Talos Architecture

1. **Consistency**: Same versions in dev and production (via `.nvmrc`/`.python-version`)
2. **Simplicity**: Add-ons are just directories with `addon.yaml`
3. **Flexibility**: Symlink add-ons from other repos
4. **Transparency**: Generated Dockerfiles include version comments
5. **Robustness**: Isolated venv prevents tooling conflicts
6. **Developer Experience**: `just dev` provides unified development environment
7. **Maintainability**: Templates centralize Docker/config patterns
8. **Extensibility**: Hook system for custom logic without modifying talos

## Future Enhancements

- Add support for multi-arch Docker builds
- Implement caching for faster rebuilds
- Add dry-run mode for deploy
- Support alternative deployment targets (not just SSH)
- Add integration tests that build and deploy all add-ons
- Consider moving templates to add-on directories for per-add-on customization

## See Also

- [USAGE.md](./USAGE.md) - Complete command reference, common workflows, and troubleshooting
- [IMPROVEMENTS.md](./IMPROVEMENTS.md) - Recent improvements and recommendations
- [../../docs/addon-development/hooks-guide.md](../../docs/addon-development/hooks-guide.md) - Lifecycle hooks guide and examples
- [../../AGENTS.md](../../AGENTS.md) - Full repository development guide
