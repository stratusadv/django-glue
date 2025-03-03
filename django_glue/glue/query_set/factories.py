import base64
import pickle

from django.db.models import QuerySet

from django_glue.glue.query_set.glue import QuerySetGlue
from django_glue.glue.query_set.session_data import GlueQuerySetSessionData


def decode_query_set_from_str(query_set_string) -> QuerySet:
    query = pickle.loads(base64.b64decode(query_set_string))
    decoded_query_set = query.model.objects.all()
    decoded_query_set.query = query
    return decoded_query_set


def glue_query_set_from_session_data(session_data: GlueQuerySetSessionData):
    return QuerySetGlue(
        unique_name=session_data.unique_name,
        query_set=decode_query_set_from_str(session_data.query_set_str),
        access=session_data.access,
        included_fields=session_data.included_fields,
        excluded_fields=session_data.excluded_fields,
        included_methods=session_data.included_methods,
    )
