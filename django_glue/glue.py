from typing import Union

from django.db.models import Model
from django.db.models.query import QuerySet
from django.http import HttpRequest

from django_glue.entities.base_entity import GlueEntity
from django_glue.entities.model_object.entities import GlueModelObject
from django_glue.entities.query_set.entities import GlueQuerySet
from django_glue.session import GlueSession, GlueKeepLiveSession
from django_glue.utils import encode_unique_name


def _glue_entity(request: HttpRequest, glue_entity: GlueEntity):
    glue_session = GlueSession(request)
    glue_session.add_glue_entity(glue_entity)

    glue_keep_live_session = GlueKeepLiveSession(request)
    glue_keep_live_session.set_unique_name(glue_entity.unique_name)

    glue_session.set_modified()


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
    glue_model_object = GlueModelObject(
        unique_name=encode_unique_name(request, unique_name),
        model_object=target,
        access=access,
        included_fields=fields,
        excluded_fields=exclude,
        included_methods=methods
    )

    _glue_entity(request, glue_model_object)


def glue_query_set(
        request: HttpRequest,
        unique_name: str,
        target: QuerySet,
        access: str = 'view',
        fields: Union[list, tuple] = ('__all__',),
        exclude: Union[list, tuple] = ('__none__',),
        methods: Union[list, tuple] = ('__none__',),
):
    glue_queryset = GlueQuerySet(
        unique_name=encode_unique_name(request, unique_name),
        query_set=target,
        access=access,
        included_fields=fields,
        excluded_fields=exclude,
        included_methods=methods
    )

    _glue_entity(request, glue_queryset)


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
