from django_glue.access.decorators import check_access
from django_glue.entities.model_object.actions import GlueModelObjectAction
from django_glue.entities.model_object.post_data import UpdateGlueObjectPostData, MethodGlueObjectPostData, GetGlueObjectPostData
from django_glue.entities.model_object.factories import glue_model_object_from_glue_session
from django_glue.entities.model_object.response_data import MethodGlueModelObjectJsonData, GlueModelObjectJsonData
from django_glue.entities.model_object.session_data import GlueModelObjectSessionData
from django_glue.handler.handlers import GlueRequestHandler
from django_glue.response.data import GlueJsonResponseData
from django_glue.response.responses import generate_json_200_response_data


class GetGlueModelObjectHandler(GlueRequestHandler):
    action = GlueModelObjectAction.GET
    _session_data_class = GlueModelObjectSessionData

    @check_access
    def process_response_data(self) -> GlueJsonResponseData:
        glue_model_object = glue_model_object_from_glue_session(self.session_data)
        return generate_json_200_response_data(
            message_title='Success',
            message_body='Successfully retrieved model object!',
            data=GlueModelObjectJsonData(glue_model_object.fields)
        )


class UpdateGlueModelObjectHandler(GlueRequestHandler):
    action = GlueModelObjectAction.UPDATE
    _session_data_class = GlueModelObjectSessionData
    _post_data_class = UpdateGlueObjectPostData

    @check_access
    def process_response_data(self) -> GlueJsonResponseData:
        glue_model_object = glue_model_object_from_glue_session(self.session_data)
        glue_model_object.update(self.post_data.fields)
        return generate_json_200_response_data(
            message_title='Success',
            message_body='Successfully updated model object!',
            data=GlueModelObjectJsonData(glue_model_object.fields)
        )


class DeleteGlueModelObjectHandler(GlueRequestHandler):
    action = GlueModelObjectAction.DELETE
    _session_data_class = GlueModelObjectSessionData

    @check_access
    def process_response_data(self) -> GlueJsonResponseData:
        glue_model_object = glue_model_object_from_glue_session(self.session_data)
        glue_model_object.model_object.delete()
        return generate_json_200_response_data(
            message_title='Success',
            message_body='Successfully deleted model object!',
        )


class MethodGlueModelObjectHandler(GlueRequestHandler):
    action = GlueModelObjectAction.METHOD
    _session_data_class = GlueModelObjectSessionData
    _post_data_class = MethodGlueObjectPostData

    @check_access
    def process_response_data(self) -> GlueJsonResponseData:
        glue_model_object = glue_model_object_from_glue_session(self.session_data)
        method_return = glue_model_object.call_method(self.post_data.method, self.post_data.kwargs)
        return generate_json_200_response_data(
            'THE METHOD ACTION',
            'this is a response from an model object method action!',
            data=MethodGlueModelObjectJsonData(method_return)
        )
