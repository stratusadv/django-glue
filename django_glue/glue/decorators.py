import functools

from django_glue.access.access import GlueAccess
from django_glue.glue.base import BaseGlue


def action(access: GlueAccess):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            glue_class = type(self)

            if BaseGlue not in glue_class.__mro__:
                raise TypeError(
                    f"Instance of {glue_class.__name__} must inherit from BaseGlue for its methods to be declared as actions.")

            return func(self, *args, **kwargs)

        wrapper._required_glue_access = access
        return wrapper

    decorator._required_glue_access = access

    return decorator