from dataclasses import dataclass
from typing import Any, ClassVar


from django.http import JsonResponse
from pydantic import BaseModel

from django_glue.message import GlueMessage
from django_glue.resolver.action.encoders import ActionDataJSONEncoder


@dataclass
class ActionResult:
    Message: ClassVar[type] = GlueMessage
    state: BaseModel | None
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
                'state': self.state.model_dump() if self.state else None
            },
            status=self.status,
            safe=True,
            encoder=ActionDataJSONEncoder,
        )

