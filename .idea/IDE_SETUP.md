# JetBrains IDE Setup for Smarthome Monorepo

This repository is configured for optimal development with JetBrains IDEs.

## Recommended IDE

**IntelliJ IDEA Ultimate** is the recommended IDE for this monorepo as it supports both TypeScript/Node.js and Python projects in a single workspace.

Alternative options:
- **WebStorm** - For TypeScript/Node.js projects only
- **PyCharm Professional** - For Python projects only

## First-Time Setup

### 1. Open the Project

Open the repository root directory (`/Users/rtimmons/Projects/smarthome`) in your IDE.

### 2. Configure Node.js Interpreter

The project uses Node.js v20.18.2 (defined in `.nvmrc`).

**If using nvm:**
1. Run `nvm install` in the project root to install the correct version
2. In IDE: **Settings/Preferences → Languages & Frameworks → Node.js**
3. Set Node interpreter to the nvm-managed version: `~/.nvm/versions/node/v20.18.2/bin/node`
4. Click "Apply"

**Manual setup:**
1. Ensure Node.js v20.18.2 is installed on your system
2. In IDE: **Settings/Preferences → Languages & Frameworks → Node.js**
3. Set Node interpreter to your Node.js v20.18.2 installation path
4. Click "Apply"

### 3. Configure Python Interpreter

The project uses Python 3.12.12 (defined in `.python-version`).

**IMPORTANT: You must configure the Python interpreter BEFORE opening Python files.**

**Using the project virtualenv (recommended):**
1. First run `just setup` from the terminal to create `.venv/`
2. In IDE: **File → Project Structure** (or **Cmd+;** on Mac)
3. Under **Project Settings → Project**, set **SDK** to Python 3.12
   - If not available, click **New** → **Add Python SDK** → **Virtualenv Environment**
   - Select **Existing environment**
   - Browse to: `[PROJECT_ROOT]/.venv/bin/python`
   - Click **OK**
4. Under **Project Settings → Modules**, select the `smarthome` module
5. Under **Dependencies**, ensure the Module SDK is set to **Python 3.12**
6. Click **Apply** then **OK**

**Alternative: Using pyenv:**
1. Run `pyenv install 3.12.12` to ensure the version is available
2. In IDE: **File → Project Structure** (or **Cmd+;** on Mac)
3. Under **Project Settings → SDKs**, click **+** → **Add Python SDK**
4. Select **System Interpreter**
5. Browse to: `~/.pyenv/versions/3.12.12/bin/python`
6. Click **OK**
7. Set this as the project SDK in **Project Settings → Project**
8. Click **Apply** then **OK**

### 4. Install Dependencies

Run from the project root:
```bash
just setup
```

This will:
- Install all Node.js dependencies for all TypeScript projects
- Set up the Python virtual environment in `.venv/`
- Install all Python dependencies

### 5. Verify Setup

After setup, you should see:
- No TypeScript errors in `grid-dashboard`, `sonos-api`, `snapshot-service`, or `new-hass-configs`
- No Python import errors in `printer`
- All run configurations available in the Run/Debug dropdown

## Available Run Configurations

The following run configurations are pre-configured and ready to use:

### Main Development
- **just dev (All Services)** - Start all services locally with auto-reload
- **just setup** - Install all dependencies
- **just test (All Tests)** - Run tests for all projects

### Individual Services
- **Grid Dashboard (Dev)** - Run grid-dashboard in development mode
- **Grid Dashboard (Tests)** - Run grid-dashboard tests
- **Printer Service (Dev)** - Run printer service in development mode
- **Printer Service (Tests)** - Run printer service tests

### Deployment
- **Build All Addons** - Build all Home Assistant add-ons
- **Deploy All Addons** - Deploy all add-ons to Home Assistant
- **Home Assistant Config (Deploy)** - Deploy Home Assistant configuration

## Project Structure

This monorepo contains:

### TypeScript/Node.js Projects
- `grid-dashboard/ExpressServer/` - Main web dashboard (Express + TypeScript)
- `sonos-api/` - Sonos API wrapper
- `snapshot-service/` - Snapshot service
- `new-hass-configs/config-generator/` - Home Assistant config generator

### Python Projects
- `printer/` - Kitchen label printing service (Flask + Python)

## Code Style

The IDE is pre-configured with:
- **TypeScript/JavaScript**: 2-space indentation, single quotes, no semicolons
- **Python**: 4-space indentation, 100-character line limit, Ruff formatting
- **ESLint**: Auto-fix on save
- **Prettier**: Auto-format on save

## Integrated Tools

The following tools are integrated:
- **ESLint** - JavaScript/TypeScript linting
- **Prettier** - Code formatting
- **TypeScript** - Type checking and IntelliSense
- **Python Black** - Python code formatting (via Ruff)
- **Git** - Version control integration

## Common Tasks

### Running Tests
- Click the run configuration dropdown → Select a test configuration → Click Run
- Or use the terminal: `just test`

### Starting Development Servers
- Click the run configuration dropdown → Select "just dev (All Services)" → Click Run
- Or use the terminal: `just dev`

### Building Add-ons
- Click the run configuration dropdown → Select "Build All Addons" → Click Run
- Or use the terminal: `just ha-addon`

### Deploying to Home Assistant
- Click the run configuration dropdown → Select "Deploy All Addons" → Click Run
- Or use the terminal: `just deploy`

## Troubleshooting

### TypeScript Navigation Not Working
If you can't navigate to TypeScript symbol definitions (Cmd+Click doesn't work):
1. Ensure all dependencies are installed:
   ```bash
   cd grid-dashboard/ExpressServer && npm install
   cd sonos-api && npm install
   cd snapshot-service && npm install
   cd new-hass-configs/config-generator && npm install
   ```
2. Verify TypeScript service is configured:
   - **Settings → Languages & Frameworks → TypeScript**
   - Ensure "TypeScript Language Service" is enabled
   - TypeScript version should be detected automatically from `node_modules`
3. Restart the TypeScript service:
   - **View → Tool Windows → TypeScript → Restart TypeScript Service**
4. If still not working, invalidate caches:
   - **File → Invalidate Caches → Invalidate and Restart**

### TypeScript Errors or Red Squiggles
If you see TypeScript errors in valid code:
1. Ensure Node.js v20.18.2 is configured correctly (see step 2 above)
2. Check that `tsconfig.json` exists in each project directory
3. Ensure the TypeScript version matches across projects (run `npm install` in each)
4. Restart the TypeScript service (see above)

### Python Import Errors or "No module named..."
If you see Python import errors:
1. Ensure the virtualenv is set up: `just setup`
2. Verify the Python interpreter via **File → Project Structure**:
   - Under **Project**, SDK should be **Python 3.12**
   - Under **Modules → smarthome → Dependencies**, Module SDK should be **Python 3.12**
3. If the SDK shows as "Python 3.12 (smarthome)" but with a red X, remove it and re-add:
   - Go to **Settings → Project → Python Interpreter**
   - Click gear icon → **Show All**
   - Remove any broken interpreters (red X)
   - Click **+** → **Add Local Interpreter**
   - Select **Existing** → Browse to `.venv/bin/python`
4. Invalidate caches: **File → Invalidate Caches → Invalidate and Restart**

### "*.js files are supported by WebStorm" Message
This is just an informational message from IntelliJ IDEA Ultimate. You can safely ignore it or:
1. Dismiss the notification
2. Or suppress it: **File → Settings → Appearance & Behavior → Notifications**
3. Find "JavaScript and TypeScript" and set to "No popup"

### Run Configurations Not Showing
If run configurations don't appear:
1. Ensure you opened the **root directory** of the repository (`/Users/rtimmons/Projects/smarthome`)
2. Check that `.idea/runConfigurations/` exists and contains XML files
3. Restart the IDE
4. If still missing, right-click on any `.xml` file in `.idea/runConfigurations/` and select **Run**

### ESLint/Prettier Not Working
If auto-formatting isn't working:
1. Check **Settings → Languages & Frameworks → JavaScript → Code Quality Tools → ESLint**
2. Ensure "Run eslint --fix on save" is enabled
3. Check **Settings → Languages & Frameworks → JavaScript → Prettier**
4. Ensure "Run on save" is enabled

## Additional Configuration

### Exclude Patterns
The following directories are already excluded from indexing:
- `node_modules/` (all TypeScript projects)
- `.venv/` (Python virtualenv)
- `build/` (build output)
- `.pytest_cache/` (Python test cache)

### Version Control
Git integration is pre-configured with:
- Commit message validation
- Automatic change detection
- Integrated diff viewer

## Further Reading

- [CLAUDE.md](../CLAUDE.md) - Project overview and development guidelines
- [README.md](../README.md) - Project documentation
- Root [Justfile](../Justfile) - Available commands and recipes
