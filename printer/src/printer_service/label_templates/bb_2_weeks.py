"""Compatibility wrapper for the renamed Best By template.

The template moved to :mod:`printer_service.label_templates.best_by`; this
module simply re-exports the implementation so older imports keep working.
"""

from .best_by import *  # noqa: F401,F403
