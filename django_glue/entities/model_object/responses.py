import json
from dataclasses import dataclass, field
from typing import Any

from django.core.serializers.json import DjangoJSONEncoder

from django_glue.response.data import GlueJsonData


@dataclass
class GlueModelField:
    name: str
    type: str
    value: Any
    # form_field: 'GlueFormField'
    html_attr: dict

    def to_dict(self) -> dict:
        return json.loads(json.dumps(
            obj={
                'name': self.name,
                'value': self.value,
                # 'form_field': self.form_field.to_dict()
                'html_attr': self.html_attr
            },
            cls=DjangoJSONEncoder)
        )


@dataclass
class GlueModelFields:
    fields: list[GlueModelField] = field(default_factory=list)

    def to_dict(self):
        return {field.name: field.to_dict() for field in self.fields}


@dataclass
class GlueModelObjectJsonData(GlueJsonData):  # This is a little duplicated but allows us to send more response data.
    fields: GlueModelFields

    def to_dict(self):
        return self.fields.to_dict()


@dataclass
class MethodGlueModelObjectJsonData(GlueJsonData):
    method_return: Any

    def to_dict(self):
        return json.loads(
            json.dumps(
                obj={'method_return': self.method_return},
                cls=DjangoJSONEncoder
            )
        )

