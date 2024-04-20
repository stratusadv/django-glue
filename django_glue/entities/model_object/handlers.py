from django_glue.access.decorators import check_access
from django_glue.entities.model_object.actions import GlueModelObjectAction
from django_glue.entities.model_object.body_data import UpdateGlueObjectPostData
from django_glue.entities.model_object.factories import glue_model_object_from_glue_session
from django_glue.entities.model_object.sessions import GlueModelObjectSessionData
from django_glue.handler.handlers import GlueRequestHandler
from django_glue.response.data import GlueJsonData, GlueJsonResponseData
from django_glue.response.responses import generate_json_200_response_data, generate_json_404_response_data
from django_glue.utils import check_valid_method_kwargs, type_set_method_kwargs


class GetGlueModelObjectHandler(GlueRequestHandler):
    action = GlueModelObjectAction.GET
    _session_data_class = GlueModelObjectSessionData

    @check_access
    def process_response(self) -> GlueJsonResponseData:
        glue_model_object = glue_model_object_from_glue_session(self.session_data)
        return generate_json_200_response_data(
            message_title='Success',
            message_body='Successfully retrieved model object!',
            data=glue_model_object.to_response_data()
        )


class UpdateGlueModelObjectHandler(GlueRequestHandler):
    action = GlueModelObjectAction.UPDATE
    _session_data_class = GlueModelObjectSessionData
    _post_data_class = UpdateGlueObjectPostData

    @check_access
    def process_response(self) -> GlueJsonResponseData:
        glue_model_object = glue_model_object_from_glue_session(self.session_data)
        model_object = glue_model_object.model_object

        for key, value in self.post_data.fields.items():
            if hasattr(model_object, key):
                setattr(model_object, key, value)

        model_object.save()
        glue_model_object.update()

        return generate_json_200_response_data(
            message_title='Success',
            message_body='Successfully updated model object!',
            data=glue_model_object.to_response_data()
        )


class DeleteGlueModelObjectHandler(GlueRequestHandler):
    action = GlueModelObjectAction.DELETE
    _session_data_class = GlueModelObjectSessionData

    @check_access
    def process_response(self) -> GlueJsonResponseData:
        glue_model_object = glue_model_object_from_glue_session(self.session_data)
        glue_model_object.model_object.delete()
        return generate_json_200_response_data(
            message_title='Success',
            message_body='Successfully deleted model object!',
        )


class MethodGlueModelObjectHandler(GlueRequestHandler):
    action = GlueModelObjectAction.METHOD
    _session_data_class = GlueModelObjectSessionData

    @check_access
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
