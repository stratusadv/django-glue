import functools
from typing import Callable, TypeVar, ParamSpec

from django_glue.access.access import GlueAccess

P = ParamSpec("P")
R = TypeVar("R")


def bind_attribute(access: GlueAccess) -> Callable[[Callable[P, R]], Callable[P, R]]:
    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            return func(*args, **kwargs)

        wrapper.__required_glue_access__ = access

        return wrapper

    return decorator
