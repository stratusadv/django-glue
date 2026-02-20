from typing import Any

from django.http import HttpRequest
from django.urls import path, include

from django_glue.access.access import GlueAccess
from django_glue.proxies import GlueModelProxy, GlueQuerySetProxy
from django_glue.session import GlueSession
from django_glue import constants
from django_glue.proxies.proxy import BaseGlueProxy


class Glue:
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
        target: Any,
        access: GlueAccess = GlueAccess.VIEW,
        **kwargs
    ):
        Glue.glue(
            request=request,
            unique_name=unique_name,
            target=target,
            proxy_class=GlueModelProxy,
            access=access,
            **kwargs
        )

    @staticmethod
    def queryset(
        request: HttpRequest,
        unique_name: str,
        target: Any,
        access: GlueAccess = GlueAccess.VIEW,
        **kwargs
    ):
        Glue.glue(
            request=request,
            unique_name=unique_name,
            target=target,
            proxy_class=GlueQuerySetProxy,
            access=access,
            **kwargs
        )


def django_glue_urls():
    return [
        path(f'{constants.BASE_URL_NAME}/', include('django_glue.urls', namespace=constants.BASE_URL_NAME))
    ]