from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any, Optional
from dataclasses import dataclass, asdict

from django.core.serializers.json import DjangoJSONEncoder
from django.http import JsonResponse

from django_glue.response.enums import GlueJsonResponseType, GlueJsonResponseStatus


@dataclass
class GlueJsonData(ABC):

    @abstractmethod
    def to_dict(self):
        return asdict(self)

    def to_json(self):
        return json.dumps(self.to_dict(), cls=DjangoJSONEncoder)


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

        if isinstance(self.data, GlueJsonData):
            self.data = self.data.to_json()

        json_response_dict = asdict(self)

        return json_response_dict

    def to_django_json_response(self) -> JsonResponse:
        return JsonResponse(self.to_dict(), status=self.response_status.value)
