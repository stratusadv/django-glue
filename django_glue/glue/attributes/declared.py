from functools import update_wrapper
from types import MethodType
from typing import Any
from typing import Callable

from django_glue.access import GlueAccess

_MISSING = object()


class Attribute:
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
        loads_state: bool = True,
    ) -> None:
        self.__required_glue_access__ = access
        self.loads_state = loads_state
        self.default = _MISSING
        self.name: str | None = None
        self.storage_name: str | None = None
        self.target: Any = None
        self.is_callable = False
        if value is not _MISSING:
            if self._is_decoratable(value):
                self._bind_target(value)
            elif hasattr(value, '__get__'):
                self.target = value
            else:
                self.default = value

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
        if self.default is not _MISSING:
            return self.default
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

    def _bind_target(self, target: Callable[..., Any] | property) -> 'Attribute':
        self.target = target
        self.is_callable = not isinstance(target, property)
        wrapped = target.fget if isinstance(target, property) else target
        if wrapped is not None:
            update_wrapper(self, wrapped)
        return self

    def _get_storage_name(self) -> str:
        if not self.storage_name:
            msg = 'Attribute must be assigned to a class before it can store values.'
            raise AttributeError(msg)
        return self.storage_name

    @staticmethod
    def _is_decoratable(value: Any) -> bool:
        return callable(value) or isinstance(value, property)
