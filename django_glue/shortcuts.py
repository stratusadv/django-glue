import json
from typing import Any

from django.http import HttpRequest
from django.urls import path, include

from django_glue.access.access import GlueAccess
from django_glue.session import GlueSession
from django_glue import constants
from django_glue.adapters.base import BaseGlueAdapter


def glue(
    request: HttpRequest,
    unique_name: str,
    target: Any,
    access: GlueAccess = GlueAccess.VIEW,
    **kwargs
):
    glue_class = [
        glue_subclass for glue_subclass in BaseGlueAdapter.__subclasses__()
        if (
                isinstance(target, glue_subclass.target_class) or
                target.__class__ == glue_subclass.target_class
        )
    ][0]

    glue_obj = glue_class(
        target=target,
        unique_name=unique_name,
        access=access,
        **kwargs
    )

    GlueSession(request).register_adapter_instance(glue_obj)

    if not hasattr(request, '__glue_context_data__'):
        request.__glue_context_data__ = {}

    request.__glue_context_data__[glue_obj.unique_name] = glue_obj.to_context_data()


def django_glue_urls():
    return [
        path(f'{constants.BASE_URL_NAME}/', include('django_glue.urls', namespace=constants.BASE_URL_NAME))
    ]