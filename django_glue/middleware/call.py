from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from typing import TYPE_CHECKING, Callable

from django.conf import settings
from django.core.exceptions import MiddlewareNotUsed, PermissionDenied
from django.core.signals import setting_changed
from django.dispatch import receiver
from django.http import Http404
from django.urls import Resolver404, resolve
from django.utils.module_loading import import_string

from django_glue.exceptions import GlueCallDeniedError

if TYPE_CHECKING:
    from django.http import HttpRequest, HttpResponse
    from django.urls import ResolverMatch

    from django_glue.glue.operation import GlueOperationKind
    from django_glue.resolver.attribute_call.context import AttributeCallRequestContext


@dataclass(frozen=True, slots=True, kw_only=True)
class GlueCall:
    """One addressed object in a Glue call, as a ``process_glue_call`` hook sees it."""

    origin: ResolverMatch
    address: str
    namespace: str
    kind: GlueOperationKind
    attribute: str | None


class GlueMiddlewareMixin:
    """
    A Django middleware that also guards each object in a Glue call (ADR 035).

    Glue runs ``process_glue_call`` once per object, before the object is
    rebuilt, on its own instance of the class: the hook must not depend on
    state Django's instance set up.
    """

    def process_glue_call(self, request: HttpRequest, glue_call: GlueCall) -> None:
        """Raise ``PermissionDenied``, ``GlueAuthorizationError`` or ``Http404`` to deny."""
        _ = request, glue_call


def _get_response_unused(request: HttpRequest) -> HttpResponse:
    _ = request
    msg = 'A Glue call hook instance does not handle requests.'
    raise RuntimeError(msg)


@cache
def glue_call_hooks() -> tuple[Callable[[HttpRequest, GlueCall], None], ...]:
    """The ``process_glue_call`` hooks of the classes in ``MIDDLEWARE``, in order."""
    hooks = []
    for path in settings.MIDDLEWARE:
        middleware_class = import_string(path)
        hook = getattr(middleware_class, 'process_glue_call', None)
        if hook is None or hook is GlueMiddlewareMixin.process_glue_call:
            continue
        try:
            middleware = middleware_class(_get_response_unused)
        except MiddlewareNotUsed:
            continue
        hooks.append(middleware.process_glue_call)
    return tuple(hooks)


@receiver(setting_changed)
def _reset_glue_call_hooks(*, setting: str, **kwargs: object) -> None:
    _ = kwargs
    if setting == 'MIDDLEWARE':
        glue_call_hooks.cache_clear()


def run_glue_call_hooks(
    context: AttributeCallRequestContext,
    resolved_origins: dict[str, ResolverMatch],
) -> None:
    """
    Run every hook for one entry, resolving its origin only when a hook is
    installed; a denial, or an origin that no longer resolves, raises
    ``GlueCallDeniedError``.
    """
    hooks = glue_call_hooks()
    if not hooks:
        return

    policy = context.target_glue_policy
    denial = GlueCallDeniedError(
        policy.name,
        kind=context.operation_kind,
        attribute=context.target_attribute_name,
    )

    if policy.origin not in resolved_origins:
        try:
            resolved_origins[policy.origin] = resolve(policy.origin)
        except Resolver404 as error:
            raise denial from error

    glue_call = GlueCall(
        origin=resolved_origins[policy.origin],
        address=policy.address,
        namespace=policy.namespace,
        kind=context.operation_kind,
        attribute=context.target_attribute_name,
    )
    for hook in hooks:
        try:
            hook(context.request, glue_call)
        except (PermissionDenied, Http404) as error:
            raise denial from error
