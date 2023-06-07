from __future__ import annotations

from typing import Any
from dataclasses import dataclass, asdict

from django.contrib.contenttypes.models import ContentType

from django_glue.enums import GlueConnection, GlueAccess


@dataclass
class GlueContextData:
    connection: GlueConnection
    access: GlueAccess
    fields: dict
    methods: list

    def to_dict(self) -> dict:
        return asdict(self)

    # @classmethod
    # def from_dict(cls, unique_name_context_dict: dict) -> GlueContextData:
    #     return GlueContextData(
    #         connection=GlueConnection(unique_name_context_dict['connection']),
    #         access=GlueAccess(unique_name_context_dict['access']),
    #         fields=unique_name_context_dict['fields'],
    #         methods=
    #     )


@dataclass
class GlueModelField:
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


class GlueModelObject:
    def __init__(self, app_label, model, object_pk):
        self.app_label = app_label
        self.model = model,
        self.object_pk = object_pk


class GlueQuerySet:
    def __init__(self, app_label, model, query_set):
        self.app_label = app_label
        self.model = model
        self.query_set = query_set