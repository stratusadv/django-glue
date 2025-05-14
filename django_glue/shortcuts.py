from __future__ import annotations

from typing import Any, Callable, TYPE_CHECKING

from django_glue.access.access import Access
from django_glue.constants import ALL_DUNDER_KEY, NONE_DUNDER_KEY
from django_glue.glue.context.glue import ContextGlue
from django_glue.glue.context.permissions import create_permission_checker
from django_glue.glue.function.glue import FunctionGlue
from django_glue.glue.model_object.glue import ModelObjectGlue
from django_glue.glue.query_set.glue import QuerySetGlue
from django_glue.glue.template.glue import TemplateGlue
from django_glue.session import Session, KeepLiveSession
from django_glue.utils import encode_unique_name

if TYPE_CHECKING:
    from django.db.models import Model
    from django.db.models.query import QuerySet
    from django.http import HttpRequest

    from django_glue.glue.glue import BaseGlue


def _glue_base_function(request: HttpRequest, glue: BaseGlue) -> None:
    glue_session = Session(request)
    glue_session.add_glue(glue)

    glue_keep_live_session = KeepLiveSession(request)
    glue_keep_live_session.set_unique_name(glue.unique_name)

    # Todo: Check to see if this has actually changed.
    glue_session.set_modified()


def glue_context(
    request: HttpRequest,
    unique_name: str,
    context_data: dict[str, Any],
    access: Access | str = Access.VIEW,
    exclude: list[str] | set[str] | tuple | None = None,
    permission_checker: Callable | None = None
) -> None:
    user = request.user

    if permission_checker is None and user.is_authenticated:
        permission_checker = create_permission_checker(user)

    context_glue = ContextGlue(
        unique_name=encode_unique_name(request, unique_name),
        context_data=context_data,
        user=user,
        permission_checker=permission_checker,
        access=access,
        exclude=exclude
    )

    _glue_base_function(request, context_glue)


def glue_function(
    request: HttpRequest,
    unique_name: str,
    target: str
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
    fields: list | tuple = (ALL_DUNDER_KEY,),
    exclude: list | tuple = (NONE_DUNDER_KEY,),
    methods: list | tuple = (NONE_DUNDER_KEY,),
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
    fields: list | tuple = (ALL_DUNDER_KEY,),
    exclude: list | tuple = (NONE_DUNDER_KEY,),
    methods: list | tuple = (NONE_DUNDER_KEY,),
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
