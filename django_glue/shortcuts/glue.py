from typing import Any, Sequence

from django.db.models import Model, QuerySet
from django.forms import ModelForm, BaseForm
from django.http import HttpRequest

from django_glue.access.access import GlueAccess
from django_glue.proxies import (
    BaseGlueProxy,
    GlueFormProxy,
    GlueFunctionProxy,
    GlueModelFormProxy,
    GlueModelProxy,
    GlueQuerySetProxy,
    GlueTemplateProxy,
)
from django_glue.session import GlueSession
from django_glue.proxies.decorators import action


class Glue:
    Access = GlueAccess
    action = staticmethod(action)

    @staticmethod
    def glue(
        request: HttpRequest,
        unique_name: str,
        target: Any,
        proxy_class: type[BaseGlueProxy],
        access: GlueAccess = GlueAccess.VIEW,
        **kwargs,
    ) -> None:
        proxy_instance = proxy_class(
            target=target, unique_name=unique_name, access=access, **kwargs
        )

        GlueSession(request).register_proxy(proxy_instance)

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
        # If it's a ModelForm, use GlueModelFormProxy
        if isinstance(target, ModelForm):
            Glue.glue(
                request=request,
                unique_name=unique_name,
                target=target,
                proxy_class=GlueModelFormProxy,
                access=access,
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

    @staticmethod
    def template(
        request: HttpRequest,
        unique_name: str,
        target: str,
        context_data: dict | None = None,
        **kwargs,
    ) -> None:
        Glue.glue(
            request=request,
            unique_name=unique_name,
            target=target,
            proxy_class=GlueTemplateProxy,
            access=GlueAccess.VIEW,
            context_data=context_data or {},
            **kwargs,
        )

    @staticmethod
    def function(
        request: HttpRequest,
        unique_name: str,
        target: str,
        **kwargs,
    ) -> None:
        Glue.glue(
            request=request,
            unique_name=unique_name,
            target=target,
            proxy_class=GlueFunctionProxy,
            access=GlueAccess.VIEW,
            **kwargs,
        )
