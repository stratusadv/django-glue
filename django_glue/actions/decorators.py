import functools
from typing import Callable, TypeVar, ParamSpec

from django_glue.access.access import GlueAccess
from django_glue.utils import AppendOnlyDict

P = ParamSpec("P")
R = TypeVar("R")

GLUE_ACTIONS = AppendOnlyDict()


def action(access: GlueAccess) -> Callable[[Callable[P, R]], Callable[P, R]]:
    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            return func(*args, **kwargs)

        wrapper.__required_glue_access__ = access

        return wrapper

    return decorator


def action_provider(
        target_class: type | None = None,
        access_path: str = '',
        provider_factory: Callable | None = None,
    ) -> Callable[..., Callable[..., type]]:
    def decorated_class(cls: type) -> type:
        _target_class = cls
        if target_class is None:
            _target_class = cls

        from django_glue.actions.action import register_action_provider

        register_action_provider(
            action_provider_class=cls,
            target_class=_target_class,
            client_proxy_access_path=access_path,
            provider_factory=provider_factory
        )

    return decorated_class
