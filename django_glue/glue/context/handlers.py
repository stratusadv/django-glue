from __future__ import annotations

from typing import TYPE_CHECKING

from django_glue.access.decorators import check_access
from django.contrib.auth import get_user_model
from django_glue.glue.context.actions import ContextGlueAction
from django_glue.glue.context.glue import ContextGlue
from django_glue.glue.context.permissions import create_permission_checker
from django_glue.glue.context.session_data import ContextGlueSessionData
from django_glue.handler.handlers import BaseRequestHandler
from django_glue.response.responses import generate_json_200_response_data

if TYPE_CHECKING:
    from django_glue.response.data import JsonResponseData


class GetContextGlueHandler(BaseRequestHandler):
    action = ContextGlueAction.GET
    _session_data_class = ContextGlueSessionData

    @check_access
    def process_response_data(self) -> JsonResponseData:
        user = None

        if hasattr(self.session_data, 'user_id') and self.session_data.user_id:
            user = get_user_model().objects.filter(id=self.session_data.user_id).first()

        permission_checker = None

        if user:
            permission_checker = create_permission_checker(user)

        context_glue = ContextGlue(
            unique_name=self.session_data.unique_name,
            context_data=self.session_data.context_data,
            access=self.session_data.access,
            exclude=self.session_data.exclude,
            user=user,
            permission_checker=permission_checker
        )

        return generate_json_200_response_data(
            message_title='Success',
            message_body='Successfully retrieved context data!',
            data=context_glue.to_response_data()
        )
