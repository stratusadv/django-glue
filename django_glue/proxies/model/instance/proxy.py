from __future__ import annotations

from typing import TYPE_CHECKING, Sequence

from django.db.models import Model
from django.forms.models import ModelForm

from django_glue.access.access import GlueAccess
from django_glue.proxies.model.proxy import BaseGlueModelProxy
from django_glue.proxies.model.instance.state import GlueModelInstanceProxyState

if TYPE_CHECKING:
    from django.http import HttpRequest


class GlueModelInstanceProxy(BaseGlueModelProxy):
    """Proxy for a single Django model instance."""

    _state_class = GlueModelInstanceProxyState

    @classmethod
    def register(
        cls,
        request: HttpRequest,
        target: Model,
        name: str,
        access: GlueAccess = GlueAccess.VIEW,
        namespace: str = 'model',
        fields: Sequence | dict = (),
        exclude: Sequence[str] = (),
        form_class: type[ModelForm] | None = None,
    ) -> None:
        state, form_class_path = cls._build_state(target, fields, exclude, form_class)
        proxy = cls(name=name, namespace=namespace, access=access, state=state)
        proxy._form_class_path = form_class_path
        proxy._register_with_request(request)
