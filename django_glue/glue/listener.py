from __future__ import annotations

import inspect
from functools import cached_property
from typing import TYPE_CHECKING, Any, Callable, Generic, TypeVar

from django_glue.access import GlueAccess
from django_glue.exceptions import GlueComponentRegistrationError
from django_glue.glue.event import GlueEvent
from django_glue.glue.operation import GlueOperation, GlueOperationKind

if TYPE_CHECKING:
    from django.http import HttpRequest

    from django_glue.glue.component import Component
    from django_glue.glue.policy import GluePolicy


SourceT = TypeVar('SourceT', bound='Component')


class ReceivedEvent(Generic[SourceT]):
    """A descendant's event delivered to a listener (ADR 024).

    ``detail`` was relayed by the client and is untrusted input. ``source`` is
    rebuilt from the emitting component's signed token on first access.
    """

    def __init__(
        self,
        *,
        name: str,
        detail: dict[str, Any],
        source_policy: GluePolicy,
        source_class: type[SourceT],
        request: HttpRequest,
    ) -> None:
        self.name = name
        self.detail = detail
        self._source_policy = source_policy
        self._source_class = source_class
        self._request = request

    @property
    def source_address(self) -> str:
        return self._source_policy.address

    @cached_property
    def source(self) -> SourceT:
        source = self._source_class._reconstruct_from_policy(self._source_policy)
        source.request = self._request
        source._address = self._source_policy.address
        source._require_authorization(GlueOperation(
            kind=GlueOperationKind.REFRESH,
            attribute=None,
            required_access=GlueAccess.VIEW,
        ))
        return source


class GlueListener:
    """A component method run when a descendant emits one of ``events`` (ADR 024).

    It is not a declared attribute: the client reaches it only through the
    component's built-in ``$receive`` call, never by name.
    """

    def __init__(
        self,
        function: Callable[..., None],
        events: tuple[GlueEvent, ...],
        *,
        required_access: GlueAccess,
        skip_rerender: bool,
    ) -> None:
        parameters = list(inspect.signature(function).parameters.values())[1:]
        if len(parameters) > 1:
            msg = f'Listener {function.__name__!r} takes at most one argument, the received event.'
            raise TypeError(msg)
        self.function = function
        self.event_identities = tuple(event.identity for event in events)
        self.required_access = required_access
        self.skip_rerender = skip_rerender
        self.takes_event = bool(parameters)
        self.name = function.__name__

    def __set_name__(self, owner: type, name: str) -> None:
        from django_glue.glue.component import Component  # noqa: PLC0415

        if not issubclass(owner, Component):
            raise GlueComponentRegistrationError(
                f'Glue.listener {name!r} is declared on {owner.__name__}, which is not a component.'
            )
        self.name = name

    def __get__(self, instance: Any, owner: type | None = None) -> Any:
        if instance is None:
            return self
        return self.function.__get__(instance, owner)

    def run(self, component: Component, event: ReceivedEvent[Any]) -> None:
        if self.takes_event:
            self.function(component, event)
        else:
            self.function(component)


def listener(
    *events: GlueEvent,
    required_access: GlueAccess = GlueAccess.VIEW,
    skip_rerender: bool = False,
) -> Callable[[Callable[..., None]], GlueListener]:
    undeclared = [event for event in events if not isinstance(event, GlueEvent) or event.identity is None]
    if not events or undeclared:
        msg = 'Glue.listener takes one or more events declared on a class, such as RowComponent.saved.'
        raise TypeError(msg)

    def decorate(function: Callable[..., None]) -> GlueListener:
        return GlueListener(
            function,
            events,
            required_access=required_access,
            skip_rerender=skip_rerender,
        )

    return decorate
