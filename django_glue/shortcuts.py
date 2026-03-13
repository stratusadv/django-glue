from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from django.db.models import QuerySet, Model
from django.forms.forms import BaseForm
from django.forms.models import ModelForm
from django.http import HttpRequest
from django.urls import path, include

from django_glue.access.access import GlueAccess
from django_glue.proxies import GlueModelProxy, GlueQuerySetProxy, GlueFormProxy
from django_glue.session import GlueSession
from django_glue import constants
from django_glue.proxies.proxy import BaseGlueProxy


@dataclass
class ForeignKeyField:
    """Helper for customizing ForeignKey field querysets in Glue proxies."""
    name: str
    queryset: QuerySet


class Glue:
    ForeignKeyField = ForeignKeyField
    Access = GlueAccess

    @staticmethod
    def request(request):
        return GluedRequest(request)

    @staticmethod
    def glue(
        request: HttpRequest,
        unique_name: str,
        target: Any,
        proxy_class: type[BaseGlueProxy],
        access: GlueAccess = GlueAccess.VIEW,
        **kwargs
    ):
        proxy = proxy_class(
            target=target,
            unique_name=unique_name,
            access=access,
            **kwargs
        )

        GlueSession(request).register_proxy(proxy)

        if not hasattr(request, '__glue_context_data__'):
            request.__glue_context_data__ = {}

        request.__glue_context_data__[proxy.unique_name] = proxy.to_context_data()

        return

    @staticmethod
    def model(
        request: HttpRequest,
        unique_name: str,
        target: Model,
        access: GlueAccess = GlueAccess.VIEW,
        fields: Sequence = (),
        exclude: Sequence[str] = (),
        form_class: type[ModelForm] = None,
        **kwargs
    ):
        Glue.glue(
            request=request,
            unique_name=unique_name,
            target=target,
            proxy_class=GlueModelProxy,
            access=access,
            fields=fields,
            exclude=exclude,
            form_class=form_class,
            **kwargs
        )

    @staticmethod
    def queryset(
        request: HttpRequest,
        unique_name: str,
        target: QuerySet,
        access: GlueAccess = GlueAccess.VIEW,
        fields: Sequence = (),
        exclude: Sequence[str] = (),
        form_class: type[ModelForm] = None,
        **kwargs
    ):
        Glue.glue(
            request=request,
            unique_name=unique_name,
            target=target,
            proxy_class=GlueQuerySetProxy,
            access=access,
            fields=fields,
            exclude=exclude,
            form_class=form_class,
            **kwargs
        )

    @staticmethod
    def form(
        request: HttpRequest,
        unique_name: str,
        target: BaseForm,
        access: GlueAccess = GlueAccess.VIEW,
        **kwargs
    ):
        # If it's a ModelForm, create a model proxy with the form's instance
        if isinstance(target, ModelForm):
            instance = target.instance if target.instance.pk else target._meta.model()
            Glue.glue(
                request=request,
                unique_name=unique_name,
                target=instance,
                proxy_class=GlueModelProxy,
                access=access,
                form_class=target.__class__,
                **kwargs
            )
        else:
            Glue.glue(
                request=request,
                unique_name=unique_name,
                target=target,
                proxy_class=GlueFormProxy,
                access=access,
                **kwargs
            )


class GluedRequest:
    def __init__(self, request):
        self.request = request

    def model(
        self,
        unique_name: str,
        target: Model,
        access: GlueAccess = GlueAccess.VIEW,
        fields: Sequence = (),
        exclude: Sequence[str] = (),
        form_class: type[ModelForm] = None,
        **kwargs
    ):
        Glue.model(
            request=self.request,
            unique_name=unique_name,
            target=target,
            access=access,
            fields=fields,
            exclude=exclude,
            form_class=form_class,
            **kwargs
        )

    def queryset(
        self,
        unique_name: str,
        target: QuerySet,
        access: GlueAccess = GlueAccess.VIEW,
        fields: Sequence = (),
        exclude: Sequence[str] = (),
        form_class: type[ModelForm] = None,
        **kwargs
    ):
        Glue.queryset(
            request=self.request,
            unique_name=unique_name,
            target=target,
            access=access,
            fields=fields,
            exclude=exclude,
            form_class=form_class,
            **kwargs
        )

    def form(
        self,
        unique_name: str,
        target: BaseForm,
        access: GlueAccess = GlueAccess.VIEW,
        **kwargs
    ):
        Glue.form(
            request=self.request,
            unique_name=unique_name,
            target=target,
            access=access,
            **kwargs
        )


def django_glue_urls():
    return [
        path(f'{constants.BASE_URL_NAME}/', include('django_glue.urls', namespace=constants.BASE_URL_NAME))
    ]