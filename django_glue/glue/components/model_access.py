from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from django.db.models import Model  # noqa: TC002

from django_glue.access import get_model_access

if TYPE_CHECKING:
    from django.http import HttpRequest


def _get_permission_model(component: Any) -> type[Model]:
    for component_class in type(component).__mro__:
        declared = vars(component_class)

        if declared.get('permission_model') is not None:
            return declared['permission_model']

        if 'get_permission_model' in declared:
            return component.get_permission_model()

    message = (
        f'{type(component).__name__} must set permission_model or implement '
        'get_permission_model().'
    )
    raise NotImplementedError(message)


class ModelAccessMixin:
    """
    Sets a component's access from the user's permissions on its permission
    model, with ``get_model_access()``. Without the model's view permission it
    leaves the access as it was: who may open a page is decided by the page's
    own guard.

    The component names the model with a ``permission_model`` class attribute
    or a ``get_permission_model()`` method. The one declared nearest the
    component's own class wins, so a subclass overrides its base whichever way
    either names it. The mixin defines neither, so it never hides a base
    component's own.

    The access is set in ``__post_init__``, so a subclass that assigns
    ``self.access`` after calling ``super().__post_init__(request)`` overrides
    it, and the level it leaves is the one signed.
    """

    permission_model: ClassVar[type[Model] | None] = None

    def __post_init__(self, request: HttpRequest, **kwargs: Any) -> None:
        super().__post_init__(request, **kwargs)

        access = get_model_access(request.user, _get_permission_model(self))

        if access is not None:
            self.access = access
