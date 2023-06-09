from django_glue.data_classes import GlueJsonResponseData, GlueBodyData
from django_glue.services.services import Service


class GlueModelObjectService(Service):
    def __init__(self, app_label, model, object_pk):
        self.app_label = app_label
        self.model = model,
        self.object_pk = object_pk

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


