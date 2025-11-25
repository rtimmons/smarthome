from __future__ import annotations

from pathlib import Path


# Location of the talos package directory (talos/src/talos)
PACKAGE_ROOT = Path(__file__).resolve().parents[0]
# Top-level talos directory
TALOS_ROOT = PACKAGE_ROOT.parents[1]
# Repository root
REPO_ROOT = TALOS_ROOT.parent
# Template directory for add-on generation
TEMPLATE_DIR = TALOS_ROOT / "templates"
# Build artifacts directory for add-ons
ADDON_BUILD_ROOT = REPO_ROOT / "build" / "home-assistant-addon"
