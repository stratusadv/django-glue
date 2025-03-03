from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional, TYPE_CHECKING

from django_glue.access.access import Access

if TYPE_CHECKING:
    from django_glue.access.actions import BaseAction


class BaseRequestHandler(ABC):
    action: BaseAction = None
    _session_data_class: 'GlueSessionData' = None
    _post_data_class: Optional['EntityBodyData'] = None

    def __init__(self, glue_session: 'GlueSession', glue_body_data: 'GlueBodyData'):
        if self._session_data_class is None:
            raise ValueError(f'Please initialize class variable _session_data_class on {self.__class__.__name__}')

        if self.action is None:
            raise ValueError(f'Please initialize class variable action on {self.__class__.__name__}')

        self.unique_name = glue_body_data.unique_name  # Unique name maps what the user is requesting

        if self._post_data_class is None:
            self.post_data = glue_body_data.data
        else:
            self.post_data = self._post_data_class(**glue_body_data.data['data'])  # The data we are expecting in post

        self.session_data = self._session_data_class(**glue_session[self.unique_name])  # data we stored in glue session.

    def has_access(self):
        glue_access = Access(self.session_data.access)
        return glue_access.has_access(self.action.required_access())

    @abstractmethod
    def process_response_data(self) -> 'GlueJsonResponseData':
        # Todo: Do we want to handle an error message here or let the system crash?
        pass
