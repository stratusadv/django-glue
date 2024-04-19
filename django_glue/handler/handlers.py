from abc import ABC, abstractmethod

from django_glue.access.access import GlueAccess
from django_glue.access.decorators import check_access


class GlueRequestHandler(ABC):
    _session_data_class: 'GlueSessionData' = None
    _action_class: 'GlueAction' = None

    def __init__(self, glue_session: 'GlueSession', glue_body_data: 'GlueBodyData'):
        if self._session_data_class is None or self._action_class is None:
            raise ValueError('Please initialize both _session_data_class and _action_class on your handler')

        self.glue_body_data = glue_body_data

        self.unique_name = self.glue_body_data.unique_name
        self.action = self._action_class(self.glue_body_data.action)

        self.session_data = self._session_data_class(**glue_session[self.unique_name])

        self.glue_entity = self.initialize_glue_entity()

    def has_access(self):
        glue_access = GlueAccess(self.session_data.access)
        return glue_access.has_access(self.action.required_access())

    @abstractmethod
    def initialize_glue_entity(self) -> 'GlueEntity':
        pass

    @abstractmethod
    @check_access
    def process_response(self) -> 'GlueJsonResponseData':
        pass
