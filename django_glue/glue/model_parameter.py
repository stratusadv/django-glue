from __future__ import annotations

import inspect
import warnings
from functools import cached_property, update_wrapper
from typing import TYPE_CHECKING, Any, get_type_hints

from django.core.exceptions import ValidationError
from django.db.models import Model

from django_glue.conf import settings
from django_glue.exceptions import (
    GlueComponentParameterError,
    GlueModelInstanceNotFoundError,
    GlueModelParameterMismatchWarning,
)
from django_glue.glue.attributes.declared import DeclaredAttribute

if TYPE_CHECKING:
    from collections.abc import Callable

RESOLVING_PARAMETERS_ATTRIBUTE = '_glue_resolving_model_parameters'


def _missing_loads(resolved: Model, supplied: Model, prefix: str = '') -> set[str]:
    """What ``resolved`` has loaded and ``supplied`` lacks, named as the queryset
    arguments that load it: annotations and fields, prefetched relations, and
    ``select_related`` relations, followed into each relation both have loaded
    so a nested load is named by its path (``project__client``)."""
    internal = {'_state', '_prefetched_objects_cache'}
    names = set(resolved.__dict__) - set(supplied.__dict__) - internal
    names |= (
        set(getattr(resolved, '_prefetched_objects_cache', {}))
        - set(getattr(supplied, '_prefetched_objects_cache', {}))
    )
    missing = {f'{prefix}{name}' for name in names}
    for name, related in resolved._state.fields_cache.items():
        if name not in supplied._state.fields_cache:
            missing.add(f'{prefix}{name}')
            continue
        supplied_related = supplied._state.fields_cache[name]
        if related is not None and supplied_related is not None:
            missing |= _missing_loads(related, supplied_related, f'{prefix}{name}__')
    return missing


class ModelParameter(DeclaredAttribute):
    """A component parameter whose value is a model row, declared by decorating
    its initializer with ``Glue.ComponentParameter`` (ADR 021).

    The component stores what construction or assignment supplied: a loaded
    instance, used as is, or a primary key, resolved through the initializer on
    the first read. Only the key is signed into ``target.parameters``.
    """

    def __init__(self, initializer: Callable[[Any, Any], Model]) -> None:
        super().__init__(parameter=True)
        self.initializer = initializer
        update_wrapper(self, initializer)

    @cached_property
    def model_class(self) -> type[Model]:
        return_type = get_type_hints(self.initializer).get('return')
        if not (isinstance(return_type, type) and issubclass(return_type, Model)):
            msg = (
                f'Model parameter {self.initializer.__qualname__!r} must annotate its '
                'return type with a Django model class.'
            )
            raise GlueComponentParameterError(msg)
        return return_type

    def __set_name__(self, owner: type, name: str) -> None:
        super().__set_name__(owner, name)
        self.resolved_name = f'__glue_resolved_{name}'

    def validate_declaration(self) -> None:
        parameters = list(inspect.signature(self.initializer).parameters.values())
        if len(parameters) != 2 or any(
            parameter.kind not in {inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD}
            for parameter in parameters
        ):
            msg = f'Model parameter {self.name!r} must be declared as def {self.name}(self, pk).'
            raise GlueComponentParameterError(msg)
        _ = self.model_class

    def __get__(self, instance: Any, owner: type | None = None) -> Any:
        if instance is None:
            return self
        if self.resolved_name in instance.__dict__:
            return instance.__dict__[self.resolved_name]
        if self.storage_name not in instance.__dict__:
            msg = f'Model parameter {self.name!r} has not been supplied.'
            raise AttributeError(msg)

        resolving = instance.__dict__.setdefault(RESOLVING_PARAMETERS_ATTRIBUTE, set())
        if self.name in resolving:
            msg = f'Model parameter {self.name!r} is part of an initializer cycle.'
            raise GlueComponentParameterError(msg)

        resolving.add(self.name)
        try:
            supplied = instance.__dict__[self.storage_name]
            value = (
                self._verified(instance, supplied)
                if isinstance(supplied, self.model_class)
                else self._resolved(instance, supplied)
            )
        finally:
            resolving.discard(self.name)

        instance.__dict__[self.resolved_name] = value
        return value

    def __set__(self, instance: Any, value: Any) -> None:
        if isinstance(value, self.model_class):
            if value.pk is None:
                msg = f'Model parameter {self.name!r} needs a saved {self.model_class.__name__}.'
                raise GlueComponentParameterError(msg)
            supplied = value
        elif isinstance(value, Model) or value is None:
            msg = (
                f'Model parameter {self.name!r} takes a {self.model_class.__name__} '
                f'or its primary key, not {value!r}.'
            )
            raise GlueComponentParameterError(msg)
        else:
            try:
                supplied = self.model_class._meta.pk.to_python(value)
            except ValidationError as error:
                msg = f'Model parameter {self.name!r} received an invalid primary key {value!r}.'
                raise GlueComponentParameterError(msg) from error

        instance.__dict__[self.storage_name] = supplied
        instance.__dict__.pop(self.resolved_name, None)

    def signed_value(self, instance: Any) -> int | str:
        """The key as it is signed: an int, or a string for any other key type,
        such as a UUID, which the key field's ``to_python`` reads back."""
        supplied = instance.__dict__[self.storage_name]
        key = supplied.pk if isinstance(supplied, Model) else supplied
        return key if isinstance(key, int) else str(key)

    def _resolved(self, instance: Any, pk: Any) -> Model:
        try:
            value = self.initializer(instance, pk)
        except self.model_class.DoesNotExist as error:
            raise GlueModelInstanceNotFoundError(self.model_class.__name__, pk) from error
        if not isinstance(value, self.model_class):
            msg = (
                f'Model parameter {self.name!r} initializer returned '
                f'{type(value).__name__}, not {self.model_class.__name__}.'
            )
            raise GlueComponentParameterError(msg)
        return value

    def _verified(self, instance: Any, supplied: Model) -> Model:
        configured = settings.DJANGO_GLUE_VERIFY_MODEL_PARAMETERS
        if not (settings.DEBUG if configured is None else configured):
            return supplied

        try:
            resolved = self._resolved(instance, supplied.pk)
        except GlueModelInstanceNotFoundError as error:
            msg = (
                f'Model parameter {self.name!r} was supplied a {self.model_class.__name__} '
                f'(pk={supplied.pk}) that its initializer does not return.'
            )
            raise GlueComponentParameterError(msg) from error

        missing = sorted(_missing_loads(resolved, supplied))
        if not missing:
            return supplied

        warnings.warn(
            GlueModelParameterMismatchWarning(
                f'Model parameter {self.name!r} was supplied a {self.model_class.__name__} '
                f'(pk={supplied.pk}) without {", ".join(missing)}, which its initializer '
                'loads; using the initializer\'s instance.'
            ),
            stacklevel=2,
        )
        return resolved
