from typing import Union

from django.db.models import Model
from django.db.models.query import QuerySet
from django.http import HttpRequest

from django_glue.entities.base_entity import GlueEntity
from django_glue.entities.function.entities import GlueFunction
from django_glue.entities.model_object.entities import GlueModelObject
from django_glue.entities.query_set.entities import GlueQuerySet
from django_glue.entities.template.entities import GlueTemplate
from django_glue.session import GlueSession, GlueKeepLiveSession
from django_glue.utils import encode_unique_name


def _glue_entity(request: HttpRequest, glue_entity: GlueEntity):
    glue_session = GlueSession(request)
    glue_session.add_glue_entity(glue_entity)

    glue_keep_live_session = GlueKeepLiveSession(request)
    glue_keep_live_session.set_unique_name(glue_entity.unique_name)

    print(glue_session.session)

    glue_session.set_modified()


def glue_function(
        request: HttpRequest,
        unique_name: str,
        target: str,
):
    glue_function_entity = GlueFunction(
        unique_name=encode_unique_name(request, unique_name),
        function_path=target
    )
    _glue_entity(request, glue_function_entity)


def glue_model(
        request: HttpRequest,
        unique_name: str,
        target: Model,
        access: str = 'view',
        fields: Union[list, tuple] = ('__all__',),
        exclude: Union[list, tuple] = ('__none__',),
        methods: Union[list, tuple] = ('__none__',),
):
    glue_model_object_entity = GlueModelObject(
        unique_name=encode_unique_name(request, unique_name),
        model_object=target,
        access=access,
        included_fields=fields,
        excluded_fields=exclude,
        included_methods=methods
    )

    _glue_entity(request, glue_model_object_entity)


def glue_query_set(
        request: HttpRequest,
        unique_name: str,
        target: QuerySet,
        access: str = 'view',
        fields: Union[list, tuple] = ('__all__',),
        exclude: Union[list, tuple] = ('__none__',),
        methods: Union[list, tuple] = ('__none__',),
):
    glue_query_set_entity = GlueQuerySet(
        unique_name=encode_unique_name(request, unique_name),
        query_set=target,
        access=access,
        included_fields=fields,
        excluded_fields=exclude,
        included_methods=methods
    )

    _glue_entity(request, glue_query_set_entity)


def glue_template(
        request: HttpRequest,
        unique_name: str,
        target: str,
):

    glue_template_entity = GlueTemplate(
        unique_name=encode_unique_name(request, unique_name),
        template_name=target
    )

    _glue_entity(request, glue_template_entity)
