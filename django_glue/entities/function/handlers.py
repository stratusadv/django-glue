from django_glue.access.decorators import check_access
from django_glue.entities.function.actions import GlueFunctionAction
from django_glue.entities.function.entities import GlueFunction
from django_glue.entities.function.post_data import CallGlueFunctionPostData

from django_glue.entities.function.session_data import FunctionSessionData
from django_glue.handler.handlers import GlueRequestHandler
from django_glue.response.data import GlueJsonResponseData
from django_glue.response.responses import generate_json_200_response_data


class CallGlueFunctionHandler(GlueRequestHandler):
    action = GlueFunctionAction.CALL
    _session_data_class = FunctionSessionData
    _post_data_class = CallGlueFunctionPostData

    @check_access
    def process_response_data(self) -> GlueJsonResponseData:
        glue_function = GlueFunction(
            unique_name=self.session_data.unique_name,
            function_path=self.session_data.function_path
        )
        function_return = glue_function.call(self.post_data.kwargs)
        return generate_json_200_response_data(
            message_title='Success',
            message_body='Successfully retrieved model object!',
            data=glue_function.to_response_data(function_return)
        )

