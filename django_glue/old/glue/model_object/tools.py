from typing import Type

from django.apps import apps
from django.db.models import Model, QuerySet

from django_glue.glue.model_object.glue import ModelObjectGlue
from django_glue.glue.model_object.session_data import ModelObjectGlueSessionData
from django_glue.glue.query_set.session_data import QuerySetGlueSessionData


def model_object_glue_from_session_data(session_data: ModelObjectGlueSessionData) -> ModelObjectGlue:
    model: type | Type[Model] = apps.get_model(session_data.app_label, session_data.model_name)

    try:
        model_object = model.objects.get(pk=session_data.object_pk)
    except model.DoesNotExist:
        model_object = model()

    return ModelObjectGlue(
        unique_name=session_data.unique_name,
        model_object=model_object,
        access=session_data.access,
        included_fields=session_data.included_fields,
        excluded_fields=session_data.exclude_fields,
        included_methods=session_data.methods,
    )


def model_object_glue_from_query_set_glue_session_data(
        model_object: Model,
        session_data: QuerySetGlueSessionData
):
    return ModelObjectGlue(
        unique_name=session_data.unique_name,
        access=session_data.access,
        model_object=model_object,
        included_fields=session_data.included_fields,
        excluded_fields=session_data.excluded_fields,
        included_methods=session_data.included_methods,
    )


def model_object_glues_from_query_set_glue_and_session_data(
        query_set: QuerySet,
        session_data: QuerySetGlueSessionData
) -> list[ModelObjectGlue]:

    return [model_object_glue_from_query_set_glue_session_data(
        model_object,
        session_data
    ) for model_object in query_set]
