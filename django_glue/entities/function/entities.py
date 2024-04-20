from django_glue.access.enums import GlueAccess
from django_glue.entities.base_entity import GlueEntity
from django_glue.entities.function.responses import GlueFunctionJsonData
from django_glue.entities.function.sessions import FunctionSessionData
from django_glue.handler.enums import GlueConnection
from django_glue.utils import check_valid_method_kwargs, type_set_method_kwargs


class GlueFunction(GlueEntity):
    def __init__(
            self,
            unique_name: str,
            function_path: str,
    ):
        super().__init__(unique_name, GlueConnection.FUNCTION, GlueAccess.VIEW)
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

    def to_session_data(self) -> FunctionSessionData:
        return FunctionSessionData(
            unique_name=self.unique_name,
            connection=self.connection,
            access=self.access,
            function_path=self.function_path
        )

    def to_response_data(self, function_return) -> GlueFunctionJsonData:
        return GlueFunctionJsonData(function_return)
