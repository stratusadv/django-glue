from __future__ import annotations

from functools import update_wrapper
from types import MethodType
from typing import Any, get_type_hints

from django_glue.access import GlueAccess
from django_glue.glue.attributes.declared import DeclaredAttributeOptions

_MISSING = object()


class GlueNamespace:
    """Descriptor marking an existing attribute as a callable namespace provider.

    `Glue.namespace` marks a declaration; it does not change how that declaration
    behaves. The wrapped value is the ordinary class attribute the project
    already writes. A namespace compiles the provider's declared attributes into
    the owning object's capability beneath one path, but has no address, policy,
    state, or lifecycle of its own.

    Three declaration forms are supported:

    - variable, descriptor prototype: ``services = Glue.namespace(Service())``
      where ``Service`` is a descriptor (every ``BaseConstructor`` subclass is);
    - variable, provider class: ``services = Glue.namespace(Service)``, which Glue
      instantiates per access with the glued target; and
    - function: ``@Glue.namespace`` on a method whose return annotation names the
      provider class.

    `__get__` is forwarded to the wrapped value, so class access, instance
    access, and nesting behave exactly as they do without the marker.
    """

    def __init__(
        self,
        value: Any = _MISSING,
        *,
        required_access: GlueAccess = GlueAccess.VIEW,
    ) -> None:
        self.required_access = required_access
        self.name: str | None = None
        self.target: Any = None
        self._is_function_form = False
        self._provider_type: type[Any] | None = None
        self.__glue_options__: DeclaredAttributeOptions | None = None
        if value is not _MISSING:
            self._bind(value)

    def _bind(self, value: Any) -> None:
        if callable(value) and not isinstance(value, type):
            self._bind_provider_function(value)
            return
        if isinstance(value, type):
            self._provider_type = value
        elif hasattr(value, '__get__'):
            self._provider_type = type(value)
        else:
            msg = (
                'Glue.namespace requires a descriptor or a class, '
                f'not a plain instance of {type(value).__name__!r}.'
            )
            raise TypeError(msg)
        self.target = value
        self._update_glue_options()

    def _bind_provider_function(self, func: Any) -> None:
        self.target = func
        self._is_function_form = True
        self._provider_type = self._resolve_return_annotation(func)
        self._update_glue_options()
        update_wrapper(self, func)

    @staticmethod
    def _resolve_return_annotation(func: Any) -> type[Any]:
        globalns = getattr(func, '__globals__', None) or {}
        try:
            annotation = get_type_hints(func, globalns=globalns).get('return')
        except Exception as error:
            msg = (
                'Glue.namespace function form requires a statically nameable '
                f'return annotation naming the provider class ({type(error).__name__}).'
            )
            raise TypeError(msg) from error
        if annotation is None or annotation is type(None):
            msg = (
                'Glue.namespace function form requires a return annotation '
                'naming the provider class.'
            )
            raise TypeError(msg)
        return annotation

    def _update_glue_options(self) -> None:
        self.__glue_options__ = DeclaredAttributeOptions(
            required_access=self.required_access,
            is_callable=False,
            is_namespace=True,
            provider_type=self._provider_type,
        )

    def __call__(self, func: Any) -> GlueNamespace:
        marker = type(self)()
        marker._bind_provider_function(func)
        return marker

    def __set_name__(self, owner: type, name: str) -> None:
        self.name = name
        if hasattr(self.target, '__set_name__'):
            self.target.__set_name__(owner, name)

    def __get__(self, instance: Any, owner: type | None = None) -> Any:
        if self._is_function_form and callable(self.target):
            if instance is None:
                return self
            return MethodType(self.target, instance)
        if isinstance(self.target, type):
            if instance is None:
                return self
            return self.target(instance)
        if hasattr(self.target, '__get__'):
            return self.target.__get__(instance, owner)
        return self.target
