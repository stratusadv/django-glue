import base64
import pickle
from typing import Union

from django.contrib.contenttypes.models import ContentType
from django.db.models import QuerySet

from django_glue.access.enums import GlueAccess
from django_glue.entities.base_entity import GlueEntity
from django_glue.entities.query_set.sessions import GlueQuerySetSessionData
from django_glue.handler.enums import GlueConnection


class GlueQuerySet(GlueEntity):
    def __init__(
            self,
            unique_name: str,
            query_set: QuerySet,
            access: Union[GlueAccess, str] = GlueAccess.VIEW,
            connection: GlueConnection = GlueConnection.QUERY_SET,
            included_fields: tuple = ('__all__',),
            excluded_fields: tuple = ('__none__',),
            included_methods: tuple = ('__none__',),
    ):
        super().__init__(unique_name, connection, access)

        self.query_set = query_set

        self.included_fields = included_fields
        self.excluded_fields = excluded_fields
        self.included_methods = included_methods

        content_type = ContentType.objects.get_for_model(query_set.query.model)
        self.app_label = content_type.app_label
        self.model = content_type.model

    def encode_query_set(self):
        return base64.b64encode(pickle.dumps(self.query_set.query)).decode()

    def to_session_data(self) -> GlueQuerySetSessionData:
        return GlueQuerySetSessionData(
            unique_name=self.unique_name,
            query_set_str=self.encode_query_set(),
            connection=self.connection,
            access=self.access,
            app_label=self.app_label,
            model_name=self.model._meta.model_name,
            included_fields=self.included_fields,
            exclude_fields=self.excluded_fields,
            methods=self.included_methods,
        )
