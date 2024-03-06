from typing import Optional

from django.contrib.contenttypes.models import ContentType
from django.db.models import Model

from django_glue.data_classes import GlueJsonResponseData, GlueJsonData, GlueBodyData, GlueMetaData
from django_glue.responses import generate_json_200_response_data, generate_json_404_response_data
from django_glue.services.services import Service
from django_glue.utils import generate_simple_field_dict, get_field_names_from_model, check_valid_method_kwargs, \
    type_set_method_kwargs, generate_field_dict


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

        if body_data['data']['function'] == self.function and hasattr(module, self.function):
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
