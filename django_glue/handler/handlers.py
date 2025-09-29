from __future__ import annotations

import json

from django.http import HttpRequest, HttpResponse

from django_glue.access.access import Access
from django_glue.glue.enums import GlueType
from django_glue.handler.data import GlueRequestData
from django_glue.settings import DJANGO_GLUE_SESSION_NAME


class GlueRequestProcessor:
    def __init__(self, request: HttpRequest):
        request_data = GlueRequestData(**json.loads(request.body.decode('utf-8')))
        glue_type = GlueType(request_data.glue_type)
        self.action = glue_type.action_type(request_data.action)
        self.action_kwargs = self.action.action_kwargs_type(**request_data.action_kwargs)
        self.glue_obj = glue_type.glue_class(
            session_data=request.session[DJANGO_GLUE_SESSION_NAME][request_data.unique_name]
        )

    def has_access(self) -> bool:
        access = Access(self.glue_obj.access)
        return access.has_access(self.action.required_access())

    def process_response(self) -> HttpResponse:
        return self.glue_obj.process_action_against_session(self.action, self.action_kwargs)



