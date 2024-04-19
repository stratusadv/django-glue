from django.contrib.contenttypes.models import ContentType
from django.db.models import Model

from django_glue.entities.model_object.entities import GlueModelObject
from django_glue.entities.model_object.sessions import GlueModelObjectSessionData


def glue_model_object_from_glue_session(glue_session: GlueModelObjectSessionData,) -> GlueModelObject:

    model_class = ContentType.objects.get_by_natural_key(
        glue_session.app_label,
        glue_session.model_name
    ).model_class()

    try:
        model_object = model_class.objects.get(pk=glue_session.object_pk)
    except model_class.DoesNotExist:
        model_object = model_class()

    return GlueModelObject(
        unique_name=glue_session.unique_name,
        model_object=model_object,
        access=glue_session.access,
        connection=glue_session.connection,
        included_fields=glue_session.included_fields,
        excluded_fields=glue_session.exclude_fields,
        included_methods=glue_session.methods,
    )


def glue_model_object_from_glue_query_set_session(model_object: Model, query_set_session_data: 'GlueQuerySetSessionData'):
    return GlueModelObject(
        unique_name=query_set_session_data.unique_name,
        access=query_set_session_data.access,
        model_object=model_object,
        connection=query_set_session_data.connection,
        included_fields=query_set_session_data.included_fields,
        excluded_fields=query_set_session_data.excluded_fields,
        included_methods=query_set_session_data.included_methods,
    )
