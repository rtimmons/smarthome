from __future__ import annotations

"""Base classes and shared types for label templates.

Each template module must expose an instance of :class:`TemplateDefinition`.
The project loader will bind in the module slug, derive default metadata, and
surface the instance through :class:`printer_service.label_templates.LabelTemplate`.
Subclass :class:`TemplateDefinition` and provide concrete implementations of
``render`` (required) and ``get_form_context`` (optional) to define a template.
"""

from abc import ABC, abstractmethod
from collections.abc import ItemsView, Iterator, Mapping
from typing import Optional, Protocol, Sequence, Mapping as TypingMapping, TypeAlias, TypeVar

from PIL import Image

from printer_service.label_specs import BrotherLabelSpec

TemplateFormValue: TypeAlias = (
    str
    | int
    | float
    | bool
    | None
    | Sequence["TemplateFormValue"]
    | TypingMapping[str, "TemplateFormValue"]
)
"""Normalized values accepted within template form submissions.

This alias supports nested JSON-compatible structures so complex payloads (for
example widget lists) can flow straight from a caller to the template. Lists and
mappings must themselves contain only :data:`TemplateFormValue` entries.
"""

_T = TypeVar("_T")


class TemplateFormData(Mapping[str, TemplateFormValue]):
    """Normalized form payload passed to a template renderer.

    The object wraps the raw mapping submitted by the browser and exposes
    helpers that coerce typed values into the trimmed string inputs templates
    typically expect.
    """

    def __init__(self, data: Mapping[str, TemplateFormValue]) -> None:
        self._data = dict(data)

    def __getitem__(self, key: str) -> TemplateFormValue:
        return self._data[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def __contains__(self, key: object) -> bool:
        return key in self._data

    def items(self) -> ItemsView[str, TemplateFormValue]:
        """Return the underlying mapping's items view."""
        return self._data.items()

    def get(
        self,
        key: str,
        default: TemplateFormValue | _T | None = None,
    ) -> TemplateFormValue | _T | None:
        """Return the raw value for ``key`` without coercion."""
        return self._data.get(key, default)

    def get_str(
        self,
        key: str,
        *aliases: str,
        default: str = "",
    ) -> str:
        """Return the first present value among ``key`` and ``aliases`` as a trimmed string."""
        for candidate in (key, *aliases):
            if candidate in self._data:
                value = self._data[candidate]
                return default if value is None else str(value).strip()
        return default


TemplateContext: TypeAlias = Mapping[str, object]
"""Additional values exposed to the Flask form template.

Like :data:`TemplateFormValue`, this alias stays in :mod:`base` to avoid
import-time template discovery when only the typing helpers are needed.
"""


class TemplateRenderable(Protocol):
    """Protocol describing any object that can produce a label image from form data."""

    def render(self, form_data: TemplateFormData) -> Image.Image:
        """Return the generated PIL image for the supplied form data."""
        ...


class TemplateDefinition(ABC):
    """Interface that all label template implementations must follow."""

    def __init__(self) -> None:
        # Bound label slug set by Template discovery; see :meth:`bind_slug`.
        self.slug: str = ""

    def bind_slug(self, slug: str) -> None:
        """Attach the module slug set by the loader to this implementation.

        The slug is available to subclasses that derive values dynamically—for
        example ``default_form_template()`` uses it to build ``{slug}.html``.
        This method is invoked exactly once during template discovery.
        """
        if self.slug and self.slug != slug:
            raise ValueError(f"Template already bound to slug '{self.slug}'.")
        self.slug = slug

    def default_display_name(self) -> str:
        """Return a fallback display name derived from the slug."""
        if not self.slug:
            raise RuntimeError("Cannot derive display_name before bind_slug has run.")
        return self.slug.replace("_", " ").title()

    def default_form_template(self) -> str:
        """Return the default Jinja template filename derived from the slug."""
        if not self.slug:
            raise RuntimeError("Cannot derive form_template before bind_slug has run.")
        return f"{self.slug}.html"

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Human-friendly name shown in navigation and form headings."""
        ...

    @property
    @abstractmethod
    def form_template(self) -> str:
        """Jinja filename relative to :mod:`printer_service.templates` rendered for the form inputs."""
        ...

    @abstractmethod
    def render(self, form_data: TemplateFormData) -> Image.Image:
        """Create and return a label image for the provided form data."""

    def get_form_context(self) -> TemplateContext:
        """Return extra context passed to the template's Jinja form.

        Override when the form requires curated options (for example select
        choices) or defaults that are not baked into the template file.
        """
        return {}

    def preferred_label_spec(self) -> Optional[BrotherLabelSpec]:
        """Return the target label spec used for sizing diagnostics, if any."""
        return None


__all__ = [
    "TemplateContext",
    "TemplateDefinition",
    "TemplateFormData",
    "TemplateFormValue",
    "TemplateRenderable",
]
