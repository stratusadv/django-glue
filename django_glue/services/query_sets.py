from typing import Optional

from django.db.models import QuerySet

from django_glue.data_classes import GlueJsonResponseData, GlueBodyData, GlueMetaData
from django_glue.services.services import Service
from django_glue.utils import decode_query_set_from_str


class GlueQuerySetService(Service):
    def __init__(self, meta_data: GlueMetaData) -> None:
        self.meta_data = meta_data
        self.query_set: Optional[QuerySet] = None

    def load_query_set(self):
        self.query_set = decode_query_set_from_str(self.meta_data.query_set_str)

    def process_get_action(self, body_data: GlueBodyData) -> GlueJsonResponseData:

        model_object = self.query_set.get(id=body_data['data']['id'])

    def process_create_action(self, body_data: GlueBodyData) -> GlueJsonResponseData:
        pass

    def process_update_action(self, body_data: GlueBodyData) -> GlueJsonResponseData:
        pass

    def process_delete_action(self, body_data: GlueBodyData) -> GlueJsonResponseData:
        pass

    def process_method_action(self, body_data: GlueBodyData) -> GlueJsonResponseData:
        pass

