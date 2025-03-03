from typing import Union

from django.db.models import Model
from django.db.models.query import QuerySet
from django.http import HttpRequest

from django_glue.glue.glue import BaseGlue
from django_glue.glue.function.glue import FunctionGlue
from django_glue.glue.model_object.glue import ModelObjectGlue
from django_glue.glue.query_set.glue import QuerySetGlue
from django_glue.glue.template.glue import TemplateGlue
from django_glue.session import GlueSession, GlueKeepLiveSession
from django_glue.utils import encode_unique_name


def _glue_entity(request: HttpRequest, glue_entity: BaseGlue):
    glue_session = GlueSession(request)
    glue_session.add_glue_entity(glue_entity)

    glue_keep_live_session = GlueKeepLiveSession(request)
    glue_keep_live_session.set_unique_name(glue_entity.unique_name)

    # Todo: Check to see if this has actually changed.
    glue_session.set_modified()


def glue_function(
        request: HttpRequest,
        unique_name: str,
        target: str,
):
    glue_function_entity = FunctionGlue(
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
    glue_model_object_entity = ModelObjectGlue(
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
    glue_query_set_entity = QuerySetGlue(
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

    glue_template_entity = TemplateGlue(
        unique_name=encode_unique_name(request, unique_name),
        template_name=target
    )

    _glue_entity(request, glue_template_entity)
