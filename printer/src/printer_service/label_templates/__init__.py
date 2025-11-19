from __future__ import annotations

"""Template discovery, metadata, and helper exports for label templates.

New templates should live in this package and expose either a ``TEMPLATE``
instance or a ``Template`` subclass with no required constructor arguments. The
project loader binds metadata automatically and re-exports the helper toolkit
to ensure every template follows the same interface.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from importlib import import_module
from inspect import isclass
from pkgutil import iter_modules
from types import ModuleType
from typing import Dict, List, Optional

_INTERNAL_MODULES = {"base", "helper"}

from PIL import Image

from printer_service.label_specs import BrotherLabelSpec

from . import helper as helper
from .base import (
    TemplateContext,
    TemplateDefinition,
    TemplateFormData,
    TemplateFormValue,
    TemplateRenderable,
)


@dataclass(frozen=True)
class LabelTemplate:
    """Runtime wrapper for a discovered template implementation."""

    slug: str
    implementation: TemplateDefinition

    def form_context(self) -> TemplateContext:
        """Return the auxiliary data exposed to the Jinja form."""
        return self.implementation.get_form_context()

    @property
    def display_name(self) -> str:
        """Human-readable name used throughout navigation."""
        return self.implementation.display_name

    @property
    def form_template(self) -> str:
        """HTML template rendered to present the form."""
        return self.implementation.form_template

    def render(self, form_data: Mapping[str, TemplateFormValue]) -> Image.Image:
        """Delegate label creation to the underlying implementation."""
        normalized = (
            form_data if isinstance(form_data, TemplateFormData) else TemplateFormData(form_data)
        )
        return self.implementation.render(normalized)

    def preferred_label_spec(self) -> Optional[BrotherLabelSpec]:
        """Expose the template's preferred label spec for diagnostics."""
        return self.implementation.preferred_label_spec()


def _load_templates() -> Dict[str, LabelTemplate]:
    discovered: Dict[str, LabelTemplate] = {}
    for module_info in iter_modules(__path__):
        if module_info.name.startswith("_") or module_info.ispkg:
            continue
        if module_info.name in _INTERNAL_MODULES:
            continue
        module = import_module(f"{__name__}.{module_info.name}")
        implementation = _resolve_template(module, module_info.name)
        implementation.bind_slug(module_info.name)
        discovered[module_info.name] = LabelTemplate(
            slug=implementation.slug,
            implementation=implementation,
        )
    if not discovered:
        raise RuntimeError("No label templates discovered. Add at least one template module.")
    return discovered


def _resolve_template(module: ModuleType, slug: str) -> TemplateDefinition:
    candidate = getattr(module, "TEMPLATE", None)
    if isinstance(candidate, TemplateDefinition):
        return candidate
    template_class = getattr(module, "Template", None)
    if isclass(template_class) and issubclass(template_class, TemplateDefinition):
        return template_class()
    raise RuntimeError(
        f"Template module '{slug}' must expose an instance named 'TEMPLATE' or a "
        "no-argument class named 'Template' inheriting from TemplateDefinition."
    )


_TEMPLATES = _load_templates()


def all_templates() -> List[LabelTemplate]:
    """Return all discovered templates sorted by display name."""
    return sorted(_TEMPLATES.values(), key=lambda template: template.display_name.lower())


def get_template(slug: str) -> LabelTemplate:
    """Return the template associated with ``slug``."""
    try:
        return _TEMPLATES[slug]
    except KeyError as exc:
        raise KeyError(f"Unknown template '{slug}'.") from exc


def default_template() -> LabelTemplate:
    """Return the alphabetically-first template to use as a default."""
    return sorted(_TEMPLATES.values(), key=lambda template: template.display_name.lower())[0]


__all__ = [
    "LabelTemplate",
    "TemplateContext",
    "TemplateDefinition",
    "TemplateFormData",
    "TemplateFormValue",
    "TemplateRenderable",
    "all_templates",
    "get_template",
    "default_template",
    "helper",
]
