from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import ClassVar, Type

from django_glue.entities.model_object.entities import GlueEntity
from django_glue.handler.data import GlueBodyData
from django_glue.session import GlueSession
from django_glue.session.data import GlueContextData, GlueMetaData


@dataclass
class GlueRequestHandler(ABC):
    """
        This class parses the request, determines the type of request, and then calls the appropriate service.
    """

    glue_session: GlueSession
    glue_body_data: GlueBodyData

    context_data: GlueContextData
    meta_data: GlueMetaData

    unique_name: str = ...

    _context_data_class: ClassVar[Type[GlueContextData]] = ...
    _meta_data_class: ClassVar[Type[GlueMetaData]] = ...

    def __post_init__(self):
        if self.context_data is None or self.meta_data is None:
            raise ValueError('Context data and message data must be set on the handler class.')

        self.unique_name = self.glue_body_data['unique_name']
        self.context_data = self._context_data_class(self.glue_session[self.unique_name]['context_data'])
        self.meta_data = self._meta_data_class(self.glue_session[self.unique_name]['meta_data'])


    # glue_entity: GlueEntity = ...

    # def __post_init__(self):
    #     self.glue_entity = self.initialize_glue_entity()

    # def __init__(self, glue_session: GlueSession, glue_body_data: GlueBodyData):
    #     self.glue_session = glue_session
    #     self.glue_body_data = glue_body_data
    #
    #     self.unique_name = self.glue_body_data['unique_name']
    #     self.context = self.glue_session['context']
    #
    #     self.meta_data: GlueMetaData = GlueMetaData(
    #         **self.glue_session['meta'][self.unique_name]
    #     )
    #
    #     self.connection = GlueConnection(self.context[self.unique_name]['connection'])
    #     self.access = GlueAccess(self.context[self.unique_name]['access'])

    @abstractmethod
    def initialize_glue_entity(self) -> GlueEntity:
        pass

    @abstractmethod()
    def process_response(self):
        pass

    # def process_response(self):
    #
    #     # Todo: Need to be able to build the base entity from the session data.
    #     # Todo: Need to send the body data from the request to whatever is processing it depending on connection type.
    #
    #     if self.connection == GlueConnection.MODEL_OBJECT:
    #         glue_model_object_service = GlueModelObjectService(
    #             self.meta_data,
    #         )
    #
    #         json_response_data = glue_model_object_service.process_body_data(self.access, self.glue_body_data)
    #         return json_response_data.to_django_json_response()
    #
    #     elif self.connection == GlueConnection.QUERY_SET:
    #         glue_query_set_service = GlueQuerySetService(
    #             self.meta_data,
    #         )
    #
    #         json_response_data = glue_query_set_service.process_body_data(self.access, self.glue_body_data)
    #         return json_response_data.to_django_json_response()
    #
    #     elif self.connection == GlueConnection.TEMPLATE:
    #         glue_template_service = GlueTemplateService(
    #             self.meta_data,
    #         )
    #
    #         html_response_data = glue_template_service.process_body_data(self.access, self.glue_body_data)
    #         return html_response_data
    #
    #     elif self.connection == GlueConnection.FUNCTION:
    #         glue_function_service = GlueFunctionService(
    #             self.meta_data,
    #         )
    #         json_response_data = glue_function_service.process_body_data(self.access, self.glue_body_data)
    #         return json_response_data.to_django_json_response()
    #
    #     else:
    #         return generate_json_404_response()
