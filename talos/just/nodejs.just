# Node.js addon library for smarthome project
# Provides Node.js-specific recipes and patterns

# Import common functionality
import '../just/common.just'
import '../just/nvm.just'

# ============================================================================
# NODE.JS VARIABLES
# ============================================================================

# Node.js paths and commands
node_modules := "node_modules"
package_json := "package.json"

# ============================================================================
# NODE.JS RECIPES
# ============================================================================

# Set up Node.js environment and install dependencies
[group: 'setup']
setup:
    @echo "🔧 Setting up Node.js environment..."
    @{{nvm_use}}
    @if [ -f "{{package_json}}" ]; then \
        echo "📦 Installing dependencies..."; \
        npm install; \
    else \
        echo "⚠️  No package.json found, skipping npm install"; \
    fi

# Run development server
[group: 'dev']
dev: setup
    @echo "🚀 Starting development server..."
    @{{nvm_use}}
    @npm run dev

# Run tests
[group: 'test']
test: setup
    @echo "🧪 Running tests..."
    @{{nvm_use}}
    @npm test

# Run linting
[group: 'test']
lint: setup
    @echo "🔍 Running linter..."
    @{{nvm_use}}
    @npm run lint

# Format code
[group: 'format']
fmt: setup
    @echo "✨ Formatting code..."
    @{{nvm_use}}
    @npm run format

# Type checking (if TypeScript)
[group: 'test']
typecheck: setup
    @echo "🔍 Running type check..."
    @{{nvm_use}}
    @if npm run | grep -q "typecheck"; then \
        npm run typecheck; \
    else \
        echo "No typecheck script found, skipping"; \
    fi

# Build production assets
[group: 'build']
build: setup
    @echo "🏗️  Building production assets..."
    @{{nvm_use}}
    @npm run build

# Clean node_modules and build artifacts
[group: 'clean']
clean-node:
    @echo "🧹 Cleaning Node.js artifacts..."
    @rm -rf {{node_modules}}
    @rm -rf dist/
    @rm -rf build/
    @rm -rf .next/
    @echo "✅ Node.js clean complete"

# Install specific package
[group: 'deps']
install PACKAGE:
    @echo "📦 Installing {{PACKAGE}}..."
    @{{nvm_use}}
    @npm install {{PACKAGE}}

# Install dev dependency
[group: 'deps']
install-dev PACKAGE:
    @echo "📦 Installing {{PACKAGE}} as dev dependency..."
    @{{nvm_use}}
    @npm install --save-dev {{PACKAGE}}

# Update dependencies
[group: 'deps']
update:
    @echo "⬆️  Updating dependencies..."
    @{{nvm_use}}
    @npm update

# Audit dependencies for security issues
[group: 'security']
audit:
    @echo "🔒 Auditing dependencies..."
    @{{nvm_use}}
    @npm audit

# Fix security issues automatically
[group: 'security']
audit-fix:
    @echo "🔧 Fixing security issues..."
    @{{nvm_use}}
    @npm audit fix

# Show outdated packages
[group: 'info']
outdated:
    @echo "📊 Checking for outdated packages..."
    @{{nvm_use}}
    @npm outdated || true

# Run all checks (test, lint, typecheck, audit)
[group: 'test']
check: test lint typecheck audit
    @echo "✅ All checks passed!"
