from typing import Sequence

from django.db.models import Model, QuerySet
from django.forms import ModelForm, BaseForm
from django.http import HttpRequest

from django_glue.access.access import GlueAccess
from django_glue.bound_attributes.decorators import Attribute
from django_glue.response import GlueRedirectResponse, GlueResponse


class Glue:
    Access = GlueAccess
    attribute = Attribute
    Response = GlueResponse
    RedirectResponse = GlueRedirectResponse

    @staticmethod
    def model(
        request: HttpRequest,
        unique_name: str,
        target: Model,
        access: GlueAccess = GlueAccess.VIEW,
        fields: Sequence = (),
        exclude: Sequence[str] = (),
        form_class: type[ModelForm] | None = None,
    ) -> None:
        from django_glue.proxies.model.instance.proxy import GlueModelInstanceProxy

        GlueModelInstanceProxy.register(
            request=request,
            target=target,
            name=unique_name,
            access=access,
            fields=fields,
            exclude=exclude,
            form_class=form_class,
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
    ) -> None:
        from django_glue.proxies.queryset.proxy import GlueQuerySetProxy

        GlueQuerySetProxy.register(
            request=request,
            target=target,
            name=unique_name,
            access=access,
            fields=fields,
            exclude=exclude,
            form_class=form_class,
        )

    @staticmethod
    def form(
        request: HttpRequest,
        unique_name: str,
        target: BaseForm,
        access: GlueAccess = GlueAccess.VIEW,
    ) -> None:
        from django_glue.proxies.form.proxy import GlueFormProxy

        GlueFormProxy.register(
            request=request,
            target=target,
            name=unique_name,
            access=access,
        )

    @staticmethod
    def template(
        request: HttpRequest,
        unique_name: str,
        target: str,
        initial_context_data: dict | None = None,
    ) -> None:
        from django_glue.proxies.template.proxy import GlueTemplateProxy

        GlueTemplateProxy.register_policy(
            request=request,
            target=target,
            name=unique_name,
            initial_context_data=initial_context_data,
        )

    @staticmethod
    def function(
        request: HttpRequest,
        unique_name: str,
        target: str,
        **kwargs,
    ) -> None:
        from django_glue.proxies.function.proxy import GlueFunctionProxy

        GlueFunctionProxy.register_policy(
            request=request,
            target=target,
            name=unique_name,
        )
