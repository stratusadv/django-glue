from __future__ import annotations

from typing import TYPE_CHECKING, Any, get_type_hints

from django_glue.exceptions import GlueAnnotationError

if TYPE_CHECKING:
    from collections.abc import Iterable


def resolve_annotations(owner: type, names: Iterable[str]) -> dict[str, Any]:
    """
    The evaluated type annotations of ``names`` on ``owner``: each from the nearest class in its
    MRO that annotates it, evaluated as ``get_type_hints`` would, in that class's module.

    Only these names are evaluated. Every other annotation on the class, such as a ``ClassVar``
    whose type is imported only under ``TYPE_CHECKING``, is left as it is, so it can't stop the
    class from being defined. A name with no annotation is left out of the result. One that can't
    be evaluated raises ``GlueAnnotationError``, naming it.
    """
    resolved: dict[str, Any] = {}

    for name in names:
        declaring = next(
            (klass for klass in owner.__mro__ if name in klass.__dict__.get('__annotations__', {})),
            None,
        )
        if declaring is None:
            continue

        # A stand-in class holding only this annotation, in the declaring class's module, lets
        # get_type_hints evaluate it as it would on the class itself, and nothing else.
        stand_in = type(
            declaring.__name__,
            (),
            {'__annotations__': {name: declaring.__dict__['__annotations__'][name]}, '__module__': declaring.__module__},
        )
        try:
            resolved[name] = get_type_hints(stand_in, localns=dict(vars(declaring)))[name]
        except (NameError, TypeError) as error:
            message = (
                f"{owner.__qualname__}.{name}'s annotation (on {declaring.__qualname__}) can't be "
                f'resolved: {error}. Import what it names at runtime, not only under TYPE_CHECKING.'
            )
            raise GlueAnnotationError(message) from error

    return resolved
