import functools
from typing import Callable, TypeVar, ParamSpec

from django_glue.access.access import GlueAccess

P = ParamSpec("P")
R = TypeVar("R")


def action(access: GlueAccess) -> Callable[[Callable[P, R]], Callable[P, R]]:
    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            return func(*args, **kwargs)

        wrapper._required_glue_access = access
        return wrapper

    return decorator
