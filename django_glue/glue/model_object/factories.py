from django.apps import apps
from django.db.models import Model, QuerySet

from django_glue.glue.model_object.glue import ModelObjectGlue
from django_glue.glue.model_object.session_data import GlueModelObjectSessionData
from django_glue.glue.query_set.session_data import GlueQuerySetSessionData


def glue_model_object_from_glue_session(glue_session: GlueModelObjectSessionData) -> ModelObjectGlue:
    model = apps.get_model(glue_session.app_label, glue_session.model_name)

    try:
        model_object = model.objects.get(pk=glue_session.object_pk)
    except model.DoesNotExist:
        model_object = model()

    return ModelObjectGlue(
        unique_name=glue_session.unique_name,
        model_object=model_object,
        access=glue_session.access,
        included_fields=glue_session.included_fields,
        excluded_fields=glue_session.exclude_fields,
        included_methods=glue_session.methods,
    )


def glue_model_object_from_glue_query_set_session(
        model_object: Model,
        query_set_session_data: GlueQuerySetSessionData
):
    return ModelObjectGlue(
        unique_name=query_set_session_data.unique_name,
        access=query_set_session_data.access,
        model_object=model_object,
        included_fields=query_set_session_data.included_fields,
        excluded_fields=query_set_session_data.excluded_fields,
        included_methods=query_set_session_data.included_methods,
    )


def glue_model_objects_from_query_set(
        query_set: QuerySet,
        query_set_session_data: GlueQuerySetSessionData
) -> list[ModelObjectGlue]:

    return [glue_model_object_from_glue_query_set_session(
        model_object,
        query_set_session_data
    ) for model_object in query_set]
