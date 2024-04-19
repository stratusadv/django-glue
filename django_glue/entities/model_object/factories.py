from django.contrib.contenttypes.models import ContentType

from django_glue.entities.model_object.entities import GlueModelObject
from django_glue.entities.model_object.sessions import GlueModelObjectSessionData


def glue_model_object_from_glue_session(
        unique_name: str,
        glue_session: GlueModelObjectSessionData,
) -> GlueModelObject:

    model_class = ContentType.objects.get_by_natural_key(
        glue_session.app_label,
        glue_session.model_name
    ).model_class()

    try:
        model_object = model_class.objects.get(pk=glue_session.object_pk)
    except model_class.DoesNotExist:
        model_object = model_class()

    return GlueModelObject(
        unique_name=unique_name,
        model_object=model_object,
        access=glue_session.access,
        connection=glue_session.connection,
        included_fields=glue_session.included_fields,
        excluded_fields=glue_session.exclude_fields,
        included_methods=glue_session.methods,
    )
