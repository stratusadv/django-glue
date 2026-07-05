from typing import Any, ClassVar


from django.http import JsonResponse
from pydantic import BaseModel
from pydantic.dataclasses import dataclass

from django_glue.message import GlueMessage
from django_glue.resolver.action.encoders import ActionDataJSONEncoder


@dataclass
class ActionResult:
    Message: ClassVar[type] = GlueMessage
    proxy_state: BaseModel | None
    payload: dict[str, Any] | None = None
    messages: list[GlueMessage] | None = None
    status: int = 200

    def to_response(self) -> JsonResponse:
        return JsonResponse(
            data={
                'messages': [message.to_dict() for message in self.messages]
                if self.messages is not None
                else None,
                'response_payload': self.payload,
                'proxy_state': self.proxy_state.model_dump() if self.proxy_state else None
            },
            status=self.status,
            safe=True,
            encoder=ActionDataJSONEncoder,
        )

