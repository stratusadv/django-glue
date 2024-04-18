from django_glue.handler.data import GlueBodyData
from django_glue.response.data import GlueJsonResponseData, GlueJsonData
from django_glue.response.responses import generate_json_200_response_data, generate_json_404_response_data
from django_glue.services.services import Service
from django_glue.session.data import GlueMetaData
from django_glue.utils import check_valid_method_kwargs, type_set_method_kwargs


class GlueFunctionService(Service):
    def __init__(self, meta_data: GlueMetaData) -> None:
        self.meta_data = meta_data
        self.module_name = None
        self.function = None

    def load_function(self):
        self.module_name = '.'.join(self.meta_data.function.split('.')[:-1])
        self.function = self.meta_data.function.split('.')[-1]

    def process_get_action(self, body_data: GlueBodyData) -> GlueJsonResponseData:
        self.load_function()
        kwargs = body_data['data']['kwargs']
        function_return = None
        module = __import__(self.module_name, fromlist=[self.function])

        if hasattr(module, self.function):
            function = getattr(module, self.function)

            if check_valid_method_kwargs(function, kwargs):
                type_set_kwargs = type_set_method_kwargs(function, kwargs)

                function_return = function(**type_set_kwargs)
            else:
                return generate_json_404_response_data()
        else:
            return generate_json_404_response_data()

        json_data = GlueJsonData()
        json_data.function_return = function_return

        return generate_json_200_response_data(
            'FUNCTION CALL',
            'this is a response from an function call!',
            json_data
        )
