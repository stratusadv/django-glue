from abc import ABC
from dataclasses import dataclass

from django_glue.entities.model_object.entities import GlueEntity
from django_glue.entities.model_object.data import GlueModelObjectMetaData, GlueModelObjectContextData
from django_glue.handler.handlers import GlueRequestHandler


@dataclass
class GlueModelObjectHandler(GlueRequestHandler):
    context_data = GlueModelObjectContextData
    meta_data = GlueModelObjectMetaData

    def initialize_glue_entity(self) -> GlueEntity:
        return model_object_from_glue_session(self.glue_session, self.glue_body_data)

    def process_response(self):
        self.load_object()
        json_data = GlueJsonData()

        json_data.simple_fields = generate_simple_field_dict(
            self.object,
            self.meta_data.fields,
            self.meta_data.exclude,
        )

        json_data.fields = generate_field_dict(self.object, self.meta_data.fields, self.meta_data.exclude)

        return generate_json_200_response_data(
            'THE GET ACTION',
            'this is a response from an model object get action!!! stay tuned!',
            json_data,
        )


