# SmartHome Improvements Roadmap

This document consolidates all improvement plans, todos, and recommendations into a single comprehensive roadmap. It merges content from previously scattered plans across multiple documents.

**Last Updated**: 2026-08-11
**Status**: Active roadmap - replaces all other TODO/improvement documents

## Overview

This roadmap prioritizes improvements across four main areas:
1. **Security & Compatibility** - Critical updates for production readiness
2. **Home Assistant Standards** - Alignment with official HA best practices
3. **Development Experience** - Modernization and tooling improvements
4. **Architecture & Performance** - Long-term technical improvements

## 🔴 Critical Security & Compatibility (Immediate Priority)

### 1. Complete Node.js Security Updates

**Status**: ✅ **COMPLETED** - Node.js upgraded to v24.18.0 LTS

**Completed Items**:
- ✅ Update maintained services and the root runtime to Node.js v24.18.0 LTS
- ✅ Keep the upstream `node-sonos-http-api` app on its declared Node 22 compatibility line
- ✅ Test all Node.js dependencies with new runtime
- ✅ Update Ansible deployment scripts for new Node version

### 2. Replace Deprecated npm Packages

**Status**: ✅ **COMPLETED** / ⚠️ **UPSTREAM SONOS REPLACEMENT REMAINS LONG-TERM DEBT**

The dashboard and local Sonos proxy now use Node's built-in `fetch`; deprecated
`request`, `request-promise`, and `body-parser` dependencies were removed. The
vendored browser Underscore was updated to 1.13.8. Maintained npm projects audit
clean. The cloned third-party `node-sonos-http-api` source is now pinned to a
reviewed commit and built with a repository-owned, production-only dependency
graph. Its abandoned request clients were replaced while preserving Pandora,
Spotify search, AWS Polly, and ElevenLabs behavior; the resulting image audits
at zero known production vulnerabilities. Replacing that upstream service is
still worthwhile because it remains largely dormant legacy code.

Production dependency resolution is now reproducible: Python add-on builds
export the frozen `uv.lock` graph to hash-locked application and build
requirements, disable PEP 517 build isolation, and the
third-party Sonos build pins its upstream commit and installs its checked-in npm
lockfile with `npm ci`. Maintained Node setup paths also use `npm ci` rather
than rewriting lockfiles, and Talos installs itself from its own `uv.lock`.
Dependabot version updates cover every maintained npm
and uv manifest plus Dockerfiles and Git submodules.

**Tasks**:
- [x] Replace deprecated request clients in maintained services with native `fetch`
- [x] Update the shipped browser Underscore build
- [x] Update maintained service dependencies and lockfiles
- [x] Audit maintained production dependency trees
- [x] Install Python production dependencies from the hash-locked `uv.lock` graph
- [x] Pin cloned upstream source and use a reviewed npm lockfile during local and container builds
- [x] Replace the Sonos upstream production graph and verify the built image audits clean
- [x] Route the legacy printer build script through the locked Talos build pipeline
- [x] Lock the Talos build/test environment and remove self-updating pip setup paths
- [x] Pin runtime container images to patch releases and verify the nvm tag's commit
- [x] Configure scheduled npm, uv, Docker, and Git submodule version updates
- [ ] Replace or upstream-modernize `node-sonos-http-api`

### 3. Python Environment Standardization

**Status**: ✅ **COMPLETED** - Python standardized to 3.14.6

**Completed Items**:
- ✅ Standardize on Python 3.14.6 across all components
- ✅ Update .python-version file
- ✅ Update PyYAML from 5.3 to 6.x

### 4. Generate Official App Configuration Artifacts

**Status**: ✅ **COMPLETED**

Talos intentionally keeps repository-specific `addon.yaml` source manifests and
generates Supervisor-compatible `config.yaml`, `Dockerfile`, `run.sh`, and
translation artifacts. Generated configs now target supported 64-bit
architectures and include TCP watchdogs for network services.

## 🟡 Home Assistant Standards Alignment (High Priority)

### 5. Implement Standard Add-on File Structure

**Issue**: Current add-ons don't follow the standard Home Assistant add-on directory structure.

**Official Standard**: [Add-on Configuration](../reference-repos/developers.home-assistant/docs/add-ons/configuration.md#add-on-script)

**Required Files**:
- `config.yaml` (not `addon.yaml`)
- `Dockerfile` (currently generated)
- `README.md` (add-on specific documentation)
- `DOCS.md` (user-facing documentation)
- `CHANGELOG.md` (version history)
- `run.sh` or equivalent entry script

**Current Code Issues**:
- Missing `DOCS.md` files for user documentation
- Missing `CHANGELOG.md` files
- Custom build system instead of standard Dockerfile

### 6. Use Explicit BuildKit-Compatible Images and Metadata

**Status**: ✅ **COMPLETED**

Supervisor 2026.04 removed the legacy automatic `BUILD_FROM` fallback. Generated
Dockerfiles now use explicit `FROM` images and emit `io.hass.version`,
`io.hass.type=app`, and `io.hass.arch` labels from BuildKit arguments.

### 7. Home Assistant Integration Modernization

**Status**: 🟡 **ACTIVE**

The live host was observed on Home Assistant 2026.6.3 with 2026.7.2 available
during this review; no live update was installed. Generated and manual
automations now use the current plural `triggers`, `conditions`, and `actions`
shape and `action` service calls.

**Tasks**:
- [x] Align generated automation and script YAML with current syntax
- [x] Align app build metadata with the current Supervisor builder
- [ ] Evaluate migration from custom generator to native HA config
- [ ] Schedule and perform the live Home Assistant 2026.7.2 update separately
- [ ] Consider MQTT for device communication

### 8. Implement Security Best Practices

**Issue**: Missing security configurations and AppArmor profiles.

**Official Standard**: [Add-on Security](../reference-repos/developers.home-assistant/docs/add-ons/security.md)
- Add AppArmor profiles (`apparmor.txt`)
- Use minimal privileges
- Implement proper secrets management

**Current Code Issues**:
- No AppArmor profiles
- `printer/addon.yaml` uses `usb: true` without security considerations

**Tasks**:
- [ ] Create AppArmor profiles for all add-ons
- [ ] Review and minimize privileges for each add-on
- [ ] Implement proper secrets management
- [ ] Security audit of all add-on configurations

## 🟢 Development Experience & Modernization (Medium Priority)

### 9. Adopt Official Testing Approach

**Issue**: Custom local development environment instead of recommended devcontainer.

**Official Standard**: [Add-on Testing](../reference-repos/developers.home-assistant/docs/add-ons/testing.md)
- Use official devcontainer for development
- Test with full Home Assistant + Supervisor environment
- Use official builder for container builds

**Current Code**: Custom `just dev` orchestration in `docs/development/local-development.md`

**Recommendation**: 
- Keep custom local dev for fast iteration
- Add official devcontainer setup for integration testing
- Document both approaches clearly

### 10. TypeScript & Build System Modernization

**Status**: ✅ **COMPLETED FOR MAINTAINED SERVICES**

- [x] Update maintained projects to TypeScript 5.9
- [x] Replace ts-node development paths with tsx
- [x] Migrate Jest/Mocha suites to Vitest where appropriate
- [x] Adopt ESLint flat configuration and current Prettier
- [x] Enable strict TypeScript in the dashboard

### 11. Testing Infrastructure

**Issue**: No comprehensive testing setup.

**Tasks**:
- [x] Set up Vitest for maintained TypeScript services and the config generator
- [ ] Add integration tests with hardware mocks
- [ ] Configure GitHub Actions CI/CD pipeline
- [ ] Add end-to-end tests for critical paths
- [ ] Implement code coverage reporting

### 12. Hardware Abstraction Layer

**Issue**: Direct hardware dependencies prevent local development and testing.

**Tasks**:
- [ ] Create hardware abstraction service for i2c-bus
- [ ] Implement mock drivers for local development
- [ ] Add interface for blind controllers
- [ ] Enable testing without physical hardware
- [ ] Document hardware interface contracts

### 13. Implement Standard Add-on Communication

**Issue**: Custom networking and service discovery instead of standard Supervisor APIs.

**Official Standard**: [Add-on Communication](../reference-repos/developers.home-assistant/docs/add-ons/communication.md)
- Use Supervisor API for service discovery
- Use standard add-on naming: `{REPO}_{SLUG}` → `local-{slug}`
- Use `supervisor` hostname for API calls

**Current Code Issues**:
- `grid-dashboard/addon.yaml` hardcodes `sonos_base_url: "http://local-sonos-api:5006"`
- Custom service naming in local development

**Recommendation**: Use standard Supervisor service discovery.

### 14. API Modernization

**Status**: 🟡 **CORE RUNTIME COMPLETED**

**Tasks**:
- [x] Update the dashboard and Sonos proxy to Express 5.2
- [ ] Add OpenAPI/Swagger documentation
- [ ] Consider GraphQL or tRPC for type-safe API
- [ ] Implement proper error handling middleware
- [ ] Add API versioning strategy

## 🔵 Architecture & Infrastructure (Lower Priority)

### 15. Containerization & Deployment

**Issue**: Current deployment system could be modernized.

**Tasks**:
- [ ] Investigate deployment via ProxMox https://www.proxmox.com/en/
- [ ] Create Dockerfile for ExpressServer
- [ ] Set up docker-compose for local development
- [ ] Add Docker build to deployment process
- [ ] Document container-based deployment

### 16. Follow Official Publishing Guidelines

**Issue**: Custom deployment system instead of standard container registry publishing.

**Official Standard**: [Add-on Publishing](../reference-repos/developers.home-assistant/docs/add-ons/publishing.md)
- Publish to container registry (GitHub Container Registry recommended)
- Use `image` field in config.yaml
- Support multiple architectures

**Current Code**: Custom talos deployment system

**Recommendation**: Implement standard publishing workflow alongside custom system.

### 17. Monorepo Structure

**Issue**: Current structure could benefit from monorepo tooling.

**Tasks**:
- [ ] Evaluate monorepo tools (Nx, Turborepo, pnpm workspaces)
- [ ] Restructure project as monorepo
- [ ] Share TypeScript configs and linting rules
- [ ] Unify dependency management
- [ ] Set up shared component library

### 18. Modern Frontend Development

**Issue**: Using jQuery and outdated frontend patterns.

**Tasks**:
- [ ] Evaluate frontend frameworks (React/Vue/Svelte)
- [ ] Plan migration from jQuery to modern framework
- [ ] Add component library (Material-UI, Ant Design, etc.)
- [ ] Implement PWA capabilities for mobile
- [ ] Add offline support

### 19. Observability & Monitoring

**Issue**: Limited logging and monitoring capabilities.

**Tasks**:
- [ ] Add structured logging (Winston/Pino)
- [ ] Implement metrics collection (Prometheus)
- [ ] Add error tracking (Sentry)
- [ ] Create dashboards for monitoring
- [ ] Add health check endpoints

## Build System & Tooling

### 20. Align Justfile Patterns with Best Practices

**Issue**: Complex custom Justfile patterns that could be simplified.

**Official Standard**: [Just Manual](../reference-repos/just/README.md)
- Use standard recipe patterns
- Leverage built-in functions
- Minimize shell complexity

**Current Code Issues**:
- Complex shell scripts in `Justfile` recipes
- Custom nvm/pyenv integration instead of using just's built-in features

**Recommendation**: Simplify recipes using just's built-in capabilities.

### 21. Build System Simplification (Future Consideration)

**Status**: ⚠️ **DEFERRED** - Current talos system is working well

**Background**: A previous plan outlined reducing infrastructure code from ~2,200 lines to <100 lines by adopting monorepo tooling. However, the current talos system has proven robust and well-designed.

**Current Assessment**:
- ✅ Talos is already world-class with excellent documentation
- ✅ Build system is stable and well-understood
- ✅ Development workflow is efficient

**Future Consideration**: Only pursue if current system becomes a bottleneck.

## Documentation & Standards

### 22. Improve Add-on Documentation

**Issue**: Inconsistent documentation between add-ons and missing user-facing docs.

**Official Standard**: [Add-on Configuration](../reference-repos/developers.home-assistant/docs/add-ons/configuration.md)
- Provide `DOCS.md` for user documentation
- Include installation and configuration instructions
- Document all options and their effects

**Current Code Issues**:
- `AGENTS.md` files are developer-focused, not user-facing
- Missing installation instructions
- Configuration options not well documented

### 23. Standardize Version Management

**Issue**: Inconsistent version handling across add-ons.

**Official Standard**: [Add-on Configuration](../reference-repos/developers.home-assistant/docs/add-ons/configuration.md)
- Include `version` field in config.yaml
- Follow semantic versioning
- Maintain CHANGELOG.md

**Status**: ✅ **COMPLETED** - Version management standardized

**Completed Items**:
- ✅ `.nvmrc` and `.python-version` are single source of truth
- ✅ Versions automatically injected into builds and documentation
- ✅ Consistent version handling across all add-ons

### 24. Implement Proper Ingress Configuration

**Issue**: Custom ingress setup that may not align with Home Assistant standards.

**Official Standard**: [Add-on Communication](../reference-repos/developers.home-assistant/docs/add-ons/communication.md)
- Use standard ingress configuration
- Follow Home Assistant UI/UX patterns
- Implement proper authentication

**Current Code Issues**:
- `grid-dashboard/addon.yaml` has custom ingress configuration
- May not follow Home Assistant frontend patterns

### 25. Deployment Safety & Rollback Guarantees

**Issue**: Documentation promises atomic deployments, automatic rollback, consolidated `/tmp/deployment-<timestamp>.log` logging, and single-session SSH efficiency, but the current deployment implementation deploys add-ons sequentially with no rollback/state tracking, spawns new SSH/`scp` sessions per add-on, and never writes the documented logs. Operators rely on guarantees that are not actually provided.

**Tasks**:
- [ ] Implement true batch transaction support with rollback of already deployed add-ons when later items fail
- [ ] Maintain a single SSH control socket/session per deployment and upload multiple archives without reconnecting
- [ ] Emit structured deployment logs on disk and surface their location in CLI output
- [ ] Keep documentation in sync with actual capabilities until parity exists

### 26. Deployment Performance & Scalability

**Issue**: Batch deployments rebuild each add-on twice (once via the pre-deploy Just recipes and again inside `deploy_addon`) and rerun prerequisite validation for every add-on, leading to very slow deployments as the number or size of add-ons grows.

**Tasks**:
- [ ] Cache build artifacts within a deployment run instead of rebuilding inside each phase
- [ ] Run `deploy-preflight`/SSH/HA health checks once per deployment (or reuse cached results) instead of per add-on
- [ ] Provide flags to reuse previous prereq checks when deploying multiple add-ons sequentially
- [ ] Record deployment timing metrics to catch regressions

### 27. CLI Command Hygiene

**Issue**: `talos addons deploy` is defined twice in `talos/src/talos/cli.py`, so one definition silently overrides the other. This leaves dead code and opens the door to inconsistent behavior.

**Tasks**:
- [ ] Remove the duplicate command registration and ensure only the enhanced deployment implementation is exposed
- [ ] Add CLI tests that validate command registration and option handling
- [ ] Document the command tree in `docs/deployment/enhanced-deployment-guide.md`

### 28. Safe Home Assistant Config Deployment

**Issue**: The Home Assistant config deploy flow hardcodes `root@homeassistant.local:22`, deletes the on-box backup before validating, skips `ha core check`, and always restarts Home Assistant even if errors occur. There is no way to target staging/DR hosts, and failures can leave the system bricked with no automatic rollback.

**Tasks**:
- [ ] Parameterize host/user/port/secrets for the config deploy recipes
- [ ] Keep the safety backup until validation and health checks succeed
- [ ] Reintroduce `ha core check` (or equivalent) before performing the restart
- [ ] Make full restarts conditional on validation results and support staging deployments

### 29. Decouple Add-on and Config Deployment

**Issue**: `just deploy` always runs the full Home Assistant config pipeline (including TypeScript generation and destructive `rsync --delete`) even when an operator only wants to push an add-on, increasing blast radius and slowing urgent hotfixes.

**Tasks**:
- [ ] Allow add-on deployments to run without touching configs (e.g., `just deploy --skip-config`)
- [ ] Provide a dedicated “config deploy” command that can be composed with add-on deploys when needed
- [ ] Ensure both flows share the same environment parameterization
- [ ] Document recommended workflows for add-on-only, config-only, and full-stack deployments

## Implementation Strategy & Migration Plan

### Phase 1: Critical Security Updates (Weeks 1-2)

**Goal**: Address immediate security vulnerabilities and compatibility issues

**Tasks**:
- [ ] Complete npm package security updates (#2)
- [ ] Implement security best practices (#8)
- [ ] Add AppArmor profiles for all add-ons
- [ ] Run comprehensive security audit

**Success Criteria**:
- ✅ No high/critical security vulnerabilities
- ✅ All add-ons have security profiles
- ✅ System passes security audit

### Phase 2: Home Assistant Standards (Weeks 3-4)

**Goal**: Align with official Home Assistant development standards

**Tasks**:
- [ ] Adopt official add-on configuration format (#4)
- [ ] Implement standard add-on file structure (#5)
- [ ] Add missing documentation (DOCS.md, CHANGELOG.md) (#22)
- [ ] Use official base images (#6)

**Success Criteria**:
- ✅ All add-ons use standard config.yaml format
- ✅ All add-ons have required documentation files
- ✅ Add-ons build with official HA base images

### Phase 3: Development Experience (Weeks 5-6)

**Goal**: Modernize development tooling and testing

**Tasks**:
- [ ] Update TypeScript and build system (#10)
- [ ] Implement testing infrastructure (#11)
- [ ] Create hardware abstraction layer (#12)
- [ ] Adopt official testing approach (#9)

**Success Criteria**:
- ✅ Modern TypeScript 5.x with strict settings
- ✅ Comprehensive test suite with CI/CD
- ✅ Local development works without hardware

### Phase 4: Architecture Modernization (Weeks 7-8)

**Goal**: Update core architecture and Home Assistant integration

**Tasks**:
- [ ] Home Assistant integration modernization (#7)
- [ ] API modernization (#14)
- [ ] Implement standard add-on communication (#13)
- [ ] Update to current Home Assistant version

**Success Criteria**:
- ✅ Current Home Assistant version
- ✅ Z-Wave JS instead of legacy XML
- ✅ Modern API patterns with documentation

### Phase 5: Long-term Improvements (Ongoing)

**Goal**: Progressive enhancement and optimization

**Tasks**:
- [ ] Containerization improvements (#15)
- [ ] Monorepo structure evaluation (#17)
- [ ] Modern frontend development (#18)
- [ ] Observability and monitoring (#19)

**Success Criteria**:
- ✅ Improved deployment options
- ✅ Better development experience
- ✅ Enhanced monitoring and observability

## Priority Matrix

### 🔴 Immediate (Do First)
- **Security Updates** (#2, #8) - Security vulnerabilities
- **Add-on Configuration** (#4) - HA compatibility
- **Security Practices** (#8) - Production readiness

### 🟡 High Priority (Do Next)
- **Standard File Structure** (#5) - HA compliance
- **Official Base Images** (#6) - Standard deployment
- **TypeScript Updates** (#10) - Development efficiency
- **Testing Infrastructure** (#11) - Code quality

### 🟢 Medium Priority (Plan For)
- **Hardware Abstraction** (#12) - Development experience
- **HA Integration** (#7) - Feature completeness
- **API Modernization** (#14) - Technical debt

### 🔵 Low Priority (Future)
- **Monorepo Structure** (#17) - Optimization
- **Modern Frontend** (#18) - User experience
- **Observability** (#19) - Operations

## Risk Mitigation

### Backward Compatibility
- Maintain existing deployment system during migration
- Test each phase thoroughly before proceeding
- Keep rollback procedures documented

### Testing Strategy
- Verify builds and deployments after each change
- Test on development Raspberry Pi before production
- Maintain comprehensive test coverage

### Documentation
- Update documentation as changes are made
- Keep migration notes for future reference
- Document rollback procedures

## Status Tracking

### ✅ Completed Improvements
- **Node.js Security Updates** (#1) - Upgraded to v24.18.0 LTS
- **Python Standardization** (#3) - Standardized to Python 3.14.6
- **Version Management** (#23) - Single source of truth implemented
- **Documentation Updates** - Comprehensive docs created and updated

### 🔄 In Progress
- **Documentation Consolidation** - This roadmap consolidates all scattered plans

### 📋 Next Immediate Actions
1. **Replace deprecated npm packages** (#2) - Start with `request` → `axios`
2. **Create AppArmor profiles** (#8) - Begin with printer add-on
3. **Update add-on configurations** (#4) - Convert first add-on to config.yaml

## Consolidated Sources

This roadmap consolidates and replaces the following documents:
- ✅ Original modernization TODO list (removed)
- ✅ Build system migration plan (removed - deferred)
- ✅ `talos/docs/IMPROVEMENTS.md` - Talos-specific improvements
- ✅ Various scattered improvement notes in other docs

## Maintenance

This roadmap should be updated as:
- Items are completed (move to ✅ Completed section)
- New issues are discovered (add with appropriate priority)
- Priorities change based on business needs
- Technology landscape evolves

**Review Schedule**: Monthly review of priorities and progress
