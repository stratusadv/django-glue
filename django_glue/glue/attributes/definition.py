from __future__ import annotations

import inspect
import json
from collections.abc import Mapping
from contextlib import suppress
from dataclasses import dataclass
from enum import StrEnum
from types import NoneType, UnionType
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Union,
    get_args,
    get_origin,
    get_type_hints,
)

from django_glue.encoders import GlueResponseJSONEncoder
from django_glue.exceptions import GlueInvalidAttributeError

if TYPE_CHECKING:
    from django_glue.access import GlueAccess
    from django_glue.glue.attributes.adapter import GlueAttributeAdapter
    from django_glue.glue.base import BaseGlue

_NAMESPACE_DEPTH_LIMIT = 20

_PROTOTYPE_SENSITIVE_CLIENT_NAMES = frozenset(
    {
        'constructor',
        'hasOwnProperty',
        'isPrototypeOf',
        'propertyIsEnumerable',
        'prototype',
        'toLocaleString',
        'toString',
        'valueOf',
        '__proto__',
    }
)


class GlueValueRole(StrEnum):
    RECONSTRUCTOR = 'reconstructor'
    EDITABLE_STATE = 'editable_state'
    DERIVED_OUTPUT = 'derived_output'


class GlueAttributeKind(StrEnum):
    VALUE = 'value'
    CALLABLE = 'callable'
    NAMESPACE = 'namespace'
    CHILD = 'child'


def _resolve_glue_result_annotation(
    target: Callable[..., Any] | None,
) -> tuple[type[Any] | None, bool]:
    if target is None:
        return None, False

    target = inspect.unwrap(target)
    annotation = inspect.signature(target).return_annotation
    if annotation is inspect.Signature.empty:
        return None, False

    with suppress(NameError, TypeError):
        annotation = get_type_hints(
            target,
            globalns=getattr(target, '__globals__', None),
        ).get('return', annotation)

    is_nullable = False
    if get_origin(annotation) in {Union, UnionType}:
        arguments = get_args(annotation)
        if len(arguments) != 2 or NoneType not in arguments:
            return None, False
        annotation = next(
            argument
            for argument in arguments
            if argument is not NoneType
        )
        is_nullable = True

    from django_glue.glue.base import BaseGlue  # noqa: PLC0415

    if not isinstance(annotation, type) or not issubclass(annotation, BaseGlue):
        return None, False
    return annotation, is_nullable


@dataclass(frozen=True, slots=True, kw_only=True)
class GlueAttributeDefinition:
    path: str
    source_name: str
    kind: GlueAttributeKind
    required_access: GlueAccess | Callable[[BaseGlue], GlueAccess]
    value_role: GlueValueRole | None = None
    is_parameter: bool = False
    is_identity: bool = False
    provider_type: type[Any] | None = None
    expected_type: type[Any] | None = None
    is_nullable: bool = False
    allowed_arguments: tuple[str, ...] = ()
    injected_arguments: tuple[str, ...] = ()
    render_as_html: bool = False
    getter: Callable[[Any], Any] | None = None
    setter: Callable[[Any, Any], None] | None = None
    callable_target: Callable[[Any], Callable[..., Any]] | None = None
    adapter: GlueAttributeAdapter | None = None

    def __post_init__(self) -> None:
        self._validate_path()
        self._validate_kind()
        self._validate_binding()

    def _validate_path(self) -> None:
        if not self.path or not self.source_name:
            msg = 'Glue attribute paths and source names cannot be empty.'
            raise ValueError(msg)
        for segment in self.path.split('.'):
            if not segment:
                msg = f'Glue attribute path {self.path!r} has an empty segment.'
                raise ValueError(msg)
            if segment.startswith('$'):
                msg = (
                    f'Glue attribute path {self.path!r} uses reserved client '
                    f'name {segment!r}.'
                )
                raise ValueError(msg)
            if segment in _PROTOTYPE_SENSITIVE_CLIENT_NAMES:
                msg = (
                    f'Glue attribute path {self.path!r} uses prototype-sensitive '
                    f'client name {segment!r}.'
                )
                raise ValueError(msg)

    def _validate_kind(self) -> None:
        if self.kind == GlueAttributeKind.VALUE and self.value_role is None:
            msg = f'Value attribute {self.path!r} requires a value role.'
            raise ValueError(msg)
        if self.kind != GlueAttributeKind.VALUE and self.value_role is not None:
            msg = f'Non-value attribute {self.path!r} cannot declare a value role.'
            raise ValueError(msg)
        if self.kind != GlueAttributeKind.VALUE and self.is_parameter:
            msg = f'Non-value attribute {self.path!r} cannot be a construction parameter.'
            raise ValueError(msg)
        if self.kind == GlueAttributeKind.NAMESPACE and self.provider_type is None:
            msg = f'Namespace attribute {self.path!r} requires a provider type.'
            raise ValueError(msg)
        if self.kind == GlueAttributeKind.CHILD and self.expected_type is None:
            msg = f'Child attribute {self.path!r} requires an expected Glue type.'
            raise ValueError(msg)
        if (
            self.expected_type is not None
            and self.kind not in {GlueAttributeKind.CALLABLE, GlueAttributeKind.CHILD}
        ):
            msg = (
                f'{self.kind.value.capitalize()} attribute {self.path!r} cannot '
                'declare a Glue result type.'
            )
            raise ValueError(msg)
        if self.expected_type is not None:
            from django_glue.glue.base import BaseGlue  # noqa: PLC0415

            if not issubclass(self.expected_type, BaseGlue):
                msg = f'Attribute {self.path!r} expected type must be a BaseGlue subclass.'
                raise ValueError(msg)
        if self.is_nullable and self.expected_type is None:
            msg = f'Attribute {self.path!r} cannot be nullable without a Glue result type.'
            raise ValueError(msg)
        if self.kind == GlueAttributeKind.CHILD and self.value_role is not None:
            msg = f'Child attribute {self.path!r} cannot declare a value role.'
            raise ValueError(msg)
        if self.kind != GlueAttributeKind.CALLABLE and (
            self.allowed_arguments
            or self.injected_arguments
            or self.render_as_html
        ):
            msg = f'Non-callable attribute {self.path!r} cannot declare callable options.'
            raise ValueError(msg)

    def _validate_binding(self) -> None:
        if self.getter is not None and self.kind in {
            GlueAttributeKind.CALLABLE,
            GlueAttributeKind.NAMESPACE,
        }:
            msg = f'{self.kind.value.capitalize()} attribute {self.path!r} cannot declare a getter.'
            raise ValueError(msg)
        if (
            self.setter is not None
            and self.value_role != GlueValueRole.EDITABLE_STATE
        ):
            msg = f'Only editable value attribute {self.path!r} can declare a setter.'
            raise ValueError(msg)
        if (
            self.callable_target is not None
            and self.kind != GlueAttributeKind.CALLABLE
        ):
            msg = f'Non-callable attribute {self.path!r} cannot declare a callable target.'
            raise ValueError(msg)


@dataclass(frozen=True, slots=True, kw_only=True)
class BoundGlueAttribute:
    definition: GlueAttributeDefinition
    owner: Any
    provider: Any | None = None

    @property
    def metadata(self) -> dict[str, Any]:
        return self.owner._get_attribute_metadata(self)

    def schema(self) -> dict[str, Any]:
        if self.definition.adapter is None:
            return {}
        return dict(self.definition.adapter.schema())

    def unsigned_data(self) -> dict[str, Any]:
        if self.definition.adapter is None:
            return {}
        return dict(self.definition.adapter.unsigned_data())

    def get(self) -> Any:
        if self.definition.callable_target is not None:
            value = self.definition.callable_target(self._binding_owner())
        elif self.definition.getter is not None:
            value = self.definition.getter(self._binding_owner())
        else:
            value = getattr(
                self._resolve_attribute_owner(),
                self.definition.source_name,
            )
        self._validate_value_result(value)
        return value

    def call(self, *args: Any, **kwargs: Any) -> Any:
        if self.definition.kind != GlueAttributeKind.CALLABLE:
            msg = f'Glue attribute {self.definition.path!r} is not callable.'
            raise TypeError(msg)
        result = self.get()(*args, **kwargs)
        self._validate_callable_result(result)
        return result

    def _validate_callable_result(self, result: Any) -> None:
        from django_glue.glue.base import BaseGlue  # noqa: PLC0415

        expected_type = self.definition.expected_type
        if expected_type is None:
            if isinstance(result, BaseGlue):
                msg = (
                    f'Glue callable {self.definition.path!r} returned a Glue object '
                    'without a Glue-object return annotation.'
                )
                raise TypeError(msg)
            return

        if result is None:
            if self.definition.is_nullable:
                return
            msg = f'Non-nullable Glue callable {self.definition.path!r} returned None.'
            raise TypeError(msg)

        if not isinstance(result, expected_type):
            msg = (
                f'Glue callable {self.definition.path!r} must return an unbound '
                f'{expected_type.__qualname__}, not {type(result).__qualname__}.'
            )
            raise TypeError(msg)
        if result.is_bound:
            msg = f'Glue callable {self.definition.path!r} returned a bound Glue object.'
            raise ValueError(msg)

    def resolve_child(self) -> BaseGlue | None:
        if self.definition.kind != GlueAttributeKind.CHILD:
            msg = f'Glue attribute {self.definition.path!r} is not a child slot.'
            raise TypeError(msg)

        from django_glue.glue.base import BaseGlue  # noqa: PLC0415

        glue_object = self.get()
        if glue_object is None:
            if self.definition.is_nullable:
                return None
            msg = f'Non-nullable Glue child {self.definition.path!r} returned None.'
            raise TypeError(msg)

        expected_type = self.definition.expected_type
        if expected_type is None or not isinstance(glue_object, expected_type):
            expected_name = (
                expected_type.__qualname__
                if expected_type is not None
                else BaseGlue.__qualname__
            )
            msg = (
                f'Glue child {self.definition.path!r} must return an unbound '
                f'{expected_name}, not {type(glue_object).__qualname__}.'
            )
            raise TypeError(msg)
        if glue_object.is_bound:
            msg = f'Glue child {self.definition.path!r} returned a bound Glue object.'
            raise ValueError(msg)
        return glue_object

    def apply_update(self, value: Any) -> None:
        if self.definition.value_role != GlueValueRole.EDITABLE_STATE:
            msg = f'Glue attribute {self.definition.path!r} does not accept client updates.'
            raise TypeError(msg)
        if self.definition.setter is not None:
            self.definition.setter(
                self._binding_owner(),
                value,
            )
            return
        setattr(
            self._resolve_attribute_owner(),
            self.definition.source_name,
            value,
        )

    def _resolve_attribute_owner(self) -> Any:
        attribute_owner = self._binding_owner()
        for segment in self.definition.path.split('.')[:-1]:
            attribute_owner = getattr(attribute_owner, segment)
        return attribute_owner

    def _binding_owner(self) -> Any:
        return self.provider if self.provider is not None else self.owner

    def _validate_value_result(self, value: Any) -> None:
        if self.definition.kind != GlueAttributeKind.VALUE:
            return

        from django_glue.glue.base import BaseGlue  # noqa: PLC0415

        if self._contains_type(value, BaseGlue, set()):
            msg = (
                f'Glue value attribute {self.definition.path!r} returned a Glue '
                'object outside an addressed child declaration.'
            )
            raise TypeError(msg)
        try:
            json.dumps(value, cls=GlueResponseJSONEncoder)
        except TypeError as error:
            owner_type = type(self._binding_owner())
            value_type = type(value)
            raise GlueInvalidAttributeError(
                attribute=self.definition.path,
                owner=f'{owner_type.__module__}.{owner_type.__qualname__}',
                value_type=f'{value_type.__module__}.{value_type.__qualname__}',
            ) from error

    @classmethod
    def _contains_type(
        cls,
        value: Any,
        expected_type: type[Any],
        visited: set[int],
    ) -> bool:
        if isinstance(value, expected_type):
            return True
        if not isinstance(value, Mapping | list | tuple | set | frozenset):
            return False
        if id(value) in visited:
            return False
        visited.add(id(value))
        if isinstance(value, Mapping):
            values = (*value.keys(), *value.values())
        else:
            values = value
        return any(
            cls._contains_type(item, expected_type, visited)
            for item in values
        )
