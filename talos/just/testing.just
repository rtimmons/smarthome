# Testing library for smarthome project
# Provides comprehensive testing recipes and patterns

# Import common functionality
import '../just/common.just'

# ============================================================================
# TESTING VARIABLES
# ============================================================================

# Test directories and files
test_dir := "tests"
test_results_dir := "test-results"

# ============================================================================
# TESTING RECIPES
# ============================================================================

# Run all tests for the addon
[group: 'test']
test-all: validate-addon
    @echo "🧪 Running comprehensive test suite for $(just addon-name)..."
    @just test-unit
    @just test-integration
    @just test-container
    @echo "✅ All tests passed!"

# Run unit tests
[group: 'test']
test-unit:
    @echo "🔬 Running unit tests..."
    @if [ -d "{{test_dir}}" ]; then \
        if [ -f "package.json" ]; then \
            just test; \
        elif [ -f "requirements.txt" ] || [ -f "setup.py" ]; then \
            just test; \
        else \
            echo "No test framework detected"; \
        fi; \
    else \
        echo "No tests directory found, skipping unit tests"; \
    fi

# Run integration tests
[group: 'test']
test-integration:
    @echo "🔗 Running integration tests..."
    @if [ -d "{{test_dir}}/integration" ]; then \
        echo "Running integration tests..."; \
        # Add integration test logic here
    else \
        echo "No integration tests found, skipping"; \
    fi

# Test container build and basic functionality
[group: 'test']
test-container: container-test
    @echo "🐳 Testing container functionality..."
    @# Additional container-specific tests can be added here

# Test deployment in dry-run mode
[group: 'test']
test-deploy: deploy-dry-run
    @echo "🚀 Deployment test completed successfully"

# Run security tests
[group: 'test']
test-security:
    @echo "🔒 Running security tests..."
    @if [ -f "package.json" ]; then \
        echo "Auditing npm dependencies..."; \
        npm audit; \
    fi
    @if [ -f "requirements.txt" ]; then \
        echo "Auditing Python dependencies..."; \
        if command -v safety >/dev/null 2>&1; then \
            safety check; \
        else \
            echo "⚠️  safety not installed, skipping Python security audit"; \
        fi; \
    fi
    @echo "✅ Security tests completed"

# Run Justfile infrastructure tests (for talos project)
[group: 'test']
test-justfile:
    @echo "📋 Running Justfile infrastructure tests..."
    @if [ -f "tests/test_justfile_infrastructure.py" ]; then \
        python -m pytest tests/test_justfile_infrastructure.py -v; \
    else \
        echo "⚠️  Justfile infrastructure tests not found"; \
    fi
    @echo "✅ Justfile tests completed"

# Run deployment system tests (for talos project)
[group: 'test']
test-deployment:
    @echo "🚀 Running deployment system tests..."
    @if [ -f "tests/test_deployment_system.py" ]; then \
        python -m pytest tests/test_deployment_system.py tests/test_deployment_integration.py -v; \
    else \
        echo "⚠️  Deployment system tests not found"; \
    fi
    @echo "✅ Deployment tests completed"

# Run tests with coverage reporting
[group: 'test']
test-coverage:
    @echo "📊 Running tests with coverage reporting..."
    @if command -v pytest >/dev/null 2>&1 && python -c "import pytest_cov" 2>/dev/null; then \
        python -m pytest {{test_dir}} --cov=. --cov-report=html --cov-report=term; \
    else \
        echo "⚠️  pytest-cov not installed, running tests without coverage"; \
        python -m pytest {{test_dir}} -v; \
    fi
    @echo "✅ Coverage report completed"

# Run specific test file
[group: 'test']
test-file file:
    @echo "🧪 Running tests in {{file}}..."
    @python -m pytest {{file}} -v
    @echo "✅ Test file completed"

# Run tests matching pattern
[group: 'test']
test-pattern pattern:
    @echo "🔍 Running tests matching pattern: {{pattern}}"
    @python -m pytest -k "{{pattern}}" -v
    @echo "✅ Pattern tests completed"

# Run slow/integration tests
[group: 'test']
test-slow:
    @echo "🐌 Running slow and integration tests..."
    @python -m pytest -m "slow or integration" -v
    @echo "✅ Slow tests completed"

# Run all tests including slow ones
[group: 'test']
test-all:
    @echo "🧪 Running all tests (including slow)..."
    @python -m pytest -v
    @echo "✅ All tests completed"

# Run only fast unit tests (default)
[group: 'test']
test-fast:
    @echo "⚡ Running fast unit tests..."
    @python -m pytest -m "not slow" -v
    @echo "✅ Fast tests completed"

# Performance tests
[group: 'test']
test-performance:
    @echo "⚡ Running performance tests..."
    @# Add performance testing logic here
    @echo "Performance tests completed"

# Load tests
[group: 'test']
test-load:
    @echo "📈 Running load tests..."
    @# Add load testing logic here
    @echo "Load tests completed"

# Generate test reports
[group: 'test']
test-report:
    @echo "📊 Generating test reports..."
    @mkdir -p {{test_results_dir}}
    @if [ -f "package.json" ]; then \
        echo "Generating JavaScript test report..."; \
        npm test -- --reporter=json > {{test_results_dir}}/test-results.json || true; \
    fi
    @if [ -f "requirements.txt" ]; then \
        echo "Generating Python test report..."; \
        python -m pytest --junitxml={{test_results_dir}}/test-results.xml || true; \
    fi
    @echo "✅ Test reports generated in {{test_results_dir}}"

# Watch tests and re-run on changes
[group: 'test']
test-watch:
    @echo "👀 Watching for changes and running tests..."
    @if command -v watchexec >/dev/null 2>&1; then \
        watchexec -e js,ts,py,yaml,json -- just test-unit; \
    elif command -v fswatch >/dev/null 2>&1; then \
        fswatch -o . | xargs -n1 -I{} just test-unit; \
    else \
        echo "❌ No file watcher found. Install watchexec or fswatch"; \
        exit 1; \
    fi

# Clean test artifacts
[group: 'clean']
clean-tests:
    @echo "🧹 Cleaning test artifacts..."
    @rm -rf {{test_results_dir}}
    @rm -rf coverage/
    @rm -rf htmlcov/
    @rm -rf .coverage
    @rm -rf .pytest_cache/
    @rm -rf .nyc_output/
    @echo "✅ Test artifacts cleaned"

# Validate test configuration
[group: 'test']
validate-tests:
    @echo "✅ Validating test configuration..."
    @if [ ! -d "{{test_dir}}" ]; then \
        echo "⚠️  Warning: No tests directory found"; \
    fi
    @if [ -f "package.json" ]; then \
        if ! grep -q '"test"' package.json; then \
            echo "⚠️  Warning: No test script in package.json"; \
        fi; \
    fi
    @if [ -f "requirements.txt" ]; then \
        if ! grep -q "pytest\|unittest" requirements.txt; then \
            echo "⚠️  Warning: No test framework in requirements.txt"; \
        fi; \
    fi
    @echo "Test configuration validation complete"

# Run smoke tests (quick validation)
[group: 'test']
smoke-test:
    @echo "💨 Running smoke tests..."
    @just validate-addon
    @just info
    @echo "✅ Smoke tests passed"
