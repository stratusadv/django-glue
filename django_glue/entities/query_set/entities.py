import base64
import pickle
from typing import Union

from django.db.models import QuerySet

from django_glue.access.access import GlueAccess
from django_glue.entities.base_entity import GlueEntity
from django_glue.entities.model_object.entities import GlueModelObject
from django_glue.entities.model_object.fields import model_object_fields_from_model
from django_glue.entities.query_set.response_data import GlueQuerySetJsonData
from django_glue.entities.query_set.session_data import GlueQuerySetSessionData
from django_glue.handler.enums import GlueConnection


class GlueQuerySet(GlueEntity):
    def __init__(
            self,
            unique_name: str,
            query_set: QuerySet,
            access: Union[GlueAccess, str] = GlueAccess.VIEW,
            included_fields: tuple = ('__all__',),
            excluded_fields: tuple = ('__none__',),
            included_methods: tuple = ('__none__',),
    ):
        super().__init__(unique_name, GlueConnection.QUERY_SET, access)

        self.query_set = query_set
        self.model = query_set.model

        self.included_fields = included_fields
        self.excluded_fields = excluded_fields
        self.included_methods = included_methods

    def encode_query_set(self):
        return base64.b64encode(pickle.dumps(self.query_set.query)).decode()

    def to_session_data(self) -> GlueQuerySetSessionData:
        return GlueQuerySetSessionData(
            unique_name=self.unique_name,
            query_set_str=self.encode_query_set(),
            connection=self.connection,
            fields=model_object_fields_from_model(self.model, self.included_fields, self.excluded_fields).to_dict(),
            access=self.access,
            included_fields=self.included_fields,
            excluded_fields=self.excluded_fields,
            included_methods=self.included_methods,
        )

    def to_response_data(self, glue_model_objects: list[GlueModelObject]) -> GlueQuerySetJsonData:
        return GlueQuerySetJsonData(
            model_objects=[glue_model_object.to_response_data() for glue_model_object in glue_model_objects]
        )
