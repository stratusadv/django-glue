from django_glue.data_classes import GlueJsonResponseData, GlueBodyData
from django_glue.services.services import Service


class GlueQuerySetService(Service):
    def __init__(self, app_label, model, query_set):
        self.app_label = app_label
        self.model = model
        self.query_set = query_set

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

