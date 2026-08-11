from dataclasses import dataclass
from typing import Any, ClassVar, Iterable, Self

from django.conf import settings
from django.http import JsonResponse
from django.urls import reverse

from django_glue.encoders import GlueResponseJSONEncoder
from django_glue.exceptions import GlueError
from django_glue.message import GlueMessage


@dataclass
class GlueResponse:
    Message: ClassVar[type] = GlueMessage

    result: Any = None
    messages: Iterable[GlueMessage] | None = None
    status: int = 200

    def __post_init__(self) -> None:
        self.messages = list(self.messages or [])

    @classmethod
    def from_result(cls, result: Any) -> Self:
        if isinstance(result, cls):
            return result
        return cls(result=result)

    @classmethod
    def from_error(cls, error: GlueError) -> Self:
        is_server_error = error.status >= 500
        expose_details = settings.DEBUG or not is_server_error

        return cls(
            result={
                'error': {
                    'code': error.code,
                    'message': (
                        str(error)
                        if expose_details
                        else 'An unexpected Glue server error occurred.'
                    ),
                    'status': error.status,
                    'details': error.details() if expose_details else {},
                }
            },
            status=error.status,
        )

    def to_payload(self, **extra: Any) -> dict[str, Any]:
        return {
            **extra,
            'result': self.result,
            'messages': [
                message.to_dict() for message in self.messages
            ],
        }

    def to_json_response(self, *, glue_object: Any = None, **extra: Any) -> JsonResponse:
        return JsonResponse(
            self._serialize_glue_values(self.to_payload(**extra), glue_object),
            status=self.status,
            safe=True,
            encoder=GlueResponseJSONEncoder,
        )

    @classmethod
    def _serialize_glue_values(cls, value: Any, glue_object: Any = None) -> Any:
        from django_glue.glue.base import BaseGlue

        if isinstance(value, BaseGlue):
            if glue_object is not None:
                value.request = glue_object.request
            return {
                **value.manifest.model_dump(),
                'state': value.state,
            }

        if isinstance(value, dict):
            return {
                key: cls._serialize_glue_values(item, glue_object)
                for key, item in value.items()
            }

        if isinstance(value, list | tuple):
            return [
                cls._serialize_glue_values(item, glue_object)
                for item in value
            ]

        return value


class GlueRedirectResponse:
    def __new__(cls, view_name: str, **kwargs) -> GlueResponse:
        return GlueResponse(
            result={
                'redirect': {
                    'url': reverse(
                        view_name, kwargs=kwargs
                    )
                }
            }
        )
