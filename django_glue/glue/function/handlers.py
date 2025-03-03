from django_glue.access.decorators import check_access
from django_glue.glue.function.actions import FunctionGlueAction
from django_glue.glue.function.glue import FunctionGlue
from django_glue.glue.function.post_data import CallFunctionGluePostData

from django_glue.glue.function.session_data import FunctionGlueSessionData
from django_glue.handler.handlers import BaseRequestHandler
from django_glue.response.data import JsonResponseData
from django_glue.response.responses import generate_json_200_response_data


class CallFunctionGlueHandler(BaseRequestHandler):
    action = FunctionGlueAction.CALL
    _session_data_class = FunctionGlueSessionData
    _post_data_class = CallFunctionGluePostData

    @check_access
    def process_response_data(self) -> JsonResponseData:
        glue_function = FunctionGlue(
            unique_name=self.session_data.unique_name,
            function_path=self.session_data.function_path
        )
        function_return = glue_function.call(self.post_data.kwargs)
        return generate_json_200_response_data(
            message_title='Success',
            message_body='Successfully retrieved model object!',
            data=glue_function.to_response_data(function_return)
        )

