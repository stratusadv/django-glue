from dataclasses import dataclass, field
from typing import Any, ClassVar

from django.http import JsonResponse
from django.urls import reverse

from django_glue.message import GlueMessage
from django_glue.resolver.attribute_event.encoders import BoundAttributeDataJSONEncoder


@dataclass
class GlueResponse:
    Message: ClassVar[type] = GlueMessage
    state: dict | None = None
    policy: dict | None = None
    result: Any = None
    messages: list[GlueMessage] = field(default_factory=list)
    status: int = 200

    def to_json_response(self) -> JsonResponse:
        data = {
            'result': self.result if self.result is not None else {},
            'state': self.state,
            'messages': [message.to_dict() for message in self.messages]
        }
        if self.policy is not None:
            data['policy'] = self.policy
        if self.messages is not None:
            data['messages'] = [message.to_dict() for message in self.messages]

        return JsonResponse(
            data=data,
            status=self.status,
            safe=True,
            encoder=BoundAttributeDataJSONEncoder,
        )


class GlueRedirectResponse:
    def __new__(cls, view_name: str, **kwargs) -> GlueResponse:
        return GlueResponse(
            result={
                'redirect': {
                    'url': reverse(
                        'django_spire:auth:user:page:detail', kwargs=kwargs
                    )
                }
            }
        )
