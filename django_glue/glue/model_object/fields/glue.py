from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Union, Type

from django.db.models import Model

from django_glue.constants import NONE_DUNDER_KEY, ALL_DUNDER_KEY
from django_glue.form.field.factories import FormFieldFactory
from django_glue.form.field.field import FormField
from django_glue.glue.model_object.fields.seralizers import serialize_field_value


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

    def load_value_from_model_object(
            self,
            model_object: Model,
    ):
        relational = ['ForeignKey', 'BinaryField', 'OnetoOneField']
        if self._meta.type in relational:
            self.value = getattr(model_object, f'{self.name}_id')
        else:
            self.value = getattr(model_object, self.name)


@dataclass
class ModelFieldsGlue:
    fields: list[ModelFieldGlue] = field(default_factory=list)

    def __iter__(self):
        return self.fields.__iter__()

    def to_dict(self) -> dict:
        return {field.name: field.to_dict() for field in self.fields}

    @staticmethod
    def _field_name_included(
        name: str,
        fields: list | tuple,
        exclude: list | tuple,
    ) -> bool:
        included = False

        if name not in exclude or exclude[0] == NONE_DUNDER_KEY:
            if name in fields or fields[0] == ALL_DUNDER_KEY:
                included = True

        return included

    @classmethod
    def from_model_object(
        cls,
        model: Type[Model],
        included_fields: tuple,
        excluded_fields: tuple
    ) -> ModelFieldsGlue:
        fields = []

        for model_field in model._meta.fields:
            if cls._field_name_included(
                model_field.name,
                included_fields,
                excluded_fields
            ):
                _meta = ModelFieldMetaGlue(
                    type=model_field.get_internal_type(),
                    name=model_field.name,
                    glue_field=FormFieldFactory(model_field).factory_method()
                )

                glue_model_field = ModelFieldGlue(
                    name=model_field.name,
                    value=None,
                    _meta=_meta
                )

                fields.append(glue_model_field)

        return ModelFieldsGlue(fields=fields)

    def load_values_from_model_object(
            self,
            model_object: Model,
    ):
        for _field in self.fields:
            _field.load_value_from_model_object(model_object)