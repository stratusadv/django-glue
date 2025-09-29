from django_glue.access.decorators import check_access
from django_glue.glue.model_object.actions import ModelObjectGlueAction
from django_glue.glue.model_object.response_data import MethodModelObjectGlueJsonData, ModelObjectGlueJsonData
from django_glue.glue.model_object.session_data import ModelObjectGlueSessionData
from django_glue.glue.model_object.tools import model_object_glue_from_session_data
from django_glue.response.data import JsonResponseData
from django_glue.response.responses import generate_json_200_response_data


class GetModelObjectGlueHandler(BaseRequestHandler[ModelObjectGlueSessionData]):
    action = ModelObjectGlueAction.GET

    @check_access
    def process_response_data(self) -> JsonResponseData:
        model_object_glue = model_object_glue_from_session_data(self.session_data)
        return generate_json_200_response_data(
            message_title='Success',
            message_body='Successfully retrieved model object!',
            data=ModelObjectGlueJsonData(model_object_glue.fields)
        )


class UpdateModelObjectGlueHandler(BaseRequestHandler):
    action = ModelObjectGlueAction.UPDATE
    _session_data_class = ModelObjectGlueSessionData
    _post_data_class = UpdatePostData

    @check_access
    def process_response_data(self) -> JsonResponseData:
        model_object_glue = model_object_glue_from_session_data(self.session_data)
        model_object_glue.update(self.post_data.fields)
        return generate_json_200_response_data(
            message_title='Success',
            message_body='Successfully updated model object!',
            data=ModelObjectGlueJsonData(model_object_glue.fields)
        )


class DeleteModelObjectGlueHandler(BaseRequestHandler):
    action = ModelObjectGlueAction.DELETE
    _session_data_class = ModelObjectGlueSessionData

    @check_access
    def process_response_data(self) -> JsonResponseData:
        model_object_glue = model_object_glue_from_session_data(self.session_data)
        model_object_glue.model_object.delete()
        return generate_json_200_response_data(
            message_title='Success',
            message_body='Successfully deleted model object!',
        )


class MethodModelObjectGlueHandler(BaseRequestHandler):
    action = ModelObjectGlueAction.METHOD
    _session_data_class = ModelObjectGlueSessionData
    _post_data_class = MethodPostData

    @check_access
    def process_response_data(self) -> JsonResponseData:
        model_object_glue = model_object_glue_from_session_data(self.session_data)
        method_return = model_object_glue.call_method(self.post_data.method, self.post_data.kwargs)
        return generate_json_200_response_data(
            'THE METHOD ACTION',
            'this is a response from an model object method action!',
            data=MethodModelObjectGlueJsonData(method_return)
        )
