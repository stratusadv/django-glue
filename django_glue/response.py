from typing import Any

from django.http import JsonResponse

from django_glue.message import GlueMessage
from django_glue.resolver.action.encoders import ActionDataJSONEncoder


class GlueJsonResponse(JsonResponse):
    Message = GlueMessage

    def __init__(
        self,
        payload: dict[str, Any] | None = None,
        messages: list[GlueMessage] | None = None,
        status: int = 200,
    ) -> None:
        super().__init__(
            data={
                'messages': [message.to_dict() for message in messages]
                if messages is not None
                else None,
                'payload': payload,
            },
            status=status,
            encoder=ActionDataJSONEncoder,
        )
