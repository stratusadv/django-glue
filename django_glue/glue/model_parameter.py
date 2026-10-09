from __future__ import annotations

import inspect
import warnings
from collections.abc import Mapping
from functools import cached_property, update_wrapper
from typing import TYPE_CHECKING, Any, ClassVar, get_args, get_type_hints

from django.apps import apps
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


def _missing_loads(
    resolved: Model,
    supplied: Model,
    prefix: str = '',
    ancestors: frozenset[int] = frozenset(),
) -> set[str]:
    """
    What ``resolved`` has loaded and ``supplied`` lacks, named as the queryset
    arguments that load it: annotations and fields, prefetched relations, and
    ``select_related`` relations, followed into each relation both have loaded
    so a nested load is named by its path (``project__client``).

    A relation that leads back to a row already on the path is not followed:
    ``select_related`` across a one-to-one caches each side on the other.
    """
    ancestors |= {id(resolved)}
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
        if related is None or supplied_related is None or id(related) in ancestors:
            continue
        missing |= _missing_loads(related, supplied_related, f'{prefix}{name}__', ancestors)
    return missing


def _key_annotation_admits_none(initializer: Callable[..., Model]) -> bool:
    """
    Whether the initializer's key, its last argument, is annotated as a union
    with ``None``, as in ``def entry(self, pk: int | None)`` (ADR 029).
    """
    key_name = list(inspect.signature(initializer).parameters)[-1]
    return type(None) in get_args(get_type_hints(initializer).get(key_name))


class ModelParameter(DeclaredAttribute):
    """
    A component parameter whose value is a model row, declared by decorating
    its initializer with ``Glue.ComponentParameter`` (ADR 021).

    The component stores what construction or assignment supplied: a loaded
    instance, used as is, or its ``(model, pk)`` key, resolved through the
    initializer on the first read. Only the key is signed into
    ``target.parameters``.

    This class holds what every model parameter does. A subclass says how a
    supplied value becomes a key, which model a row belongs to, how the
    initializer is called, and how the key is signed.
    """

    initializer_arity: ClassVar[int]

    def __init__(self, initializer: Callable[..., Model]) -> None:
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
        if len(parameters) != self.initializer_arity or any(
            parameter.kind not in {inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD}
            for parameter in parameters
        ):
            msg = (
                f'Model parameter {self.name!r} must be declared as def {self.name}(self, pk) '
                f'or def {self.name}(self, model, pk).'
            )
            raise GlueComponentParameterError(msg)

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
        else:
            supplied = self._key_from(value)

        instance.__dict__[self.storage_name] = supplied
        instance.__dict__.pop(self.resolved_name, None)

    def _key_from(self, value: Any) -> tuple[type[Model], Any]:
        """
        The ``(model, pk)`` key a supplied value that is not a row stands for.
        """
        raise NotImplementedError

    def _row_model(self, row: Model) -> type[Model]:
        """
        The model a supplied row is signed and resolved as.
        """
        raise NotImplementedError

    def _initializer_arguments(self, model: type[Model], pk: Any) -> tuple[Any, ...]:
        """
        What the initializer is called with, after the component, for a key.
        """
        raise NotImplementedError

    def _signed(self, model: type[Model], pk: Any) -> Any:
        """
        The key as it is written into ``target.parameters``.
        """
        raise NotImplementedError

    def _primary_key(self, model: type[Model], value: Any) -> Any:
        try:
            return model._meta.pk.to_python(value)
        except ValidationError as error:
            msg = f'Model parameter {self.name!r} received an invalid primary key {value!r}.'
            raise GlueComponentParameterError(msg) from error

    def _signed_key(self, pk: Any) -> Any:
        """
        A primary key as it is signed: an int, or a string for any other key
        type, such as a UUID, which the key field's ``to_python`` reads back.
        """
        return pk if isinstance(pk, int) else str(pk)

    def signed_value(self, instance: Any) -> Any:
        supplied = instance.__dict__[self.storage_name]
        if isinstance(supplied, Model):
            return self._signed(self._row_model(supplied), supplied.pk)
        return self._signed(*supplied)

    def _resolved(self, instance: Any, key: tuple[type[Model], Any]) -> Model:
        model, pk = key
        try:
            value = self.initializer(instance, *self._initializer_arguments(model, pk))
        except model.DoesNotExist as error:
            raise GlueModelInstanceNotFoundError(model.__name__, pk) from error
        if not isinstance(value, model):
            msg = (
                f'Model parameter {self.name!r} initializer returned '
                f'{type(value).__name__}, not {model.__name__}.'
            )
            raise GlueComponentParameterError(msg)
        return value

    def _verified(self, instance: Any, supplied: Model) -> Model:
        configured = settings.DJANGO_GLUE_VERIFY_MODEL_PARAMETERS
        if not (settings.DEBUG if configured is None else configured):
            return supplied

        model = self._row_model(supplied)
        try:
            resolved = self._resolved(instance, (model, supplied.pk))
        except GlueModelInstanceNotFoundError as error:
            msg = (
                f'Model parameter {self.name!r} was supplied a {model.__name__} '
                f'(pk={supplied.pk}) that its initializer does not return.'
            )
            raise GlueComponentParameterError(msg) from error

        missing = sorted(_missing_loads(resolved, supplied))
        if not missing:
            return supplied

        warnings.warn(
            GlueModelParameterMismatchWarning(
                f'Model parameter {self.name!r} was supplied a {model.__name__} '
                f'(pk={supplied.pk}) without {", ".join(missing)}, which its initializer '
                'loads; using the initializer\'s instance.'
            ),
            stacklevel=2,
        )
        return resolved


class ConcreteModelParameter(ModelParameter):
    """
    A model parameter whose initializer takes only the key,
    ``def entry(self, pk)`` (ADR 021). Its model is the one its return
    annotation names.

    When the key is annotated ``pk: int | None`` the parameter accepts a draft:
    it may be left out, its key is ``None``, and the initializer builds the row
    that does not exist yet (ADR 029).
    """

    initializer_arity: ClassVar[int] = 2

    @cached_property
    def accepts_draft(self) -> bool:
        return _key_annotation_admits_none(self.initializer)

    def validate_declaration(self) -> None:
        super().validate_declaration()
        if self.model_class is Model or self.model_class._meta.abstract:
            msg = (
                f'Model parameter {self.name!r} returns {self.model_class.__name__}, which has '
                f'no rows of its own; declare def {self.name}(self, model, pk) to accept its '
                'concrete subclasses (ADR 026).'
            )
            raise GlueComponentParameterError(msg)
        if self.accepts_draft:
            # Left out at construction, the parameter is a row that does not exist yet.
            self.default = None

    def __set__(self, instance: Any, value: Any) -> None:
        if self.accepts_draft and isinstance(value, self.model_class) and value.pk is None:
            msg = (
                f'Model parameter {self.name!r} needs a saved {self.model_class.__name__}. For a '
                'new one, leave the parameter out and build the draft in the initializer.'
            )
            raise GlueComponentParameterError(msg)
        super().__set__(instance, value)

    def _key_from(self, value: Any) -> tuple[type[Model], Any]:
        if value is None and self.accepts_draft:
            return self.model_class, None
        if isinstance(value, Model) or value is None:
            msg = (
                f'Model parameter {self.name!r} takes a {self.model_class.__name__} '
                f'or its primary key, not {value!r}.'
            )
            if value is None:
                msg += ' To accept a draft, annotate its key as int | None (ADR 029).'
            raise GlueComponentParameterError(msg)
        return self.model_class, self._primary_key(self.model_class, value)

    def _row_model(self, row: Model) -> type[Model]:  # noqa: ARG002
        return self.model_class

    def _initializer_arguments(self, model: type[Model], pk: Any) -> tuple[Any, ...]:  # noqa: ARG002
        return (pk,)

    def _signed(self, model: type[Model], pk: Any) -> Any:  # noqa: ARG002
        return None if pk is None else self._signed_key(pk)

    def signed_value(self, instance: Any) -> Any:
        """
        A draft the component has since saved is signed by its new key.
        """
        resolved = instance.__dict__.get(self.resolved_name)
        if (
            instance.__dict__[self.storage_name] == (self.model_class, None)
            and resolved is not None
            and resolved.pk is not None
        ):
            return self._signed_key(resolved.pk)
        return super().signed_value(instance)


class BoundedModelParameter(ModelParameter):
    """
    A model parameter whose initializer takes the model as well as the key,
    ``def host(self, model, pk)`` (ADR 026).

    Its return annotation is an upper bound: the parameter accepts a row of any
    concrete model that subclasses it, and signs that model's label with the key.
    """

    initializer_arity: ClassVar[int] = 3

    def validate_declaration(self) -> None:
        super().validate_declaration()
        if _key_annotation_admits_none(self.initializer):
            msg = (
                f'Model parameter {self.name!r} takes a model and a key, and does not accept a '
                'draft: None does not say which model the draft is of (ADR 029).'
            )
            raise GlueComponentParameterError(msg)

    def _key_from(self, value: Any) -> tuple[type[Model], Any]:
        if not (
            isinstance(value, Mapping)
            and value.keys() == {'model', 'pk'}
            and isinstance(value['model'], str)
            and value['pk'] is not None
        ):
            msg = (
                f'Model parameter {self.name!r} takes a {self.model_class.__name__} '
                f'or its signed model and key, not {value!r}.'
            )
            raise GlueComponentParameterError(msg)
        try:
            model = apps.get_model(value['model'])
        except (LookupError, ValueError) as error:
            msg = f'Model parameter {self.name!r} names no installed model {value["model"]!r}.'
            raise GlueComponentParameterError(msg) from error
        if not issubclass(model, self.model_class):
            msg = (
                f'Model parameter {self.name!r} received {value["model"]!r}, '
                f'which is not a {self.model_class.__name__}.'
            )
            raise GlueComponentParameterError(msg)
        return model, self._primary_key(model, value['pk'])

    def _row_model(self, row: Model) -> type[Model]:
        return type(row)

    def _initializer_arguments(self, model: type[Model], pk: Any) -> tuple[Any, ...]:
        return model, pk

    def _signed(self, model: type[Model], pk: Any) -> dict[str, Any]:
        return {'model': model._meta.label_lower, 'pk': self._signed_key(pk)}
