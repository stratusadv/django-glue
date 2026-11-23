from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from collections.abc import Mapping

    from django_glue.access import GlueAccess
    from django_glue.glue.base import BaseGlue


class GlueChildType(ABC):
    """
    A Django type a child's method may return bare (ADR 050): the Glue object
    that wraps it, the options ``@Glue.child`` takes for it, and what reading
    the child returns. Every child type takes ``access``.
    """

    value_type: ClassVar[type[Any]]
    glue_class: ClassVar[type[BaseGlue]]
    options: ClassVar[frozenset[str]] = frozenset()

    @classmethod
    def check_options(cls, options: Mapping[str, Any], *, child: str) -> None:
        """Refuses, when the child's class is defined, an option this type does not take."""
        unsupported = sorted(set(options) - {'access', *cls.options})
        if unsupported:
            taken = ', '.join(sorted({'access', *cls.options}))
            msg = (
                f'Glue.child {child}() returns a {cls.value_type.__qualname__}, whose '
                f'{cls.glue_class.__qualname__} takes {taken}, not {", ".join(unsupported)}.'
            )
            raise TypeError(msg)

    @classmethod
    @abstractmethod
    def wrap(cls, value: Any, *, name: str, access: GlueAccess, **options: Any) -> BaseGlue:
        """The unbound Glue object that is the child's island for ``value``."""

    @classmethod
    @abstractmethod
    def read(cls, glue_object: Any) -> Any:
        """What application code reads the child as."""


class GlueChildTypeRegistry:
    def __init__(self) -> None:
        self._child_types: list[type[GlueChildType]] = []

    def register(self, child_type: type[GlueChildType]) -> type[GlueChildType]:
        self._child_types.insert(0, child_type)
        return child_type

    def for_value_type(self, value_type: Any) -> type[GlueChildType] | None:
        """The child type that wraps a value of ``value_type``, or None when none does."""
        if not isinstance(value_type, type):
            return None
        return next(
            (child_type for child_type in self._child_types if issubclass(value_type, child_type.value_type)),
            None,
        )

    def for_glue_class(self, glue_class: type[BaseGlue]) -> type[GlueChildType] | None:
        """The child type whose Glue object ``glue_class`` is, or None when none is."""
        return next(
            (child_type for child_type in self._child_types if issubclass(glue_class, child_type.glue_class)),
            None,
        )


glue_child_type_registry = GlueChildTypeRegistry()
