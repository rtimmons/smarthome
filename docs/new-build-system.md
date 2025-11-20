# Build System Migration Plan

**Status:** Planning
**Goal:** Reduce infrastructure code from ~2,200 lines to <100 lines by adopting monorepo tooling and native build systems
**Constraints:**
- No Docker required for local development
- No external service dependencies (GitHub Actions, container registries)
- Local SSH-based deployment preserved
- System must remain deployable at every step
- All tests must pass after each iteration

---

## Table of Contents

1. [Current State Analysis](#current-state-analysis)
2. [Target State](#target-state)
3. [Migration Strategy](#migration-strategy)
4. [Iteration Plan](#iteration-plan)
5. [Verification Procedures](#verification-procedures)
6. [Rollback Plan](#rollback-plan)

---

## Current State Analysis

### Infrastructure Code (2,203 lines)

| Component | Lines | Purpose |
|-----------|-------|---------|
| `tools/dev_orchestrator.py` | 594 | Local dev orchestration, dependency resolution, log multiplexing |
| `tools/addon_builder.py` | 381 | Build system, Jinja2 templating, tarball creation |
| `tools/manage_ports.py` | 156 | Port conflict detection and process management |
| `tools/addon_hooks.py` | 79 | Pre-flight hooks system |
| `tools/templates/*.j2` | ~400 | Jinja2 templates for Dockerfile, config.yaml, run.sh, etc. |
| `printer/scripts/*` | 473 | Duplicate build/deploy scripts |
| Per-addon Justfiles | ~120 | 4 nearly identical Justfiles |

### Build Flow

```
Developer → just dev
           ↓
  dev_orchestrator.py (594 lines)
           ↓
  ┌─────────────────────┐
  │ Discover addons     │
  │ Build dep graph     │
  │ Start in order      │
  │ Multiplex logs      │
  │ Watch for changes   │
  └─────────────────────┘

Developer → just ha-addon grid-dashboard → just deploy grid-dashboard
           ↓                                ↓
  addon_builder.py (381 lines)              SSH + rsync
           ↓
  ┌─────────────────────┐
  │ Load addon.yaml     │
  │ Render Jinja2       │
  │ Build tarball       │
  └─────────────────────┘
```

### Package Structure

**Node.js packages:**
- `grid-dashboard/ExpressServer/` - TypeScript 3.6.3, Express server
- `sonos-api/` - TypeScript 4.9.5, API proxy
- `node-sonos-http-api/node-sonos-http-api/` - Upstream git clone

**Python packages:**
- `printer/` - Python 3.12, uses uv
- `new-hass-configs/config-generator/` - TypeScript config generator
- `new-hass-configs/MetaHassConfig/` - **LEGACY** (to be removed)

### Current Strengths

✅ **Good patterns to preserve:**
- Add-on auto-discovery via `*/addon.yaml` glob pattern
- Single source of truth for versions (`.nvmrc`, `.python-version`)
- Declarative `addon.yaml` specifications
- Just-based command interface

---

## Target State

### Infrastructure Code (~80 lines)

| Component | Lines | Purpose |
|-----------|-------|---------|
| Root `package.json` | ~20 | npm workspace config |
| Root `pyproject.toml` | ~10 | uv workspace config |
| `nx.json` | ~30 | Task orchestration config |
| `tools/addon.py` | ~50 | Minimal addon discovery + build invocation |
| Per-addon `build.sh` | ~30 each | Declarative build scripts |
| Root `Justfile` | ~40 | Consolidated task runner |

### Build Flow

```
Developer → just dev
           ↓
  nx run-many --target=dev --all --parallel
           ↓
  ┌─────────────────────┐
  │ Nx reads deps       │
  │ Starts in order     │
  │ Native log output   │
  │ Built-in watching   │
  └─────────────────────┘

Developer → just ha-addon grid-dashboard → just deploy grid-dashboard
           ↓                                ↓
  addon.py (50 lines)                       Fabric/SSH
           ↓
  ┌─────────────────────┐
  │ Discover addons     │
  │ Run build.sh        │
  │ Create tarball      │
  └─────────────────────┘
```

### Technology Stack

| Function | Tool | Rationale |
|----------|------|-----------|
| Node.js dependency management | npm workspaces | Built-in, zero config, dedupes dependencies |
| Python dependency management | uv workspaces | Already using uv, workspace support is native |
| Task orchestration | Nx | Best polyglot support, local caching, dep graph |
| Task runner (user interface) | Just | Keep existing interface, users already know it |
| Build scripts | Shell scripts | Simpler than Python + Jinja2, easier to debug |
| Deployment | Fabric (Python) | Standard SSH automation library |
| Patch management | Fork or patch-package | Git-native workflows |

---

## Migration Strategy

### Principles

1. **Backward Compatibility First** - Old and new systems coexist during migration
2. **Incremental Validation** - Each iteration must pass all tests and deploy successfully
3. **Feature Parity** - Don't lose functionality during migration
4. **Session Boundaries** - Each iteration can be paused and resumed
5. **Quick Wins** - Start with high-value, low-risk changes

### Risk Mitigation

- **Branch Strategy**: Work in feature branch `refactor/new-build-system`
- **Rollback**: Keep old infrastructure until migration is 100% complete
- **Testing**: Verify build + deploy + test for every addon after each iteration
- **Documentation**: Update CLAUDE.md as we go

---

## Iteration Plan

### 📋 Pre-Migration Checklist

**Before starting, verify:**
- [ ] All tests currently pass: `just test`
- [ ] All add-ons build successfully: `just ha-addon all`
- [ ] Current deployment works: `just deploy grid-dashboard` (test with one addon)
- [ ] Create feature branch: `git checkout -b refactor/new-build-system`
- [ ] Backup current state: `git tag pre-migration-backup`

---

### Iteration 1: Workspace Foundation (Non-Breaking)

**Goal:** Set up npm and uv workspaces without changing existing build system

**Time Estimate:** 30-60 minutes
**Can Deploy After:** ✅ Yes

#### Tasks

1. **Create root `package.json` with workspace config**
   ```json
   {
     "name": "smarthome-monorepo",
     "private": true,
     "workspaces": [
       "grid-dashboard/ExpressServer",
       "sonos-api",
       "node-sonos-http-api/node-sonos-http-api"
     ],
     "scripts": {
       "install:all": "npm install"
     }
   }
   ```

2. **Test workspace installation**
   ```bash
   # Remove existing node_modules
   rm -rf grid-dashboard/ExpressServer/node_modules
   rm -rf sonos-api/node_modules

   # Install via workspace
   npm install

   # Verify packages are linked
   ls -la node_modules/
   ```

3. **Create root `pyproject.toml` for uv workspace**
   ```toml
   [tool.uv.workspace]
   members = ["printer"]
   ```

4. **Test uv workspace**
   ```bash
   cd printer
   rm -rf .venv
   cd ..
   uv sync  # Should create workspace-level venv
   ```

5. **Update `just setup` to use workspaces**
   ```just
   setup:
       npm install  # workspace install
       cd printer && uv sync
   ```

#### Verification

```bash
# Clean install
just setup

# Verify workspace dependencies installed
test -d node_modules && echo "✅ npm workspace OK"
test -d printer/.venv && echo "✅ uv workspace OK"

# Verify existing build still works
just ha-addon grid-dashboard
test -f build/home-assistant-addon/grid-dashboard.tar.gz && echo "✅ Build OK"

# Verify tests still pass
just test grid-dashboard
```

#### Success Criteria

- ✅ `just setup` completes successfully
- ✅ `just test all` passes
- ✅ `just ha-addon grid-dashboard` builds successfully
- ✅ Deployment works: `just deploy grid-dashboard`
- ✅ No functionality lost

#### Commit Point

```bash
git add package.json pyproject.toml Justfile
git commit -m "Add npm and uv workspace configuration

- Add root package.json with workspace definitions
- Add root pyproject.toml for uv workspace
- Update just setup to use workspaces
- All tests passing, builds working"
```

---

### Iteration 2: Install and Configure Nx (Non-Breaking)

**Goal:** Add Nx for task orchestration, but don't migrate tasks yet

**Time Estimate:** 30-45 minutes
**Can Deploy After:** ✅ Yes

#### Tasks

1. **Install Nx**
   ```bash
   npm add -D nx @nx/js
   ```

2. **Initialize Nx**
   ```bash
   npx nx init
   ```

3. **Create `nx.json` with basic config**
   ```json
   {
     "$schema": "./node_modules/nx/schemas/nx-schema.json",
     "targetDefaults": {
       "dev": {
         "dependsOn": ["^dev"],
         "cache": false
       },
       "build": {
         "dependsOn": ["^build"],
         "outputs": ["{projectRoot}/dist"],
         "cache": true
       },
       "test": {
         "cache": true
       }
     },
     "defaultBase": "master"
   }
   ```

4. **Create `project.json` for grid-dashboard**
   ```bash
   mkdir -p grid-dashboard/ExpressServer/.nx
   cat > grid-dashboard/ExpressServer/project.json <<EOF
   {
     "name": "grid-dashboard",
     "$schema": "../../node_modules/nx/schemas/project-schema.json",
     "targets": {
       "dev": {
         "executor": "nx:run-commands",
         "options": {
           "command": "npm run dev",
           "cwd": "grid-dashboard/ExpressServer"
         }
       },
       "test": {
         "executor": "nx:run-commands",
         "options": {
           "command": "npm test",
           "cwd": "grid-dashboard/ExpressServer"
         }
       }
     },
     "implicitDependencies": ["sonos-api"]
   }
   EOF
   ```

5. **Create `project.json` for sonos-api**
   ```bash
   cat > sonos-api/project.json <<EOF
   {
     "name": "sonos-api",
     "$schema": "../node_modules/nx/schemas/project-schema.json",
     "targets": {
       "dev": {
         "executor": "nx:run-commands",
         "options": {
           "command": "npm run dev",
           "cwd": "sonos-api"
         }
       }
     }
   }
   EOF
   ```

6. **Test Nx without changing Justfile**
   ```bash
   # Test single task
   npx nx dev sonos-api

   # Test all tasks
   npx nx run-many --target=test --all
   ```

#### Verification

```bash
# Verify Nx can run tasks
npx nx test grid-dashboard && echo "✅ Nx task execution OK"

# Verify Nx detects dependencies
npx nx graph  # Should show grid-dashboard → sonos-api

# Verify old system still works
just dev  # Should use old dev_orchestrator.py
just test all  # Should use old test system

# Verify builds and deploys still work
just ha-addon grid-dashboard
just deploy grid-dashboard
```

#### Success Criteria

- ✅ Nx installed and configured
- ✅ `npx nx graph` shows dependency graph
- ✅ `npx nx test grid-dashboard` works
- ✅ Old `just` commands still work unchanged
- ✅ All tests passing
- ✅ Build and deploy still functional

#### Commit Point

```bash
git add nx.json package.json grid-dashboard/ExpressServer/project.json sonos-api/project.json
git commit -m "Add Nx task orchestration (non-breaking)

- Install nx and @nx/js
- Configure task defaults in nx.json
- Add project.json for grid-dashboard and sonos-api
- Nx runs in parallel with old system
- All tests passing, no functionality changed"
```

---

### Iteration 3: Migrate `just dev` to Nx

**Goal:** Replace `dev_orchestrator.py` with Nx for local development

**Time Estimate:** 45-60 minutes
**Can Deploy After:** ✅ Yes (build/deploy unchanged)

#### Tasks

1. **Add project.json for all remaining add-ons**
   - `printer/project.json`
   - `node-sonos-http-api/node-sonos-http-api/project.json`

2. **Update root Justfile to use Nx for dev**
   ```just
   # Old (keep temporarily):
   dev-old:
       .venv/bin/python tools/dev_orchestrator.py

   # New:
   dev:
       npx nx run-many --target=dev --all --parallel=4
   ```

3. **Add environment variable handling**
   - Review `addon.yaml` `run_env` specifications
   - Add `.env` files or update `project.json` with env vars

4. **Test dependency ordering**
   ```bash
   # Start only grid-dashboard (should auto-start sonos-api)
   npx nx dev grid-dashboard
   ```

5. **Compare log output**
   - Old: `just dev-old` (using dev_orchestrator.py)
   - New: `just dev` (using Nx)
   - Ensure all services start correctly

#### Verification

```bash
# Test new dev command
just dev &
DEV_PID=$!
sleep 10

# Verify all services running
curl http://localhost:3000 && echo "✅ grid-dashboard running"
curl http://localhost:5006 && echo "✅ sonos-api running"
curl http://localhost:5005 && echo "✅ node-sonos-http-api running"
curl http://localhost:8099 && echo "✅ printer running"

kill $DEV_PID

# Verify builds and deploys still work
just ha-addon grid-dashboard
just deploy grid-dashboard

# Verify tests still pass
just test all
```

#### Success Criteria

- ✅ `just dev` starts all services using Nx
- ✅ Dependencies start in correct order
- ✅ All services accessible on expected ports
- ✅ Logs are readable (even if format changed)
- ✅ Ctrl+C gracefully stops all services
- ✅ Build and deploy still work
- ✅ All tests pass

#### Commit Point

```bash
# If successful, can remove old orchestrator
mv tools/dev_orchestrator.py tools/dev_orchestrator.py.bak
mv tools/manage_ports.py tools/manage_ports.py.bak

git add Justfile */project.json
git commit -m "Migrate 'just dev' to use Nx

- Replace dev_orchestrator.py (594 lines) with Nx
- Add project.json for all add-ons
- Update just dev to use nx run-many
- Backup old orchestrator files
- All services start correctly, tests passing"
```

---

### Iteration 4: Simplify Build System - Part 1 (Single Add-on)

**Goal:** Replace Jinja2 templating with shell scripts for ONE add-on (grid-dashboard)

**Time Estimate:** 1-2 hours
**Can Deploy After:** ✅ Yes

#### Tasks

1. **Create `grid-dashboard/build.sh`**
   ```bash
   #!/usr/bin/env bash
   set -euo pipefail

   # Read versions
   NODE_VERSION=$(cat ../.nvmrc | sed 's/^v//')

   # Read addon config
   ADDON_NAME="grid-dashboard"
   VERSION=$(jq -r '.version' ExpressServer/package.json)

   # Create build directory
   BUILD_DIR="../build/home-assistant-addon/${ADDON_NAME}"
   rm -rf "$BUILD_DIR"
   mkdir -p "$BUILD_DIR"

   # Generate Dockerfile (instead of Jinja2 template)
   cat > "$BUILD_DIR/Dockerfile" <<EOF
   # Auto-generated from grid-dashboard/build.sh
   # Node.js version from .nvmrc: ${NODE_VERSION}
   ARG BUILD_FROM="node:${NODE_VERSION}-alpine"
   FROM \${BUILD_FROM}

   WORKDIR /app
   COPY ExpressServer/package*.json ./
   RUN npm install --production
   COPY ExpressServer/ ./

   CMD ["npm", "start"]
   EOF

   # Generate config.yaml
   # ... (similar pattern)

   # Copy source files
   cp -r ExpressServer "$BUILD_DIR/"

   # Create tarball
   cd ../build/home-assistant-addon
   tar -czf "${ADDON_NAME}.tar.gz" "${ADDON_NAME}/"
   ```

2. **Make build script executable**
   ```bash
   chmod +x grid-dashboard/build.sh
   ```

3. **Create minimal `tools/addon.py`**
   ```python
   #!/usr/bin/env python3
   """Minimal addon helper - replaces 381-line addon_builder.py"""
   import subprocess
   from pathlib import Path
   import yaml

   REPO_ROOT = Path(__file__).resolve().parents[1]

   def discover_addons():
       """Find all */addon.yaml files."""
       addons = {}
       for addon_yaml in REPO_ROOT.glob("*/addon.yaml"):
           addon_key = addon_yaml.parent.name
           data = yaml.safe_load(addon_yaml.read_text())
           addons[addon_key] = data
       return addons

   def build_addon(name):
       """Run addon's build.sh script."""
       addon_dir = REPO_ROOT / name
       build_script = addon_dir / "build.sh"

       if build_script.exists():
           subprocess.run(["bash", str(build_script)], cwd=addon_dir, check=True)
       else:
           # Fall back to old system
           from tools import addon_builder
           addon_builder.build_addon(name)

   if __name__ == "__main__":
       import sys
       if sys.argv[1] == "build":
           build_addon(sys.argv[2])
   ```

4. **Test new build script**
   ```bash
   cd grid-dashboard
   ./build.sh

   # Verify tarball created
   ls -lh ../build/home-assistant-addon/grid-dashboard.tar.gz

   # Verify contents
   tar -tzf ../build/home-assistant-addon/grid-dashboard.tar.gz | head -20
   ```

5. **Update Justfile to support both systems**
   ```just
   ha-addon addon="all":
       python tools/addon.py build {{addon}}
   ```

6. **Deploy and test**
   ```bash
   just deploy grid-dashboard
   # Verify addon works in Home Assistant
   ```

#### Verification

```bash
# Build using new script
cd grid-dashboard && ./build.sh && cd ..

# Build using just (should call new script)
just ha-addon grid-dashboard

# Compare tarballs (should be similar size)
ls -lh build/home-assistant-addon/grid-dashboard.tar.gz

# Deploy and test
just deploy grid-dashboard

# Verify addon starts and works
# (Manual verification in Home Assistant UI)

# Run tests
just test grid-dashboard
```

#### Success Criteria

- ✅ `grid-dashboard/build.sh` generates valid tarball
- ✅ Tarball deploys successfully
- ✅ Add-on runs correctly in Home Assistant
- ✅ Tests pass
- ✅ Old build system still works for other add-ons
- ✅ No Jinja2 templates used for grid-dashboard

#### Commit Point

```bash
git add grid-dashboard/build.sh tools/addon.py Justfile
git commit -m "Replace Jinja2 with shell script for grid-dashboard

- Create grid-dashboard/build.sh (replaces template)
- Create minimal tools/addon.py (~50 lines)
- Hybrid system: new build.sh coexists with old addon_builder.py
- Deployed and tested successfully
- Tests passing"
```

---

### Iteration 5: Simplify Build System - Part 2 (All Add-ons)

**Goal:** Migrate remaining add-ons to shell-based builds

**Time Estimate:** 2-3 hours
**Can Deploy After:** ✅ Yes

#### Tasks

1. **Create `sonos-api/build.sh`** (similar pattern to grid-dashboard)
2. **Create `printer/build.sh`** (Python-based)
3. **Create `node-sonos-http-api/build.sh`** (handle git clone + patches)
4. **Test each build script individually**
5. **Remove fallback to old system in `tools/addon.py`**

#### Verification

```bash
# Build all add-ons
just ha-addon all

# Verify all tarballs created
ls -lh build/home-assistant-addon/*.tar.gz

# Deploy one addon from each type
just deploy sonos-api  # Node.js
just deploy printer    # Python

# Run all tests
just test all
```

#### Success Criteria

- ✅ All add-ons build with shell scripts
- ✅ All tarballs deploy successfully
- ✅ All add-ons run correctly in Home Assistant
- ✅ All tests pass
- ✅ No Jinja2 templates used

#### Commit Point

```bash
# Remove old system
rm -rf tools/templates/
rm tools/addon_builder.py

git add */build.sh tools/
git rm -r tools/templates/ tools/addon_builder.py
git commit -m "Complete migration to shell-based builds

- Add build.sh for all add-ons
- Remove tools/templates/ (7 Jinja2 files, ~400 lines)
- Remove tools/addon_builder.py (381 lines)
- All add-ons build and deploy successfully
- All tests passing

Code reduction: -781 lines"
```

---

### Iteration 6: Consolidate Justfiles

**Goal:** Use Just includes to eliminate duplication

**Time Estimate:** 30-45 minutes
**Can Deploy After:** ✅ Yes

#### Tasks

1. **Create `tools/addon.just`**
   ```just
   # Shared addon recipes - imported by other Justfiles

   [private]
   _build addon:
       python tools/addon.py build {{addon}}

   [private]
   _deploy addon:
       python tools/addon.py deploy {{addon}}

   [private]
   _test addon:
       npx nx test {{addon}}
   ```

2. **Simplify root `Justfile`**
   ```just
   import 'tools/addon.just'

   setup:
       npm install
       cd printer && uv sync

   dev:
       npx nx run-many --target=dev --all --parallel=4

   test addon="all":
       if [ "{{addon}}" = "all" ]; then \
           npx nx run-many --target=test --all; \
       else \
           npx nx test {{addon}}; \
       fi

   build addon="all": (_build addon)
   deploy addon="all": (_deploy addon)

   # Shortcuts for common operations
   build-grid: (build "grid-dashboard")
   deploy-grid: (deploy "grid-dashboard")
   ```

3. **Simplify per-addon Justfiles (or remove)**
   ```just
   # grid-dashboard/Justfile (optional)
   import '../tools/addon.just'

   build: (_build "grid-dashboard")
   deploy: (_deploy "grid-dashboard")
   ```

4. **Test all commands**
   ```bash
   just setup
   just test all
   just build grid-dashboard
   just deploy grid-dashboard

   # Test from addon directory
   cd grid-dashboard
   just build
   just deploy
   ```

#### Verification

```bash
# Test root commands
just --list
just test all
just build all
just deploy grid-dashboard

# Test addon commands
cd grid-dashboard && just --list && cd ..
cd sonos-api && just --list && cd ..

# Verify all functionality preserved
just ha-addon all
```

#### Success Criteria

- ✅ All `just` commands work as before
- ✅ No duplication in Justfiles
- ✅ Per-addon Justfiles simplified or removed
- ✅ All tests pass
- ✅ Build and deploy work

#### Commit Point

```bash
git add Justfile tools/addon.just */Justfile
git commit -m "Consolidate Justfiles using imports

- Create tools/addon.just with shared recipes
- Simplify root Justfile
- Simplify per-addon Justfiles
- Eliminate ~90 lines of duplication
- All commands work as before"
```

---

### Iteration 7: Final Cleanup

**Goal:** Remove legacy code and update documentation

**Time Estimate:** 30-45 minutes
**Can Deploy After:** ✅ Yes

#### Tasks

1. **Remove legacy Python config generator**
   ```bash
   rm -rf new-hass-configs/MetaHassConfig/
   ```

2. **Remove duplicate printer scripts**
   ```bash
   rm -rf printer/scripts/
   ```

3. **Remove backed-up orchestrator files**
   ```bash
   rm tools/dev_orchestrator.py.bak
   rm tools/manage_ports.py.bak
   rm tools/addon_hooks.py
   ```

4. **Update `CLAUDE.md`**
   - Document new workspace structure
   - Update build system section
   - Document Nx usage

5. **Update `docs/dev-setup.md`**
   - Reflect new setup process
   - Update troubleshooting section

6. **Create `docs/architecture.md`**
   - Document new build system
   - Explain Nx task graph
   - Show workspace structure

#### Verification

```bash
# Clean slate test
rm -rf node_modules printer/.venv
just setup

# Full workflow test
just dev &
sleep 10
curl http://localhost:3000
pkill -f "nx run-many"

just test all
just ha-addon all
just deploy grid-dashboard
```

#### Success Criteria

- ✅ No legacy code remains
- ✅ Documentation updated
- ✅ Clean setup works from scratch
- ✅ All tests pass
- ✅ Build and deploy work

#### Commit Point

```bash
git add docs/ CLAUDE.md
git rm -r new-hass-configs/MetaHassConfig/ printer/scripts/ tools/dev_orchestrator.py.bak tools/manage_ports.py.bak tools/addon_hooks.py
git commit -m "Final cleanup and documentation update

- Remove legacy MetaHassConfig (~300 lines)
- Remove duplicate printer scripts (473 lines)
- Remove old orchestrator backups (750 lines)
- Update CLAUDE.md with new build system
- Update docs/dev-setup.md
- Create docs/architecture.md

Total code reduction: ~2,100 lines"
```

---

### Iteration 8: Merge to Main

**Goal:** Integrate changes into main branch

**Time Estimate:** 15-30 minutes
**Can Deploy After:** ✅ Yes

#### Tasks

1. **Final verification on feature branch**
   ```bash
   git checkout refactor/new-build-system

   # Clean test
   rm -rf node_modules printer/.venv build/
   just setup
   just test all
   just ha-addon all
   ```

2. **Create PR or merge directly**
   ```bash
   git checkout master
   git merge refactor/new-build-system
   ```

3. **Test on main**
   ```bash
   just setup
   just test all
   just ha-addon all
   just deploy all
   ```

4. **Tag release**
   ```bash
   git tag v2.0.0-simplified-build
   git push origin master --tags
   ```

#### Success Criteria

- ✅ All changes merged to main
- ✅ Full test suite passes on main
- ✅ All add-ons build and deploy from main
- ✅ Tagged for easy rollback if needed

---

## Verification Procedures

### After Each Iteration

Run this checklist after completing any iteration:

```bash
#!/usr/bin/env bash
# save as tools/verify_migration.sh

set -e

echo "🔍 Running migration verification..."

echo "✅ 1. Setup works"
just setup

echo "✅ 2. All tests pass"
just test all

echo "✅ 3. All add-ons build"
just ha-addon all

echo "✅ 4. Check tarballs exist"
ls -lh build/home-assistant-addon/*.tar.gz

echo "✅ 5. Dev server starts"
timeout 30s just dev || true

echo "✅ 6. Test one deployment"
just deploy grid-dashboard

echo ""
echo "✅ All verification checks passed!"
echo "Safe to commit this iteration."
```

### Deployment Verification

After deploying any add-on:

1. Check Home Assistant UI - add-on appears and starts
2. Check add-on logs - no errors
3. Test add-on functionality - UI loads, API responds
4. Check dependent add-ons still work

---

## Rollback Plan

### If an iteration fails:

```bash
# Discard changes
git reset --hard HEAD

# Or rollback to previous commit
git reset --hard HEAD~1

# Or rollback to tag
git reset --hard pre-migration-backup
```

### If issues discovered after merge:

```bash
# Revert to pre-migration state
git revert <commit-hash>

# Or reset to tag
git reset --hard pre-migration-backup
git push origin master --force  # Use with caution
```

---

## Session Boundaries

You can safely stop and resume at any commit point. Before resuming:

1. Review the last completed iteration
2. Run verification procedure
3. Continue with next iteration

---

## Metrics

Track progress after each iteration:

| Metric | Before | After | Target |
|--------|--------|-------|--------|
| Infrastructure code | 2,203 lines | ??? | <100 lines |
| Build time (all) | ??? | ??? | Faster |
| Setup time | ??? | ??? | <2 min |
| Number of files in tools/ | 8+ | ??? | 2-3 |

---

## Questions to Answer During Migration

- [ ] What environment variables does each add-on need?
- [ ] Are there any hidden dependencies between add-ons?
- [ ] What's the actual startup order required?
- [ ] Can we run tests in parallel safely?
- [ ] Do any add-ons share code that should be extracted?

---

## Future Enhancements (Post-Migration)

Once migration is complete, consider:

1. **Add pre-commit hooks** - Automated linting and formatting
2. **Extract shared code** - Create shared libraries for common code
3. **Add CI/CD** - Local CI/CD using tools like GitLab CI (self-hosted)
4. **Improve test coverage** - Add integration tests
5. **Add documentation generation** - Auto-generate docs from code
6. **Consider Nix** - For ultimate reproducibility (advanced)

---

## Notes and Learnings

Use this section to track issues, decisions, and learnings during migration:

### Iteration 1 Notes
- (Add notes here during execution)

### Iteration 2 Notes
- (Add notes here during execution)

(etc.)
