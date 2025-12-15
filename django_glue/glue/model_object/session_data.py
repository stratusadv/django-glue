from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Union, Type, TYPE_CHECKING

from django.apps import apps
from django.db.models import Model

from django_glue.glue.model_object.fields.glue import ModelFieldGlue
from django_glue.session.data import SessionData

if TYPE_CHECKING:
    from django_glue.glue.model_object.glue import ModelObjectGlue


@dataclass
class ModelObjectGlueSessionData(SessionData):
    app_label: str
    model_name: str
    object_pk: Union[int, str, uuid.uuid4]
    fields: list[ModelFieldGlue] # Should be ModelFieldsGlue?
    included_fields: Union[list, tuple]
    # This seems like it should be named excluded_fields to match
    # QuerySetGlueSessionData's excluded_fields (or vice versa)
    exclude_fields: Union[list, tuple]
    # This seems like it should be named included_methods be the same as
    # QuerySetGlueSessionData's included_methods (or vice versa)
    methods: Union[list, tuple]

    def __post_init__(self):
        if isinstance(self.object_pk, uuid.UUID):
            self.object_pk = str(self.object_pk)

    def to_model_object_glue(self) -> ModelObjectGlue:
        from django_glue.glue.model_object.glue import ModelObjectGlue
        model: type | Type[Model] = apps.get_model(
            self.app_label,
            self.model_name
        )

        try:
            model_object = model.objects.get(pk=self.object_pk)
        except model.DoesNotExist:
            model_object = model()

        return ModelObjectGlue(
            model_object=model_object,
            unique_name=self.unique_name,
            access=self.access,
            included_fields=self.included_fields,
            excluded_fields=self.exclude_fields,
            included_methods=self.methods,
        )