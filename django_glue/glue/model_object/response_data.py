from dataclasses import dataclass
from typing import Any

from django_glue.glue.model_object.fields.glue import ModelFieldsGlue
from django_glue.response.data import BaseJsonData


@dataclass
class ModelObjectGlueJsonData(BaseJsonData):  # This is a little duplicated but allows us to send more response data.
    fields: ModelFieldsGlue

    def to_dict(self) -> dict:
        return self.fields.to_dict()


@dataclass
class MethodModelObjectGlueJsonData(BaseJsonData):
    method_return: Any

    def to_dict(self) -> dict:
        return {'method_return': self.method_return}
