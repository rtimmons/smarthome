# SmartHome Modernization TODO

## 🔴 Critical Security Updates (Immediate)

### 1. Node.js Runtime Upgrade
- [x] Update ExpressServer from Node.js v8.16.0 to v20.x LTS
- [x] Update root .nvmrc from v12.6.0 to v20.x LTS  
- [x] Test all Node.js dependencies with new runtime
- [x] Update Ansible deployment scripts for new Node version

### 2. Replace Deprecated npm Packages
- [ ] Replace `request` package with `axios` or `node-fetch`
- [ ] Replace `underscore` with native ES6+ features or `lodash`
- [ ] Update all 2019-era dependencies to current versions
- [ ] Run security audit and fix vulnerabilities

### 3. Python Environment Standardization
- [ ] Standardize on Python 3.11 or 3.12 across all components
- [ ] Update .python-version file
- [ ] Update Ansible python39 role to install correct version
- [ ] Replace deprecated `nose` with `pytest` in MetaHassConfig
- [ ] Update PyYAML from 5.3 to 6.x

## 🟡 Architecture Modernization (High Priority)

### 4. Home Assistant Integration
- [ ] Research current Home Assistant best practices
- [ ] Evaluate migration from custom metaconfig to native HA config
- [ ] Migrate from custom Z-Wave XML config to Home Assistant's Z-Wave JS
- [ ] Update from Home Assistant 2021.9.7 to current version
- [ ] Consider MQTT for device communication

### 5. Hardware Abstraction Layer
- [ ] Create hardware abstraction service for i2c-bus
- [ ] Implement mock drivers for local development
- [ ] Add interface for blind controllers
- [ ] Enable testing without physical hardware
- [ ] Document hardware interface contracts

### 6. TypeScript & Build System
- [ ] Update TypeScript from 3.6.3 to 5.x
- [ ] Migrate from ts-node to modern build tool (Vite/esbuild)
- [ ] Add proper type definitions for all modules
- [ ] Configure strict TypeScript settings
- [ ] Update ESLint and Prettier configurations

## 🟢 Infrastructure Improvements (Medium Priority)

### 7. Containerization
- [ ] Create Dockerfile for ExpressServer
- [ ] Create Dockerfile for MetaHassConfig
- [ ] Set up docker-compose for local development
- [ ] Add Docker build to deployment process
- [ ] Document container-based deployment

### 8. API Modernization
- [ ] Update Express from 4.17.1 to latest 4.x
- [ ] Add OpenAPI/Swagger documentation
- [ ] Consider GraphQL or tRPC for type-safe API
- [ ] Implement proper error handling middleware
- [ ] Add API versioning strategy

### 9. Testing Infrastructure
- [ ] Set up Jest or Vitest for unit tests
- [ ] Add integration tests with hardware mocks
- [ ] Configure GitHub Actions CI/CD pipeline
- [ ] Add end-to-end tests for critical paths
- [ ] Implement code coverage reporting

## 🔵 Development Experience (Lower Priority)

### 10. Monorepo Structure
- [ ] Evaluate monorepo tools (Nx, Turborepo, pnpm workspaces)
- [ ] Restructure project as monorepo
- [ ] Share TypeScript configs and linting rules
- [ ] Unify dependency management
- [ ] Set up shared component library

### 11. Modern Frontend
- [ ] Evaluate frontend frameworks (React/Vue/Svelte)
- [ ] Plan migration from jQuery to modern framework
- [ ] Add component library (Material-UI, Ant Design, etc.)
- [ ] Implement PWA capabilities for mobile
- [ ] Add offline support

### 12. Observability
- [ ] Add structured logging (Winston/Pino)
- [ ] Implement metrics collection (Prometheus)
- [ ] Add error tracking (Sentry)
- [ ] Create dashboards for monitoring
- [ ] Add health check endpoints

## Migration Schedule

### Phase 1: Security Updates (Week 1-2)
- [ ] Complete Node.js runtime upgrade
- [ ] Replace all deprecated packages
- [ ] Standardize Python environment
- [ ] Run security audits

### Phase 2: Hardware Abstraction (Week 3-4)
- [ ] Design abstraction layer
- [ ] Implement mock drivers
- [ ] Migrate i2c code
- [ ] Test on Raspberry Pi

### Phase 3: Containerization (Week 5-6)
- [ ] Create Docker images
- [ ] Set up docker-compose
- [ ] Update deployment scripts
- [ ] Document new deployment process

### Phase 4: Home Assistant Integration (Week 7-8)
- [ ] Research HA best practices
- [ ] Plan migration strategy
- [ ] Migrate configurations
- [ ] Test automations

### Phase 5: Progressive Improvements (Ongoing)
- [ ] Incrementally modernize frontend
- [ ] Add tests for new features
- [ ] Improve documentation
- [ ] Refactor legacy code

## Notes

- Each phase builds on the previous one to minimize risk
- Prioritize security updates and critical bug fixes
- Maintain backward compatibility during migration
- Test thoroughly on development Raspberry Pi before production deployment
- Keep detailed migration documentation for rollback procedures