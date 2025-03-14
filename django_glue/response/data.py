from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from typing import Optional

from django.core.serializers.json import DjangoJSONEncoder
from django.http import JsonResponse

from django_glue.response.enums import JsonResponseType, JsonResponseStatus


@dataclass
class BaseJsonData(ABC):

    @abstractmethod
    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), cls=DjangoJSONEncoder)


@dataclass
class JsonResponseData:
    """
        Consistent structure for our json responses.
    """
    message_title: Optional[str] = None
    message_body: Optional[str] = None
    data: Optional[BaseJsonData] = None
    optional_message_data: Optional[dict] = None
    response_type: JsonResponseType = JsonResponseType.SUCCESS
    response_status: JsonResponseStatus = JsonResponseStatus.SUCCESS

    def to_dict(self) -> dict:

        if isinstance(self.data, BaseJsonData):
            self.data = self.data.to_json()

        json_response_dict = asdict(self)

        return json_response_dict

    def to_django_json_response(self) -> JsonResponse:
        return JsonResponse(self.to_dict(), status=self.response_status.value)
