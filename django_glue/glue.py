from typing import Union
import urllib.parse

from django.db.models import Model
from django.db.models.query import QuerySet
from django.http import HttpRequest

from django_glue.entities.model_object.entities import GlueModelObject
from django_glue.session import GlueSession, GlueKeepLiveSession
from django_glue.utils import encode_unique_name


def glue_function(
        request: HttpRequest,
        unique_name: str,
        target: callable,
):
    glue_session = GlueSession(request)

    encoded_unique_name = encode_unique_name(request, unique_name)
    glue_session.add_function(encoded_unique_name, target)

    glue_keep_live_session = GlueKeepLiveSession(request)
    glue_keep_live_session.set_unique_name(encoded_unique_name)

    glue_session.set_modified()


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

    encoded_unique_name = encode_unique_name(request, unique_name)

    # Todo: Initialize a glue model object & pass it here.
    glue_model_object = GlueModelObject(
        model_object=target,
        access=access,
        fields=fields,
        exclude=exclude,
        methods=methods
    )

    glue_session.add_model_object(encoded_unique_name, target, access, fields, exclude, methods)

    glue_keep_live_session = GlueKeepLiveSession(request)
    glue_keep_live_session.set_unique_name(encoded_unique_name)

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

    encoded_unique_name = encode_unique_name(request, unique_name)
    glue_session.add_query_set(encoded_unique_name, target, access, fields, exclude, methods)

    glue_keep_live_session = GlueKeepLiveSession(request)
    glue_keep_live_session.set_unique_name(encoded_unique_name)

    glue_session.set_modified()


def glue_template(
        request: HttpRequest,
        unique_name: str,
        target: str,
):
    glue_session = GlueSession(request)

    encoded_unique_name = encode_unique_name(request, unique_name)
    glue_session.add_template(encoded_unique_name, target)

    glue_keep_live_session = GlueKeepLiveSession(request)
    glue_keep_live_session.set_unique_name(encoded_unique_name)

    glue_session.set_modified()
