import functools
from typing import Callable, TypeVar, ParamSpec

from django_glue.access.access import GlueAccess
from django_glue.proxies.proxy import BaseGlueProxy

P = ParamSpec("P")
R = TypeVar("R")


def action(access: GlueAccess) -> Callable[[Callable[P, R]], Callable[P, R]]:
    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            glue_class = type(args[0])

            if BaseGlueProxy not in glue_class.__mro__:
                message = f'Instance of {glue_class.__name__} must inherit from BaseGlueProxy for its methods to be declared as actions.'
                raise TypeError(message)

            return func(*args, **kwargs)

        wrapper._required_glue_access = access
        return wrapper

    return decorator
