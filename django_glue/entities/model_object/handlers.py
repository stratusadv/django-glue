from abc import ABC
from dataclasses import dataclass

from django_glue.entities.model_object.entities import GlueEntity
from django_glue.entities.model_object.data import GlueModelObjectSessionData
from django_glue.entities.model_object.factories import glue_model_object_from_glue_session
from django_glue.handler.handlers import GlueRequestHandler


@dataclass
class GlueModelObjectHandler(GlueRequestHandler, ABC):
    _session_data_class = GlueModelObjectSessionData

    def initialize_glue_entity(self) -> GlueEntity:
        return glue_model_object_from_glue_session(self.session_data, self.glue_body_data)


class GetGlueModelObjectHandler(GlueModelObjectHandler):
    def process_response(self):
        pass
