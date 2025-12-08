# Python addon library for smarthome project
# Provides Python-specific recipes and patterns

# Import common functionality
import '../just/common.just'

# ============================================================================
# PYTHON VARIABLES
# ============================================================================

# Python paths and files
python_version := env_var_or_default("PYTHON_VERSION", "3.11")
venv_dir := ".venv"
requirements_file := "requirements.txt"
requirements_dev_file := "requirements-dev.txt"

# Python executable paths
python_exe := if os_family() == "windows" { venv_dir + "/Scripts/python.exe" } else { venv_dir + "/bin/python" }
pip_exe := if os_family() == "windows" { venv_dir + "/Scripts/pip" } else { venv_dir + "/bin/pip" }

# System Python command
system_python := if os_family() == "windows" { "python" } else { "python3" }

# ============================================================================
# PYTHON RECIPES
# ============================================================================

# Create virtual environment and install dependencies
[group: 'setup']
setup:
    @echo "🐍 Setting up Python environment..."
    @if [ ! -d "{{venv_dir}}" ]; then \
        echo "Creating virtual environment..."; \
        {{system_python}} -m venv {{venv_dir}}; \
    fi
    @echo "📦 Installing dependencies..."
    @{{pip_exe}} install --upgrade pip wheel
    @if [ -f "{{requirements_file}}" ]; then \
        {{pip_exe}} install -r {{requirements_file}}; \
    fi
    @if [ -f "{{requirements_dev_file}}" ]; then \
        {{pip_exe}} install -r {{requirements_dev_file}}; \
    fi

# Run development server
[group: 'dev']
dev: setup
    @echo "🚀 Starting development server..."
    @{{python_exe}} -m app

# Run tests
[group: 'test']
test: setup
    @echo "🧪 Running tests..."
    @{{python_exe}} -m pytest

# Run tests with coverage
[group: 'test']
test-coverage: setup
    @echo "🧪 Running tests with coverage..."
    @{{python_exe}} -m pytest --cov=. --cov-report=html --cov-report=term

# Run linting with flake8
[group: 'test']
lint: setup
    @echo "🔍 Running linter..."
    @{{python_exe}} -m flake8 .

# Format code with black
[group: 'format']
fmt: setup
    @echo "✨ Formatting code with black..."
    @{{python_exe}} -m black .

# Type checking with mypy
[group: 'test']
typecheck: setup
    @echo "🔍 Running type check..."
    @{{python_exe}} -m mypy .

# Install specific package
[group: 'deps']
install PACKAGE:
    @echo "📦 Installing {{PACKAGE}}..."
    @{{pip_exe}} install {{PACKAGE}}

# Install dev dependency
[group: 'deps']
install-dev PACKAGE:
    @echo "📦 Installing {{PACKAGE}} as dev dependency..."
    @{{pip_exe}} install {{PACKAGE}}
    @echo "{{PACKAGE}}" >> {{requirements_dev_file}}

# Update requirements files
[group: 'deps']
freeze:
    @echo "📋 Updating requirements files..."
    @{{pip_exe}} freeze > {{requirements_file}}

# Clean Python artifacts
[group: 'clean']
clean-python:
    @echo "🧹 Cleaning Python artifacts..."
    @rm -rf {{venv_dir}}
    @find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    @find . -type f -name "*.pyc" -delete 2>/dev/null || true
    @rm -rf .pytest_cache/
    @rm -rf htmlcov/
    @rm -rf .coverage
    @rm -rf dist/
    @rm -rf build/
    @rm -rf *.egg-info/
    @echo "✅ Python clean complete"

# Security audit with safety
[group: 'security']
audit: setup
    @echo "🔒 Auditing dependencies for security issues..."
    @{{pip_exe}} install safety
    @{{python_exe}} -m safety check

# Show outdated packages
[group: 'info']
outdated: setup
    @echo "📊 Checking for outdated packages..."
    @{{pip_exe}} list --outdated

# Run all checks (test, lint, typecheck, audit)
[group: 'test']
check: test lint typecheck audit
    @echo "✅ All checks passed!"
