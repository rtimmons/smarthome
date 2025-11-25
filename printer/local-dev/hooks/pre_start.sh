#!/usr/bin/env bash
set -euo pipefail

# Pre-start validation runs the same checks as pre_setup
"$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/pre_setup.sh"
