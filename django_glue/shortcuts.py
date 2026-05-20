from typing import Any, Sequence

from django.db.models import Model, QuerySet
from django.forms import ModelForm, BaseForm
from django.http import HttpRequest
from django.urls import include, path

from django_glue import constants
from django_glue.access.access import GlueAccess
from django_glue.proxies import BaseGlueProxy, GlueModelProxy, GlueQuerySetProxy, GlueFormProxy
# from django_glue.request import GlueRequest
from django_glue.session import GlueSession


def django_glue_urls() -> list:
    return [
        path(
            f'{constants.BASE_URL_NAME}/',
            include('django_glue.urls', namespace=constants.BASE_URL_NAME),
        )
    ]


class Glue:
    Access = GlueAccess

    # @staticmethod
    # def request(request: HttpRequest) -> GlueRequest:
    #     return GlueRequest(request)

    @staticmethod
    def glue(
        request: HttpRequest,
        unique_name: str,
        target: Any,
        proxy_class: type[BaseGlueProxy],
        access: GlueAccess = GlueAccess.VIEW,
        **kwargs,
    ) -> None:
        proxy_instance = proxy_class(target=target, unique_name=unique_name, access=access, **kwargs)

        GlueSession(request).register_proxy(proxy_instance)

        if not hasattr(request, '__glue_context_data__'):
            request.__glue_context_data__ = {}

        request.__glue_context_data__[proxy_instance.unique_name] = proxy_instance.to_context_data()

    @staticmethod
    def model(
        request: HttpRequest,
        unique_name: str,
        target: Model,
        access: GlueAccess = GlueAccess.VIEW,
        fields: Sequence = (),
        exclude: Sequence[str] = (),
        form_class: type[ModelForm] | None = None,
        **kwargs,
    ) -> None:
        Glue.glue(
            request=request,
            unique_name=unique_name,
            target=target,
            proxy_class=GlueModelProxy,
            access=access,
            fields=fields,
            exclude=exclude,
            form_class=form_class,
            **kwargs,
        )

    @staticmethod
    def queryset(
        request: HttpRequest,
        unique_name: str,
        target: QuerySet,
        access: GlueAccess = GlueAccess.VIEW,
        fields: Sequence = (),
        exclude: Sequence[str] = (),
        form_class: type[ModelForm] | None = None,
        **kwargs,
    ) -> None:
        Glue.glue(
            request=request,
            unique_name=unique_name,
            target=target,
            proxy_class=GlueQuerySetProxy,
            access=access,
            fields=fields,
            exclude=exclude,
            form_class=form_class,
            **kwargs,
        )

    @staticmethod
    def form(
        request: HttpRequest,
        unique_name: str,
        target: BaseForm,
        access: GlueAccess = GlueAccess.VIEW,
        **kwargs,
    ) -> None:
        # If it's a ModelForm, create a model proxy with the form's instance
        if isinstance(target, ModelForm):
            instance = target.instance if target.instance.pk is not None else target._meta.model()
            Glue.glue(
                request=request,
                unique_name=unique_name,
                target=instance,
                proxy_class=GlueModelProxy,
                access=access,
                form_class=target.__class__,
                **kwargs,
            )
        else:
            Glue.glue(
                request=request,
                unique_name=unique_name,
                target=target,
                proxy_class=GlueFormProxy,
                access=access,
                **kwargs,
            )
