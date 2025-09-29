from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from django.http import HttpRequest, JsonResponse

from django_glue.access.access import Access
from django_glue.constants import UNIQUE_NAME_KEY, ACTION_KEY, GLUE_TYPE_KEY
from django_glue.glue.enums import GlueType
from django_glue.session import Session

if TYPE_CHECKING:
    from django_glue.handler.body import GlueRequest


class GlueRequest:
    def __init__(self, django_request: HttpRequest):
        self.data = json.loads(django_request.body.decode('utf-8'))
        self.session = Session(django_request)

        # Validate and set unique name
        if UNIQUE_NAME_KEY not in self.data:
            raise KeyError(f'Glue request data must contain an entry for {UNIQUE_NAME_KEY}')
        self.unique_name = self.data[UNIQUE_NAME_KEY]
        if self.unique_name not in self.session:
            raise KeyError(f'Glue request session must contain an entry for {self.unique_name}')

        # Validate and set action
        if ACTION_KEY not in self.data:
            raise KeyError(f'Glue request data must contain an entry for {UNIQUE_NAME_KEY}')
        self.action = self.data[ACTION_KEY]

        # Validate and set glue type
        if GLUE_TYPE_KEY not in self.session[self.unique_name]:
            raise KeyError(f'Glue request session entry for {self.unique_name} is missing entry for {GLUE_TYPE_KEY}')
        self.glue_type = GlueType(self.session[self.unique_name][GLUE_TYPE_KEY])

    def __getitem__(self, key: str) -> Any:
        return self.data[key]

    def __setitem__(self, key: str, value: Any):
        self.data[key] = value


class GlueResponse:
    def __init__(self, data: dict):
        self.data = data


class BaseGlueRequestProcessor(ABC):
    @abstractmethod
    def process(self) -> JsonResponse:
        pass


class GlueRequestProcessor(BaseGlueRequestProcessor):
    def __init__(self, request: HttpRequest):
        self.glue_request = GlueRequest(request)

        if self._post_data_class is None:
            self.post_data = self.glue_request.data
        else:
            self.post_data = self._post_data_class(**self.glue_request.data['data'])  # The data we are expecting in post

        self.session_data = self._session_data_class(**self.glue_request[self.unique_name])  # data we stored in glue session.

    def has_access(self) -> bool:
        access = Access(self.session_data.access)
        return access.has_access(self.action.required_access())

    def process(self) -> JsonResponse:
        # Todo: Do we want to handle an error message here or let the system crash?
        pass
