from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from django.db.models import Model  # noqa: TC002

from django_glue.access import GlueAccess, get_model_access

if TYPE_CHECKING:
    from django.http import HttpRequest, HttpResponse

    from django_glue.glue.operation import GlueOperation


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
    own guard, such as :class:`ModelAccessRequiredMixin`.

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


class ModelAccessRequiredMixin(ModelAccessMixin):
    """
    A :class:`ModelAccessMixin` that also turns away a user whose permissions
    on the permission model do not reach ``get_required_access()``, ``VIEW``
    by default. Glue asks ``is_authorized()`` when the component first
    appears and on every later call, so the one rule guards both.

    A user turned away from a page that ``as_view()`` serves is redirected to
    log in, as Django's ``permission_required`` decorator does. A refused call
    is a 403.

    The mixin does not define ``get_required_access()``, for the reason it
    does not define ``get_permission_model()``: listed before the component
    class, its method would hide the one a base component supplies, such as a
    form component's ``ADD`` or ``CHANGE``.

    A subclass that grants more than the user's permissions, such as to the
    owner of a row, overrides ``is_authorized()`` as well as the access it
    assigns, or mixes in :class:`ModelAccessMixin` instead.
    """

    def is_authorized(self, request: HttpRequest, operation: GlueOperation) -> bool | HttpResponse:
        _ = operation
        access = get_model_access(request.user, _get_permission_model(self))
        get_required_access = getattr(self, 'get_required_access', None)
        required_access = GlueAccess.VIEW if get_required_access is None else get_required_access()

        if access is not None and access.has_access(required_access):
            return True

        # Imported here: auth's views load its models, which glue is imported before.
        from django.contrib.auth.views import redirect_to_login  # noqa: PLC0415

        return redirect_to_login(request.get_full_path())
