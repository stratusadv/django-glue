from dataclasses import dataclass, field
from typing import Any, Union

from django_glue.glue.model_object.fields.seralizers import serialize_field_value
from django_glue.form.field.field import FormField


@dataclass
class ModelFieldMetaGlue:
    type: str
    name: str
    glue_field: FormField

    def to_dict(self) -> dict:
        return {
            'type': self.type,
            'name': self.name,
            'glue_field': self.glue_field.to_dict(),
        }


@dataclass
class ModelFieldGlue:
    name: str
    value: Any
    _meta: Union[ModelFieldMetaGlue, dict] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            'name': self.name,
            'value': serialize_field_value(self),
            '_meta': self._meta.to_dict()
        }


@dataclass
class ModelFieldsGlue:
    fields: list[ModelFieldGlue] = field(default_factory=list)

    def __iter__(self):
        return self.fields.__iter__()

    def to_dict(self) -> dict:
        return {field.name: field.to_dict() for field in self.fields}
