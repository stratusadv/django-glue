from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from functools import update_wrapper
from types import MethodType
from typing import TYPE_CHECKING, Any, Callable

from django_glue.access import GlueAccess
from django_glue.glue.attributes.definition import GlueValueRole
from django_glue.glue.attributes.value_adapters import DEFAULT_VALUE_ADAPTERS, GlueValueAdapter

if TYPE_CHECKING:
    from django_glue.glue.base import BaseGlue

_MISSING = object()
_SESSION_VALUE_ONLY = (
    'Glue.attr session=True is only valid for value declarations, such as '
    'step: int = Glue.SessionAttr(0). It cannot decorate a method or property.'
)


@dataclass(frozen=True, slots=True, kw_only=True)
class DeclaredAttributeOptions:
    """Configuration for a declared glue attribute, attached as __glue_options__ by the decorator."""

    required_access: GlueAccess | Callable[[BaseGlue], GlueAccess] = GlueAccess.VIEW
    is_callable: bool = True
    render_as_html: bool = False
    skip_rerender: bool = False
    is_parameter: bool = False
    value_role: GlueValueRole | None = None
    is_namespace: bool = False
    provider_type: type[Any] | None = None
    expected_type: type[Any] | None = None
    is_nullable: bool = False
    is_declared_child: bool = False


class DeclaredAttribute:
    """
    Descriptor for marking methods or values as Glue attributes.

    Use as a decorator on methods or assign directly on classes to expose
    them through the Glue system. The required access level determines what
    operations are permitted on this attribute, and defaults to VIEW.

    Examples:
        # As a decorator on a method
        @Attribute(required_access=GlueAccess.CHANGE)
        def save(self, data: dict) -> dict:
            ...

        # As a class attribute for a value
        services = Attribute(TaskService(), required_access=GlueAccess.DELETE)

        # As a decorator on a method that returns a TemplateResponse and
        # should be rendered to HTML on the client instead of sent as raw
        # text (see Glue.html_attr for a shortcut that sets this for you)
        @Attribute(render_as_html=True)
        def render_panel(self, request: HttpRequest) -> TemplateResponse:
            ...
    """

    def __init__(
        self,
        value: Any = _MISSING,
        *,
        required_access: GlueAccess | Callable[[BaseGlue], GlueAccess] = GlueAccess.VIEW,
        parameter: bool = False,
        editable: bool = False,
        session: bool = False,
        render_as_html: bool = False,
        skip_rerender: bool = False,
        default: Any = _MISSING,
        default_factory: Callable[[], Any] | object = _MISSING,
        glue_factory: Callable[..., Any] | None = None,
        value_adapters: list[GlueValueAdapter] | None = None,
    ) -> None:
        if value is not _MISSING and default is not _MISSING:
            raise TypeError('DeclaredAttribute received both value and default.')
        if default is not _MISSING and default_factory is not _MISSING:
            raise TypeError('DeclaredAttribute received both default and default_factory.')

        self.required_access = required_access
        self._parameter = parameter
        self._editable = editable
        self._session = session
        self._render_as_html = render_as_html
        self._skip_rerender = skip_rerender
        self.default = default
        self.default_factory = default_factory
        self.glue_factory = glue_factory
        self.value_adapters = value_adapters if value_adapters is not None else DEFAULT_VALUE_ADAPTERS
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

        if session:
            self._store_in_session()

        self._update_glue_options()

    def _update_glue_options(self) -> None:
        """Create and attach the __glue_options__ based on current state."""
        self.__glue_options__ = DeclaredAttributeOptions(
            required_access=self.required_access,
            is_callable=self._is_callable,
            render_as_html=self._render_as_html,
            skip_rerender=self._skip_rerender,
            is_parameter=self._parameter,
            value_role=self._resolve_value_role(),
        )

    def _store_in_session(self) -> None:
        """
        Keep this value in the owning component's session rather than on the
        instance (ADR 031). The session is the only copy, so the value is sent
        down as derived output and never signed into the token. Every option
        that would give it a second home, or that only a callable has, is
        rejected.
        """
        conflicts = [
            option
            for option, given in (
                ('parameter', self._parameter),
                ('editable', self._editable),
                ('render_as_html', self._render_as_html),
                ('skip_rerender', self._skip_rerender),
                ('glue_factory', self.glue_factory is not None),
            )
            if given
        ]
        if conflicts:
            msg = f'Glue.attr session=True cannot be combined with {", ".join(conflicts)}.'
            raise TypeError(msg)
        if self.target is not None:
            raise TypeError(_SESSION_VALUE_ONLY)

        from django_glue.glue.components.session import SessionValue

        self.target = SessionValue(
            default=None if self.default is _MISSING else self.default,
            default_factory=None if self.default_factory is _MISSING else self.default_factory,
        )

    def _resolve_value_role(self) -> GlueValueRole | None:
        if self._is_callable:
            return None
        if self._session:
            return GlueValueRole.DERIVED_OUTPUT
        if self._editable:
            return GlueValueRole.EDITABLE_STATE
        return GlueValueRole.RECONSTRUCTOR

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        if len(args) == 1 and not kwargs and self._is_decoratable(args[0]):
            if self._session:
                raise TypeError(_SESSION_VALUE_ONLY)
            if self.target is None:
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
        if not self._parameter and not self._skip_rerender and not self._session:
            return
        from django_glue.glue.base import BaseGlue
        from django_glue.glue.components.component import Component

        if self._session and not (isinstance(owner, type) and issubclass(owner, Component)):
            msg = (
                f'Glue.SessionAttr (Glue.attr(session=True)) on {owner.__name__}.{name} keeps '
                "the value in a Glue.Component's session; "
                f'{owner.__name__!r} is not a Component.'
            )
            raise TypeError(msg)

        if self._skip_rerender and not (isinstance(owner, type) and issubclass(owner, Component)):
            msg = (
                f'skip_rerender=True on {owner.__name__}.{name} only means something on a '
                "Glue.Component's callable, which re-renders the component; "
                f'{owner.__name__!r} is not a Component.'
            )
            raise TypeError(msg)
        if not self._parameter:
            return
        if (
            isinstance(owner, type)
            and issubclass(owner, BaseGlue)
            and not issubclass(owner, Component)
        ):
            msg = (
                'Glue.ComponentParameter (Glue.attr(parameter=True)) marks a value as a '
                'component construction parameter and is only valid on Glue.Component '
                f'subclasses. {owner.__name__!r} is not a Component; declare the value '
                'as an ordinary Glue.attr().'
            )
            raise TypeError(msg)

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
        value = self._adapt_value(value, instance)
        instance.__dict__[self._get_storage_name()] = value

    def _adapt_value(self, value: Any, instance: Any) -> Any:
        """Run value through the first matching GlueValueAdapter, if any."""
        for adapter in self.value_adapters:
            if adapter.applies_to(value, attribute=self):
                return adapter.adapt(value, attribute=self, instance=instance)
        return value

    def __delete__(self, instance: Any) -> None:
        if isinstance(self.target, property) and self.target.fdel is not None:
            self.target.__delete__(instance)
            return
        if hasattr(self.target, '__delete__'):
            self.target.__delete__(instance)
            return
        instance.__dict__.pop(self._get_storage_name(), None)

    def _bind_target(self, target: Callable[..., Any] | property) -> DeclaredAttribute:
        self.target = target
        self._is_callable = not isinstance(target, property)
        self._validate_callable_options()
        wrapped = target.fget if isinstance(target, property) else target
        if wrapped is not None:
            update_wrapper(self, wrapped)
        self._update_glue_options()
        return self

    def _validate_callable_options(self) -> None:
        if not self._is_callable:
            return
        if self._parameter:
            msg = (
                'Glue.attr parameter=True is only valid for value declarations. '
                'A model parameter is declared with a bare @Glue.ComponentParameter '
                'on its initializer and takes no options, such as editable=True.'
            )
            raise TypeError(msg)
        if self._editable:
            msg = 'Glue.attr editable=True is only valid for value declarations.'
            raise TypeError(msg)

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
