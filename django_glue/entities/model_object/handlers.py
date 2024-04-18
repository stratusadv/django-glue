from dataclasses import dataclass

from django_glue.entities.model_object.entities import GlueEntity
from django_glue.handler.handlers import GlueRequestHandler


@dataclass
class GlueModelObjectRequestHandler(GlueRequestHandler):

    def initialize_glue_entity(self) -> GlueEntity:
        pass

    def process_response(self):
        pass