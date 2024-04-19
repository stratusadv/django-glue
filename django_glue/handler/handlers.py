from abc import ABC, abstractmethod

from django_glue.entities.model_object.entities import GlueEntity
from django_glue.handler.data import GlueBodyData
from django_glue.response.data import GlueJsonResponseData
from django_glue.session import GlueSession
from django_glue.session.data import GlueSessionData


class GlueRequestHandler(ABC):
    _session_data_class: GlueSessionData = None

    def __init__(self, glue_session: GlueSession, glue_body_data: GlueBodyData):
        if self._session_data_class is None:
            raise ValueError('Please initialize both _session_data_class and _glue_entity_class on your handler')

        self.glue_body_data = glue_body_data

        self.unique_name = self.glue_body_data.unique_name
        self.action = self.glue_body_data.action

        self.session_data = self._session_data_class(**glue_session[self.unique_name])

        self.glue_entity = self.initialize_glue_entity()

    def has_access(self):
        # Todo: Check access to call
        pass

    @abstractmethod
    def initialize_glue_entity(self) -> GlueEntity:
        pass

    @abstractmethod
    def process_response(self) -> GlueJsonResponseData:
        pass
