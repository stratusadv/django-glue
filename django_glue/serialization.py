from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from pydantic import PydanticUserError, TypeAdapter
from pydantic import ValidationError as PydanticValidationError
from pydantic_core import PydanticSerializationError

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from django_glue.glue.attributes.description import GlueFieldDescription


class GlueSerializerError(ValueError):
    pass


class GlueSerializer(ABC):
    """
    How the values of one declaration cross the wire, in both directions. The
    declaration is the target: a type hint, or a field that stands for one.
    """

    def __init__(self, target: Any) -> None:
        self.target = target

    @classmethod
    @abstractmethod
    def supports(cls, target: Any) -> bool:
        raise NotImplementedError

    @abstractmethod
    def load(self, raw: Any) -> Any:
        """The value the browser sent, or one Python assigned, as the declaration holds it."""
        raise NotImplementedError

    def restore(self, raw: Any) -> Any:
        """
        A value this serializer dumped into a signed token. A serializer whose
        signed values load as any other keeps this default.
        """
        return self.load(raw)

    def dump(self, value: Any) -> Any:
        """The value in its wire form. A serializer whose values already are keeps this default."""
        return value

    def default(self) -> Any:
        """
        The value an attribute holds when its declaration gives no default. A
        serializer with no value of its own to offer keeps this default.
        """
        return None

    def adopt(self, value: Any) -> Any:
        """
        A default or an assigned value as the attribute holds it. A serializer
        whose values are held as they are given keeps this default.
        """
        return value

    def check(self) -> None:  # noqa: B027
        """
        Refuse a target this serializer cannot handle before any value arrives.
        A serializer with nothing to check keeps this default.
        """

    def description(
        self,
        *,
        read: Callable[[], Any],
        editable: bool,
    ) -> GlueFieldDescription | None:
        """
        What the browser needs to draw a control for one of its values, read
        through ``read``. A serializer with nothing to describe keeps this default.
        """
        _ = read, editable
        return None


class GlueSerializerRegistry:
    def __init__(
        self,
        serializer_classes: Iterable[type[GlueSerializer]] = (),
    ) -> None:
        self._serializer_classes = list(serializer_classes)

    def register(
        self,
        serializer_class: type[GlueSerializer],
        *,
        prepend: bool = True,
    ) -> type[GlueSerializer]:
        if prepend:
            self._serializer_classes.insert(0, serializer_class)
        else:
            self._serializer_classes.append(serializer_class)
        return serializer_class

    def resolve(self, target: Any) -> GlueSerializer:
        """The serializer of a declaration: the first registered class that supports it."""
        for serializer_class in self._serializer_classes:
            if serializer_class.supports(target):
                return serializer_class(target)
        return PlainSerializer(target)


class PlainSerializer(GlueSerializer):
    """An undeclared value: it crosses the wire as the JSON it already is."""

    @classmethod
    def supports(cls, target: Any) -> bool:
        return target is None

    def load(self, raw: Any) -> Any:
        return raw


_ADAPTERS: dict[Any, TypeAdapter[Any]] = {}


def _adapter(target: Any) -> TypeAdapter[Any]:
    """
    The pydantic adapter for a type hint, built once: building one compiles a
    schema, which costs 30-200x as much as using it, and a component's
    parameters are loaded and dumped on every construction.
    """
    try:
        return _ADAPTERS[target]
    except KeyError:
        adapter = _ADAPTERS[target] = TypeAdapter(target)
        return adapter
    except TypeError:
        # An unhashable type hint cannot be a cache key.
        return TypeAdapter(target)


class AnnotationSerializer(GlueSerializer):
    """A type hint, loaded and dumped by pydantic."""

    @classmethod
    def supports(cls, target: Any) -> bool:
        return target is not None

    def load(self, raw: Any) -> Any:
        try:
            return _adapter(self.target).validate_python(raw)
        except (PydanticValidationError, PydanticUserError, TypeError, ValueError) as error:
            raise GlueSerializerError(str(error)) from error

    def dump(self, value: Any) -> Any:
        try:
            return _adapter(self.target).dump_python(value, mode='json')
        except (PydanticUserError, PydanticSerializationError) as error:
            raise GlueSerializerError(str(error)) from error

    def check(self) -> None:
        try:
            _adapter(self.target)
        except PydanticUserError as error:
            raise GlueSerializerError(str(error)) from error


glue_serializer_registry = GlueSerializerRegistry(
    (
        PlainSerializer,
        AnnotationSerializer,
    )
)


__all__ = [
    'GlueSerializer',
    'GlueSerializerError',
    'GlueSerializerRegistry',
    'glue_serializer_registry',
]
