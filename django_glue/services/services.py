from abc import ABC, abstractmethod

from django_glue.access.enums import GlueAccess, GlueAction
from django_glue.handler.body_data import GlueBodyData
from django_glue.response.data import GlueJsonResponseData
from django_glue.response.responses import generate_json_404_response_data


class Service(ABC):
    def process_body_data(self, access: GlueAccess, body_data: GlueBodyData) -> GlueJsonResponseData:
        action = body_data.action
        if access.has_access(action.required_access):
            if action == GlueAction.GET:
                return self.process_get_action(body_data)
            if action == GlueAction.UPDATE:
                return self.process_update_action(body_data)
            if action == GlueAction.DELETE:
                return self.process_delete_action(body_data)
            if action == GlueAction.METHOD:
                return self.process_method_action(body_data)
            else:
                return generate_json_404_response_data()
        else:
            return generate_json_404_response_data()

    @abstractmethod
    def process_get_action(self, body_data: GlueBodyData) -> GlueJsonResponseData:
        return generate_json_404_response_data()

    def process_update_action(self, body_data: GlueBodyData) -> GlueJsonResponseData:
        return generate_json_404_response_data()

    def process_delete_action(self, body_data: GlueBodyData) -> GlueJsonResponseData:
        return generate_json_404_response_data()

    def process_method_action(self, body_data: GlueBodyData) -> GlueJsonResponseData:
        return generate_json_404_response_data()

