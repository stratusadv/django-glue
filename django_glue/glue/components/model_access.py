from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.core.exceptions import PermissionDenied

from django_glue.access import get_model_access

if TYPE_CHECKING:
    from django.db.models import Model
    from django.http import HttpRequest


class ModelAccessMixin:
    """
    Sets a component's access from the user's permissions on the model
    ``get_access_model()`` returns, with ``get_model_access()``, and refuses a
    user without the model's view permission.

    The access is set in ``__post_init__``, so a subclass that assigns
    ``self.access`` after calling ``super().__post_init__(request)`` overrides
    it, and the level it leaves is the one signed.
    """

    def get_access_model(self) -> type[Model]:
        """Return the model whose permissions decide this component's access."""
        message = f'{type(self).__name__} must implement get_access_model().'
        raise NotImplementedError(message)

    def __post_init__(self, request: HttpRequest, **kwargs: Any) -> None:
        super().__post_init__(request, **kwargs)

        access = get_model_access(request.user, self.get_access_model())

        if access is None:
            raise PermissionDenied

        self.access = access
