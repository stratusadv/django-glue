from django_glue.access.access import Access
from django_glue.glue.enums import GlueType
from django_glue.glue.function.response_data import FunctionGlueJsonData
from django_glue.glue.function.session_data import FunctionGlueSessionData
from django_glue.glue.glue import BaseGlue
from django_glue.utils import check_valid_method_kwargs, type_set_method_kwargs


class FunctionGlue(BaseGlue):
    def __init__(
            self,
            unique_name: str,
            function_path: str,
    ):
        super().__init__(unique_name, GlueType.FUNCTION, Access.VIEW)
        self.function_path = function_path

        self.module_name = '.'.join(function_path.split('.')[:-1])
        self.function_name = function_path.split('.')[-1]

    def call(self, function_kwargs):
        module = __import__(self.module_name, fromlist=[self.function_name])

        if hasattr(module, self.function_name):
            function = getattr(module, self.function_name)

            if check_valid_method_kwargs(function, function_kwargs):
                type_set_kwargs = type_set_method_kwargs(function, function_kwargs)

                return function(**type_set_kwargs)

        return None

    def to_session_data(self) -> FunctionGlueSessionData:
        return FunctionGlueSessionData(
            unique_name=self.unique_name,
            glue_type=self.glue_type,
            access=self.access,
            function_path=self.function_path
        )

    @staticmethod
    def to_response_data(function_return) -> FunctionGlueJsonData:
        return FunctionGlueJsonData(function_return)
