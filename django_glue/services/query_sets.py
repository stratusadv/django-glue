from django_glue.data_classes import GlueJsonResponseData, GlueBodyData, GlueMetaData
from django_glue.services.services import Service


class GlueQuerySetService(Service):
    def __init__(self, meta_data: GlueMetaData) -> None:
        self.meta_data = meta_data

    def process_get_action(self, body_data: GlueBodyData) -> GlueJsonResponseData:
        pass

    def process_create_action(self, body_data: GlueBodyData) -> GlueJsonResponseData:
        pass

    def process_update_action(self, body_data: GlueBodyData) -> GlueJsonResponseData:
        pass

    def process_delete_action(self, body_data: GlueBodyData) -> GlueJsonResponseData:
        pass

    def process_method_action(self, body_data: GlueBodyData) -> GlueJsonResponseData:
        pass

