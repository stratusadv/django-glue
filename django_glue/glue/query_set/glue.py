import base64
import pickle
from typing import Union

from django.db.models import QuerySet

from django_glue.access.access import Access
from django_glue.glue.glue import BaseGlue
from django_glue.glue.model_object.fields.tools import model_object_fields_glue_from_model
from django_glue.glue.query_set.session_data import QuerySetGlueSessionData
from django_glue.handler.enums import Connection


class QuerySetGlue(BaseGlue):
    def __init__(
            self,
            unique_name: str,
            query_set: QuerySet,
            access: Union[Access, str] = Access.VIEW,
            included_fields: tuple = ('__all__',),
            excluded_fields: tuple = ('__none__',),
            included_methods: tuple = ('__none__',),
    ):
        super().__init__(unique_name, Connection.QUERY_SET, access)

        self.query_set = query_set
        self.model = query_set.model

        self.included_fields = included_fields
        self.excluded_fields = excluded_fields
        self.included_methods = included_methods

    def encode_query_set(self) -> str:
        return base64.b64encode(pickle.dumps(self.query_set.query)).decode()

    def to_session_data(self) -> QuerySetGlueSessionData:
        return QuerySetGlueSessionData(
            unique_name=self.unique_name,
            query_set_str=self.encode_query_set(),
            connection=self.connection,
            fields=model_object_fields_glue_from_model(self.model, self.included_fields, self.excluded_fields).to_dict(),
            access=self.access,
            included_fields=self.included_fields,
            excluded_fields=self.excluded_fields,
            included_methods=self.included_methods,
        )
