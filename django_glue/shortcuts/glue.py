from typing import Sequence

from django.db.models import Model, QuerySet
from django.forms import ModelForm, BaseForm
from django.http import HttpRequest

from django_glue.access.access import GlueAccess
from django_glue.actions.action import register_target_actions
from django_glue.actions.decorators import action, action_provider


class Glue:
    Access = GlueAccess
    action = staticmethod(action)
    action_provider = staticmethod(action_provider)

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

        proxy = GlueModelInstanceProxy(
            name=unique_name,
            access=access,
            model_instance=target,
            fields=fields,
            exclude=exclude,
            form_class=form_class,
        )

        for t in [
            proxy,
            target
        ]:
            register_target_actions(t)

            proxy.register_with_request(request)

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

        proxy = GlueQuerySetProxy(
            name=unique_name,
            access=access,
            queryset=target,
            fields=fields,
            exclude=exclude,
            form_class=form_class,
        )

        for t in [
            proxy,
            target
        ]:
            register_target_actions(t)

        proxy.register_with_request(request)

    @staticmethod
    def form(
        request: HttpRequest,
        unique_name: str,
        target: BaseForm,
        access: GlueAccess = GlueAccess.VIEW,
    ) -> None:
        from django_glue.proxies.form.proxy import GlueFormProxy

        proxy = GlueFormProxy(
            name=unique_name,
            access=access,
            form_instance=target,
        )

        for t in [
            proxy.register_with_request(request),
            target
        ]:
            register_target_actions(t)

        proxy.register_with_request(request)

    @staticmethod
    def template(
        request: HttpRequest,
        unique_name: str,
        target: str,
        initial_context_data: dict | None = None,
    ) -> None:
        from django_glue.proxies.template.proxy import GlueTemplateProxy

        proxy = GlueTemplateProxy(
            request=request,
            name=unique_name,
            template_path=target,
            proxy_class=GlueTemplateProxy,
            access=GlueAccess.VIEW,
            initial_context_data=initial_context_data or {},
        )

        for t in [
            proxy,
            target
        ]:
            register_target_actions(t)

        proxy.register_with_request(request)

    @staticmethod
    def function(
        request: HttpRequest,
        unique_name: str,
        target: str,
        **kwargs,
    ) -> None:
        from django_glue.proxies.function.proxy import GlueFunctionProxy

        proxy = GlueFunctionProxy(
            request=request,
            name=unique_name,
            function_path=target,
            access=GlueAccess.VIEW,
            **kwargs,
        )

        for t in [
            proxy,
            target
        ]:
            register_target_actions(t)

        proxy.register_with_request(request)
