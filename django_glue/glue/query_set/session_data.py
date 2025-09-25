import base64
import pickle
from dataclasses import dataclass
from typing import Union, TYPE_CHECKING

from django.db.models import Model, QuerySet

from django_glue.glue.model_object.glue import ModelObjectGlue
from django_glue.session.data import SessionData

if TYPE_CHECKING:
    from django_glue.glue.query_set.glue import QuerySetGlue

@dataclass
class QuerySetGlueSessionData(SessionData):
    query_set_str: str
    fields: dict # Why isn't this list[ModelFieldGlue]? Or ModelFieldsGlue?
    included_fields: Union[list, tuple]
    excluded_fields: Union[list, tuple]
    included_methods: Union[list, tuple]

    def to_queryset_glue(self):
        from django_glue.glue.query_set.glue import QuerySetGlue

        query = pickle.loads(base64.b64decode(self.query_set_str))
        decoded_query_set = query.model.objects.all()
        decoded_query_set.query = query

        return QuerySetGlue(
            query_set=decoded_query_set,
            **self.to_dict()
        )

    def extract_model_object_glue_matching_model_object(self, model_object: Model) -> ModelObjectGlue:
        return ModelObjectGlue(
            model_object=model_object,
            **self.to_dict()
        )

    def extract_model_object_glues_matching_queryset(self, query_set: QuerySet) -> list[ModelObjectGlue]:
        return [
            self.extract_model_object_glue_matching_model_object(model_object)
            for model_object in query_set
        ]