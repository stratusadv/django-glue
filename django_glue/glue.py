from typing import Union

from django.db.models import Model
from django.db.models.query import QuerySet
from django.http import HttpRequest

from django_glue.sessions import GlueSession, GlueKeepLiveSession


def glue_model(
        request: HttpRequest,
        unique_name: str,
        target: Model,
        access: str = 'view',
        fields: Union[list, tuple] = ('__all__',),
        exclude: Union[list, tuple] = ('__none__',),
        methods: Union[list, tuple] = ('__none__',),
):
    glue_session = GlueSession(request)
    glue_session.add_model_object(unique_name, target, access, fields, exclude, methods)

    glue_keep_live_session = GlueKeepLiveSession(request)
    glue_keep_live_session.set_unique_name(unique_name)

    glue_session.set_modified()


def glue_query_set(
        request: HttpRequest,
        unique_name: str,
        target: QuerySet,
        access: str = 'view',
        fields: Union[list, tuple] = ('__all__',),
        exclude: Union[list, tuple] = ('__none__',),
        methods: Union[list, tuple] = ('__none__',),
):
    glue_session = GlueSession(request)
    glue_session.add_query_set(unique_name, target, access, fields, exclude, methods)

    glue_keep_live_session = GlueKeepLiveSession(request)
    glue_keep_live_session.set_unique_name(unique_name)

    glue_session.set_modified()


def glue_template(
        request: HttpRequest,
        unique_name: str,
        target: str,
):
    glue_session = GlueSession(request)
    glue_session.add_template(unique_name, target)

    glue_keep_live_session = GlueKeepLiveSession(request)
    glue_keep_live_session.set_unique_name(unique_name)

    glue_session.set_modified()
