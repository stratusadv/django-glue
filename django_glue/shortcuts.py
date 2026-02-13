from typing import Any

from django.http import HttpRequest
from django.urls import path, include

from django_glue.access.access import GlueAccess
from django_glue.session import GlueSession
from django_glue import constants
from django_glue.proxies.proxy import BaseGlueProxy


def glue(
    request: HttpRequest,
    unique_name: str,
    target: Any,
    access: GlueAccess = GlueAccess.VIEW,
    **kwargs
):
    proxy_class = [
        proxy_subclass for proxy_subclass in BaseGlueProxy.__subclasses__()
        if (
                isinstance(target, proxy_subclass.subject_type) or
                target.__class__ == proxy_subclass.subject_type
        )
    ][0]

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


def django_glue_urls():
    return [
        path(f'{constants.BASE_URL_NAME}/', include('django_glue.urls', namespace=constants.BASE_URL_NAME))
    ]