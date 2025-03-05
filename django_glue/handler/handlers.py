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

    def __init__(self, session: 'GlueSession', request_body: 'GlueBodyData'):
        if self._session_data_class is None:
            raise ValueError(f'Please initialize class variable _session_data_class on {self.__class__.__name__}')

        if self.action is None:
            raise ValueError(f'Please initialize class variable action on {self.__class__.__name__}')

        self.unique_name = request_body.unique_name  # Unique name maps what the user is requesting

        if self._post_data_class is None:
            self.post_data = request_body.data
        else:
            self.post_data = self._post_data_class(**request_body.data['data'])  # The data we are expecting in post

        self.session_data = self._session_data_class(**session[self.unique_name])  # data we stored in glue session.

    def has_access(self):
        access = Access(self.session_data.access)
        return access.has_access(self.action.required_access())

    @abstractmethod
    def process_response_data(self) -> 'JsonResponseData':
        # Todo: Do we want to handle an error message here or let the system crash?
        pass
