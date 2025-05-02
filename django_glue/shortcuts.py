from typing import Union

from django.db.models import Model
from django.db.models.query import QuerySet
from django.http import HttpRequest

from django_glue.constants import ALL_DUNDER_KEY, NONE_DUNDER_KEY
from django_glue.glue.function.glue import FunctionGlue
from django_glue.glue.glue import BaseGlue
from django_glue.glue.model_object.glue import ModelObjectGlue
from django_glue.glue.query_set.glue import QuerySetGlue
from django_glue.glue.template.glue import TemplateGlue
from django_glue.session import Session, KeepLiveSession
from django_glue.utils import encode_unique_name


def _glue_base_function(request: HttpRequest, glue: BaseGlue) -> None:

    glue_session = Session(request)
    glue_session.add_glue(glue)

    glue_keep_live_session = KeepLiveSession(request)
    glue_keep_live_session.set_unique_name(glue.unique_name)

    # Todo: Check to see if this has actually changed.
    glue_session.set_modified()


def glue_function(
        request: HttpRequest,
        unique_name: str,
        target: str,
) -> None:
    glue_function_entity = FunctionGlue(
        unique_name=encode_unique_name(request, unique_name),
        function_path=target
    )
    _glue_base_function(request, glue_function_entity)


def glue_model_object(
        request: HttpRequest,
        unique_name: str,
        model_object: Model,
        access: str = 'view',
        fields: Union[list, tuple] = (ALL_DUNDER_KEY,),
        exclude: Union[list, tuple] = (NONE_DUNDER_KEY,),
        methods: Union[list, tuple] = (NONE_DUNDER_KEY,),
) -> None:
    glue_model_object_entity = ModelObjectGlue(
        unique_name=encode_unique_name(request, unique_name),
        model_object=model_object,
        access=access,
        included_fields=fields,
        excluded_fields=exclude,
        included_methods=methods
    )

    _glue_base_function(request, glue_model_object_entity)


def glue_query_set(
        request: HttpRequest,
        unique_name: str,
        target: QuerySet,
        access: str = 'view',
        fields: Union[list, tuple] = (ALL_DUNDER_KEY,),
        exclude: Union[list, tuple] = (NONE_DUNDER_KEY,),
        methods: Union[list, tuple] = (NONE_DUNDER_KEY,),
) -> None:
    glue_query_set_entity = QuerySetGlue(
        unique_name=encode_unique_name(request, unique_name),
        query_set=target,
        access=access,
        included_fields=fields,
        excluded_fields=exclude,
        included_methods=methods
    )

    _glue_base_function(request, glue_query_set_entity)


def glue_template(
        request: HttpRequest,
        unique_name: str,
        target: str,
) -> None:

    glue_template_entity = TemplateGlue(
        unique_name=encode_unique_name(request, unique_name),
        template_name=target
    )

    _glue_base_function(request, glue_template_entity)
