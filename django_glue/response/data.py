from __future__ import annotations

from abc import ABC
from typing import Any, Optional
from dataclasses import dataclass, asdict

from django.http import JsonResponse

from django_glue.response.enums import GlueJsonResponseType, GlueJsonResponseStatus


@dataclass
class GlueJsonData(ABC):
    """
        Used to provide a consistent structure for our glue objects.
    """
    fields: Optional[dict] = None
    simple_fields: Optional[dict] = None
    method_return: Optional[Any] = None
    function_return: Optional[Any] = None
    custom: Optional[dict] = None

    def to_dict(self):
        return asdict(self)


@dataclass
class GlueJsonResponseData:
    """
        Consistent structure for our json responses.
    """
    message_title: Optional[str] = None
    message_body: Optional[str] = None
    data: Optional[GlueJsonData] = None
    optional_message_data: Optional[dict] = None
    response_type: GlueJsonResponseType = GlueJsonResponseType.SUCCESS
    response_status: GlueJsonResponseStatus = GlueJsonResponseStatus.SUCCESS

    def to_dict(self) -> dict:
        json_response_dict = asdict(self)

        if isinstance(self.data, GlueJsonData):
            json_response_dict['data'] = self.data.to_dict()

        return json_response_dict

    def to_django_json_response(self) -> JsonResponse:
        return JsonResponse(self.to_dict(), status=self.response_status.value)