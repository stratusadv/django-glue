from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Any, get_type_hints

from django_glue.exceptions import GlueAnnotationError

if TYPE_CHECKING:
    from collections.abc import Iterable


if sys.version_info >= (3, 14):
    from annotationlib import Format, get_annotations

    def _get_own_annotations(klass: type) -> dict[str, Any]:
        """
        ``klass``'s own annotations. Python 3.14 evaluates them on demand (PEP 649), so a name
        that can't be resolved, such as one imported only under ``TYPE_CHECKING``, comes back as
        a ``ForwardRef`` rather than raising.
        """
        return get_annotations(klass, format=Format.FORWARDREF)

else:

    def _get_own_annotations(klass: type) -> dict[str, Any]:
        """``klass``'s own annotations, as the class body stored them."""
        return klass.__dict__.get('__annotations__', {})


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
    own_annotations = {klass: _get_own_annotations(klass) for klass in owner.__mro__}

    for name in names:
        declaring = next((klass for klass in owner.__mro__ if name in own_annotations[klass]), None)
        if declaring is None:
            continue

        # A stand-in class holding only this annotation, in the declaring class's module, lets
        # get_type_hints evaluate it as it would on the class itself, and nothing else.
        stand_in = type(
            declaring.__name__,
            (),
            {
                '__annotations__': {name: own_annotations[declaring][name]},
                '__module__': declaring.__module__,
            },
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
