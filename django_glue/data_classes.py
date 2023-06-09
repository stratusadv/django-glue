from __future__ import annotations

import json
from typing import Any, Optional
from dataclasses import dataclass, asdict

from django.contrib.contenttypes.models import ContentType
from django.http import JsonResponse


from django_glue.enums import GlueConnection, GlueAccess, GlueAction, GlueJsonResponseStatus, GlueJsonResponseType


class GlueBodyData:
    def __init__(self, request_body):
        self.data = json.loads(request_body.decode('utf-8'))
        self.glue_action = GlueAction(self.data['action'])

    def __getitem__(self, key):
        return self.data[key]

    def __setitem__(self, key, value):
        self.data[key] = value

    @property
    def action(self) -> GlueAction:
        return self.glue_action


@dataclass
class GlueContextData:
    connection: GlueConnection
    access: GlueAccess
    fields: dict
    methods: list

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class GlueJsonResponseData:
    message_title: str
    message_body: str
    response_type: GlueJsonResponseType = GlueJsonResponseType.SUCCESS
    response_status: GlueJsonResponseStatus = GlueJsonResponseStatus.SUCCESS
    message_dict: Optional[dict] = None
    additional_data: Optional[dict] = None

    def to_dict(self) -> dict:
        return asdict(self)

    def to_django_json_response(self) -> JsonResponse:
        if self.message_dict is None:
            self.message_dict = dict()

        if self.additional_data is None:
            self.additional_data = dict()

        return JsonResponse(asdict(self), status=self.response_status.value)


@dataclass
class GlueModelFieldData:
    type: str
    value: Any
    html_attr: dict

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class GlueMetaData:
    app_label: str
    model: str
    object_pk: int = None
    query_set_str: str = None

    @property
    def model_class(self):
        return ContentType.objects.get_by_natural_key(self.app_label, self.model).model_class()

    def to_dict(self) -> dict:
        return asdict(self)
