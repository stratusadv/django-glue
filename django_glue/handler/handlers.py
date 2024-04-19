from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import ClassVar, Type

from django_glue.entities.model_object.entities import GlueEntity
from django_glue.handler.data import GlueBodyData
from django_glue.session import GlueSession
from django_glue.session.data import GlueSessionData, GlueMetaData


@dataclass
class GlueRequestHandler(ABC):
    """
        This class parses the request, determines the type of request, and then calls the appropriate service.
    """

    glue_session: GlueSession
    glue_body_data: GlueBodyData
    unique_name: str

    glue_entity: GlueEntity = ...
    session_data: GlueSessionData = ...
    _session_data_class: ClassVar[Type[GlueSessionData]] = None

    def __post_init__(self):
        if self._session_data_class is None:
            raise ValueError('You must add a session data class to the Handler.')

        self.unique_name = self.glue_body_data['unique_name']
        self.session_data = self._session_data_class(self.glue_session[self.unique_name])
        self.glue_entity = self.initialize_glue_entity()

    @abstractmethod
    def initialize_glue_entity(self) -> GlueEntity:
        pass

    @abstractmethod
    def process_response(self):
        pass
