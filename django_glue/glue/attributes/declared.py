from dataclasses import dataclass
from copy import deepcopy
from functools import update_wrapper
from types import MethodType
from typing import Any
from typing import Callable

from django_glue.access import GlueAccess

_MISSING = object()


@dataclass(frozen=True)
class DeclaredAttributeOptions:
    """Configuration for a declared glue attribute, attached as __glue_options__ by the decorator."""

    access: GlueAccess
    is_callable: bool = True
    loads_state: bool | list[str] | tuple[str, ...] = True
    updates_state: bool = True
    is_identity: bool = False


class DeclaredAttribute:
    """
    Descriptor for marking methods or values as Glue attributes.

    Use as a decorator on methods or assign directly on classes to expose
    them through the Glue system. The access level determines what operations
    are permitted on this attribute.

    Examples:
        # As a decorator on a method
        @Attribute(access=GlueAccess.CHANGE)
        def save(self, data: dict) -> dict:
            ...

        # As a decorator on a method that doesn't need client state
        @Attribute(access=GlueAccess.VIEW, loads_state=False)
        def load(self) -> dict:
            ...

        # As a class attribute for a value
        services = Attribute(TaskService(), access=GlueAccess.DELETE)
    """

    def __init__(
        self,
        value: Any = _MISSING,
        *,
        access: GlueAccess,
        loads_state: bool | list[str] | tuple[str, ...] = True,
        updates_state: bool = True,
        identity: bool = False,
        default: Any = _MISSING,
        default_factory: Callable[[], Any] | object = _MISSING,
    ) -> None:
        if value is not _MISSING and default is not _MISSING:
            raise TypeError('DeclaredAttribute received both value and default.')
        if default is not _MISSING and default_factory is not _MISSING:
            raise TypeError('DeclaredAttribute received both default and default_factory.')

        self._access = access
        self._loads_state = loads_state
        self._updates_state = updates_state
        self._identity = identity
        self.default = default
        self.default_factory = default_factory
        self.name: str | None = None
        self.storage_name: str | None = None
        self.target: Any = None
        self._is_callable = False

        if value is not _MISSING:
            if self._is_decoratable(value):
                self._bind_target(value)
            elif hasattr(value, '__get__'):
                self.target = value
            else:
                self.default = value

        self._update_glue_options()

    def _update_glue_options(self) -> None:
        """Create and attach the __glue_options__ based on current state."""
        self.__glue_options__ = DeclaredAttributeOptions(
            access=self._access,
            is_callable=self._is_callable,
            loads_state=self._loads_state,
            updates_state=self._updates_state,
            is_identity=self._identity,
        )

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        if self.target is None and len(args) == 1 and not kwargs and self._is_decoratable(args[0]):
            return self._bind_target(args[0])
        if callable(self.target):
            return self.target(*args, **kwargs)
        msg = f"'{self.__class__.__name__}' object is not callable"
        raise TypeError(msg)

    def __set_name__(self, owner: type, name: str) -> None:
        self.name = name
        self.storage_name = f'__glue_attribute_{name}'
        if hasattr(self.target, '__set_name__'):
            self.target.__set_name__(owner, name)

    def __get__(self, instance: Any, owner: type | None = None) -> Any:
        if hasattr(self.target, '__get__'):
            return self.target.__get__(instance, owner)
        if instance is None:
            return self
        if isinstance(self.target, property):
            return self.target.__get__(instance, owner)
        if callable(self.target):
            return MethodType(self.target, instance)
        if self.storage_name in instance.__dict__:
            return instance.__dict__[self.storage_name]
        if self.default_factory is not _MISSING:
            value = self._prepare_default(self.default_factory())
            instance.__dict__[self._get_storage_name()] = value
            return value
        if self.default is not _MISSING:
            value = self._prepare_default(self._clone_default())
            instance.__dict__[self._get_storage_name()] = value
            return value
        return None

    def __set__(self, instance: Any, value: Any) -> None:
        if isinstance(self.target, property) and self.target.fset is not None:
            self.target.__set__(instance, value)
            return
        if hasattr(self.target, '__set__'):
            self.target.__set__(instance, value)
            return
        instance.__dict__[self._get_storage_name()] = value

    def __delete__(self, instance: Any) -> None:
        if isinstance(self.target, property) and self.target.fdel is not None:
            self.target.__delete__(instance)
            return
        if hasattr(self.target, '__delete__'):
            self.target.__delete__(instance)
            return
        instance.__dict__.pop(self._get_storage_name(), None)

    def _bind_target(self, target: Callable[..., Any] | property) -> 'DeclaredAttribute':
        self.target = target
        self._is_callable = not isinstance(target, property)
        wrapped = target.fget if isinstance(target, property) else target
        if wrapped is not None:
            update_wrapper(self, wrapped)
        self._update_glue_options()
        return self

    def _get_storage_name(self) -> str:
        if not self.storage_name:
            msg = 'Attribute must be assigned to a class before it can store values.'
            raise AttributeError(msg)
        return self.storage_name

    def _clone_default(self) -> Any:
        try:
            return deepcopy(self.default)
        except Exception:
            return self.default

    def _prepare_default(self, value: Any) -> Any:
        self._reset_glue_default(value, set())
        return value

    def _reset_glue_default(self, value: Any, seen: set[int]) -> None:
        if id(value) in seen:
            return

        seen.add(id(value))

        from django_glue.glue.base import BaseGlue

        if isinstance(value, BaseGlue):
            value.request = None
            value.__dict__.pop('policy', None)
            value.__dict__.pop('metadata', None)
            value.__dict__.pop('state', None)
            value.__dict__.pop('_attribute_collector', None)
            for child in value.__dict__.values():
                self._reset_glue_default(child, seen)
            return

        if isinstance(value, dict):
            for child in value.values():
                self._reset_glue_default(child, seen)
            return

        if isinstance(value, list | tuple | set):
            for child in value:
                self._reset_glue_default(child, seen)

    @staticmethod
    def _is_decoratable(value: Any) -> bool:
        return callable(value) or isinstance(value, property)
