import functools
from typing import Callable

from django_glue.access.access import GlueAccess
from django_glue.proxies.proxy import BaseGlueProxy


def action(access: GlueAccess) -> Callable:
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs) -> Callable:
            glue_class = type(self)

            if BaseGlueProxy not in glue_class.__mro__:
                message = f'Instance of {glue_class.__name__} must inherit from BaseGlueProxy for its methods to be declared as actions.'
                raise TypeError(message)

            return func(self, *args, **kwargs)

        wrapper._required_glue_access = access
        return wrapper

    decorator._required_glue_access = access

    return decorator
