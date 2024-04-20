from abc import ABC, abstractmethod
from typing import Optional

from django_glue.access.access import GlueAccess


class GlueRequestHandler(ABC):
    action: 'GlueAction' = None  # Actually define the glue action on the class.
    _session_data_class: 'GlueSessionData' = None  # Tell us what data to expect from the session.
    _post_data_class: Optional['EntityBodyData'] = None

    def __init__(self, glue_session: 'GlueSession', glue_body_data: 'GlueBodyData'):
        if self._session_data_class is None:
            raise ValueError(f'Please initialize class variable _session_data_class on {self.__class__.__name__}')

        if self.action is None:
            raise ValueError(f'Please initialize class variable action on {self.__class__.__name__}')

        self.unique_name = glue_body_data.unique_name

        if self._post_data_class is None:
            self.post_data = glue_body_data.data
        else:
            self.post_data = self._post_data_class(**glue_body_data.data['data'])

        self.session_data = self._session_data_class(**glue_session[self.unique_name])  # Expected session data.

    def has_access(self):
        glue_access = GlueAccess(self.session_data.access)
        return glue_access.has_access(self.action.required_access())

    @abstractmethod
    def process_response(self) -> 'GlueJsonResponseData':
        pass
