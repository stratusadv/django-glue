from abc import ABC
from dataclasses import dataclass

from django_glue.entities.model_object.entities import GlueEntity, GlueModelObject
from django_glue.entities.model_object.factories import glue_model_object_from_glue_session
from django_glue.entities.model_object.sessions import GlueModelObjectSessionData
from django_glue.handler.handlers import GlueRequestHandler
from django_glue.response.data import GlueJsonResponseData
from django_glue.response.responses import generate_json_200_response_data


@dataclass
class GlueModelObjectHandler(GlueRequestHandler, ABC):
    glue_entity: GlueModelObject
    _session_data_class = GlueModelObjectSessionData

    def initialize_glue_entity(self) -> GlueEntity:
        return glue_model_object_from_glue_session(self.unique_name, self.session_data)


class GetGlueModelObjectHandler(GlueModelObjectHandler):
    def process_response(self) -> GlueJsonResponseData:
        return generate_json_200_response_data(
            message_title='Success',
            message_body='Successfully retrieved model object!',
            data=self.glue_entity.fields
        )
