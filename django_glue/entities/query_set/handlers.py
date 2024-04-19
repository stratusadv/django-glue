from abc import ABC

from django_glue.entities.base_entity import GlueEntity
from django_glue.entities.query_set.factories import decode_query_set_from_str
from django_glue.entities.query_set.sessions import GlueQuerySetSessionData
from django_glue.handler.handlers import GlueRequestHandler
from django_glue.response.data import GlueJsonResponseData
from django_glue.response.responses import generate_json_200_response_data


class GlueQuerySetHandler(GlueRequestHandler, ABC):
    _session_data_class = GlueQuerySetSessionData

    def initialize_glue_entity(self) -> GlueEntity:
        return decode_query_set_from_str(self.session_data.query_set_str)


class GetGlueQuerySetHandler(GlueQuerySetHandler):
    def process_response(self) -> GlueJsonResponseData:
        # Todo: Returns a list of glue model objects
        return generate_json_200_response_data(
            message_title='Success',
            message_body='Successfully retrieved model object!',
            data=self.glue_entity.fields
        )


class UpdateGlueQuerySetHandler(GlueQuerySetHandler):
    def process_response(self) -> GlueJsonResponseData:
        # Todo: Updates and returns a list of model objects

        return generate_json_200_response_data(
            message_title='Success',
            message_body='Successfully updated model object!',
            data=self.glue_entity.generate_field_data()
        )

class DeleteGlueQuerySetHandler(GlueQuerySetHandler):
    def process_response(self) -> GlueJsonResponseData:
        # Todo: Deletes the query set
        return generate_json_200_response_data(
            message_title='Success',
            message_body='Successfully deleted model object!',
        )


class MethodGlueQuerySetHandler(GlueQuerySetHandler):
    def process_response(self) -> GlueJsonResponseData:
        # Todo: Do we call this on they query set or each model object?
        return generate_json_200_response_data(
            'THE METHOD ACTION',
            'this is a response from an model object method action!',
        )
