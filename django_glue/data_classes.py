from __future__ import annotations

import json
from typing import Any, Optional, Union
from dataclasses import dataclass, asdict

from django.contrib.contenttypes.models import ContentType
from django.http import JsonResponse

from django_glue.enums import GlueConnection, GlueAccess, GlueAction, GlueJsonResponseStatus, GlueJsonResponseType
from django_glue.core.utils import remove_none_value_field_from_data_class_object


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

    @property
    def unique_name(self) -> str:
        return self.data['unique_name']


@dataclass
class GlueContextData:
    connection: GlueConnection
    access: GlueAccess = None
    fields: dict[GlueModelFieldData] = None
    methods: list[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class GlueJsonData:
    fields: Optional[dict] = None
    simple_fields: Optional[dict] = None
    method_return: Optional[Any] = None
    custom: Optional[dict] = None

    def to_dict(self):
        remove_none_value_field_from_data_class_object(self)
        return asdict(self)


@dataclass
class GlueJsonResponseData:
    message_title: Optional[str] = None
    message_body: Optional[str] = None
    data: Optional[GlueJsonData] = None
    optional_message_data: Optional[dict] = None
    response_type: GlueJsonResponseType = GlueJsonResponseType.SUCCESS
    response_status: GlueJsonResponseStatus = GlueJsonResponseStatus.SUCCESS

    def to_dict(self) -> dict:
        remove_none_value_field_from_data_class_object(self)

        json_response_dict = asdict(self)

        if isinstance(self.data, GlueJsonData):
            json_response_dict['data'] = self.data.to_dict()

        return json_response_dict

    def to_django_json_response(self) -> JsonResponse:
        return JsonResponse(self.to_dict(), status=self.response_status.value)


@dataclass
class GlueModelFieldData:
    type: str
    value: Any
    html_attr: dict

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class GlueMetaData:
    """
        # Todo: Should this handle both queryset and models? Should this be split into two classes?
        This class is used to store meta data about the model or query set.
    """
    app_label: str = None
    model: str = None
    object_pk: int = None
    query_set_str: str = None
    template: str = None
    fields: Union[list, tuple] = None
    exclude: Union[list, tuple] = None
    methods: Union[list, tuple] = None

    @property
    def model_class(self):
        return ContentType.objects.get_by_natural_key(self.app_label, self.model).model_class()

    def to_dict(self) -> dict:
        return asdict(self)
