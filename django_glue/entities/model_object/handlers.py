from abc import ABC

from django_glue.entities.model_object.entities import GlueEntity
from django_glue.entities.model_object.factories import glue_model_object_from_glue_session
from django_glue.entities.model_object.sessions import GlueModelObjectSessionData
from django_glue.handler.handlers import GlueRequestHandler
from django_glue.response.data import GlueJsonResponseData, GlueJsonData
from django_glue.response.responses import generate_json_200_response_data, generate_json_404_response_data
from django_glue.utils import check_valid_method_kwargs, type_set_method_kwargs


class GlueModelObjectHandler(GlueRequestHandler, ABC):
    _session_data_class = GlueModelObjectSessionData

    def initialize_glue_entity(self) -> GlueEntity:
        return glue_model_object_from_glue_session(self.session_data)


class GetGlueModelObjectHandler(GlueModelObjectHandler):
    def process_response(self) -> GlueJsonResponseData:
        return generate_json_200_response_data(
            message_title='Success',
            message_body='Successfully retrieved model object!',
            data=self.glue_entity.fields
        )


class UpdateGlueModelObjectHandler(GlueModelObjectHandler):
    def process_response(self) -> GlueJsonResponseData:
        model_object = self.glue_entity.model_object

        for key, value in self.glue_body_data.data['data'].items():
            if hasattr(model_object, key):
                setattr(model_object, key, value)

        model_object.save()

        return generate_json_200_response_data(
            message_title='Success',
            message_body='Successfully updated model object!',
            data=self.glue_entity.generate_field_data()
        )


class DeleteGlueModelObjectHandler(GlueModelObjectHandler):
    def process_response(self) -> GlueJsonResponseData:
        self.glue_entity.model_object.delete()
        return generate_json_200_response_data(
            message_title='Success',
            message_body='Successfully deleted model object!',
        )


class MethodGlueModelObjectHandler(GlueModelObjectHandler):
    def process_response(self) -> GlueJsonResponseData:
        kwargs = self.glue_body_data.data['kwargs']

        method_return = None
        method_name = self.glue_body_data.data['method']

        if method_name in self.glue_entity.included_methods and hasattr(self.model_class, method_name):
            method = getattr(self.object, method_name)

            if check_valid_method_kwargs(method, kwargs):
                type_set_kwargs = type_set_method_kwargs(method, kwargs)

                method_return = method(**type_set_kwargs)
            else:
                return generate_json_404_response_data()
        else:
            return generate_json_404_response_data()

        json_data = GlueJsonData()

        json_data.method_return = method_return

        return generate_json_200_response_data(
            'THE METHOD ACTION',
            'this is a response from an model object method action!',
            json_data
        )
