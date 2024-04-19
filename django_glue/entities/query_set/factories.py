import base64
import pickle

from django.db.models import QuerySet


def decode_query_set_from_str(query_set_string) -> QuerySet:
    query = pickle.loads(base64.b64decode(query_set_string))
    decoded_query_set = query.model.objects.all()
    decoded_query_set.query = query
    return decoded_query_set
