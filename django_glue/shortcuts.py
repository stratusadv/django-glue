import inspect
from abc import ABC
from typing import Any

from django.http import HttpRequest
from django.urls import path, include
from django.utils.module_loading import import_string

from django_glue.access.access import GlueAccess
from django_glue.conf import settings
from django_glue.session import GlueSession
from django_glue import constants
from django_glue.proxies.proxy import BaseGlueProxy
from django_glue.utils import get_inheritors


def glue(
    request: HttpRequest,
    unique_name: str,
    target: Any,
    access: GlueAccess = GlueAccess.VIEW,
    **kwargs
):
    type_names = [
        proxy_subclass.subject_type.__name__
        for proxy_subclass in get_inheritors(BaseGlueProxy)
        if not inspect.isabstract(proxy_subclass)
    ]

    for subject_type_name in type_names:
        if (
            subject_type_name in settings.DJANGO_GLUE_TYPE_CONFIG.keys() and
            subject_type_name in [
                inherited_class.__name__ for inherited_class in target.__class__.__mro__
            ]
        ):
            proxy_class = import_string(
                settings.DJANGO_GLUE_TYPE_CONFIG[subject_type_name]['proxy_classes']['server']
            )

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

    # TODO: error handling


def django_glue_urls():
    return [
        path(f'{constants.BASE_URL_NAME}/', include('django_glue.urls', namespace=constants.BASE_URL_NAME))
    ]